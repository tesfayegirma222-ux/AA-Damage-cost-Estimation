import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- GOOGLE SHEETS CONNECTION ---
def connect_gs():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Streamlit handles secrets better via st.secrets, but we'll use your json for now
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
        return client.open("Asset_Damage_System")
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

gc = connect_gs()

# --- AUTHENTICATION LOGIC ---
def login():
    st.sidebar.title("🔐 Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    
    if st.sidebar.button("Login"):
        user_sheet = gc.worksheet("Users")
        users_df = pd.DataFrame(user_sheet.get_all_records())
        
        user_data = users_df[(users_df['Username'] == username) & (users_df['Password'] == str(password))]
        
        if not user_data.empty:
            st.session_state['logged_in'] = True
            st.session_state['user'] = username
            st.session_state['role'] = user_data.iloc[0]['Role']
            st.rerun()
        else:
            st.sidebar.error("Invalid credentials")

# --- APP MODULES ---
def asset_registry():
    st.header("🏗️ Asset Registration")
    with st.form("asset_form"):
        name = st.text_input("Asset Name")
        category = st.selectbox("Category", ["Roadside", "Pavement", "Signage", "Lighting"])
        unit = st.text_input("Unit (e.g., Meter, Piece)")
        cost = st.number_input("Standard Unit Cost", min_value=0.0)
        
        if st.form_submit_button("Register Asset"):
            ws = gc.worksheet("AssetRegistry")
            ws.append_row([len(ws.get_all_values()), name, category, unit, cost])
            st.success(f"Asset '{name}' added successfully!")

def damage_reporting():
    st.header("🚨 Damage Reporting")
    # Fetch asset names for the dropdown
    asset_ws = gc.worksheet("AssetRegistry")
    assets = pd.DataFrame(asset_ws.get_all_records())['Asset Name'].tolist()
    
    with st.form("damage_form"):
        case_no = st.text_input("Case Number (Reference)")
        asset_name = st.selectbox("Select Damaged Asset", assets)
        location = st.text_input("Location Details")
        gps = st.text_input("GPS Coordinates")
        date = st.date_input("Date of Incident")
        
        if st.form_submit_button("Submit Report"):
            ws = gc.worksheet("DamageReports")
            ws.append_row([case_no, asset_name, location, gps, str(date), st.session_state['user'], "Pending"])
            st.success("Report submitted to Road Asset Management.")

def cost_estimation():
    st.header("💰 Engineering Cost Estimation")
    # Get pending reports
    reports_ws = gc.worksheet("DamageReports")
    reports_df = pd.DataFrame(reports_ws.get_all_records())
    pending_cases = reports_df[reports_df['Status'] == 'Pending']['Case No'].tolist()
    
    if not pending_cases:
        st.info("No pending damage reports to estimate.")
        return

    case_select = st.selectbox("Select Case Number", pending_cases)
    qty = st.number_input("Quantity Damaged", min_value=0.1)
    
    # Auto-fetch Unit Cost from Registry
    asset_name = reports_df[reports_df['Case No'] == case_select]['Asset Name'].values[0]
    registry_df = pd.DataFrame(gc.worksheet("AssetRegistry").get_all_records())
    unit_cost = registry_df[registry_df['Asset Name'] == asset_name]['Unit Cost'].values[0]
    
    st.write(f"**Asset:** {asset_name} | **Standard Unit Cost:** ${unit_cost}")
    
    # Logic: Subtotal = Qty * Cost
    subtotal = qty * unit_cost
    vat = subtotal * 0.15
    grand_total = subtotal + vat
    
    st.metric("Estimated Grand Total (Incl. 15% VAT)", f"${grand_total:,.2f}")

    if st.button("Finalize and Send for Approval"):
        ws = gc.worksheet("Estimations")
        ws.append_row([case_select, qty, subtotal, vat, grand_total, st.session_state['user'], "No"])
        st.success("Estimation saved and synced to Cloud.")

# --- ADMIN USER MANAGEMENT ---
def admin_panel():
    st.header("👥 User Management")
    with st.expander("Add New User"):
        new_u = st.text_input("New Username")
        new_p = st.text_input("New Password")
        new_r = st.selectbox("Role", ["Admin", "Safety", "Engineer", "Manager"])
        if st.button("Create User"):
            gc.worksheet("Users").append_row([new_u, new_p, new_r])
            st.success("User added.")
    
    st.subheader("Current Users")
    users_df = pd.DataFrame(gc.worksheet("Users").get_all_records())
    st.dataframe(users_df)

# --- MAIN NAVIGATION ---
if 'logged_in' not in st.session_state:
    login()
else:
    st.sidebar.write(f"Logged in as: **{st.session_state['user']}**")
    task = st.sidebar.radio("Navigation", ["Dashboard", "Asset Registry", "Damage Reporting", "Cost Estimation", "Admin Panel"])
    
    if st.sidebar.button("Logout"):
        del st.session_state['logged_in']
        st.rerun()

    if task == "Dashboard":
        st.title("📊 System Overview")
        # Load and show damage reports using Pandas
        df = pd.DataFrame(gc.worksheet("DamageReports").get_all_records())
        st.write("Recent Damage Incidents")
        st.dataframe(df, use_container_width=True)

    elif task == "Asset Registry":
        asset_registry()
    elif task == "Damage Reporting":
        damage_reporting()
    elif task == "Cost Estimation":
        cost_estimation()
    elif task == "Admin Panel":
        if st.session_state['role'] == "Admin":
            admin_panel()
        else:
            st.error("Access Denied.")