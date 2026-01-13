import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="Asset Damage System", layout="wide")

# --- GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def connect_gs():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Pulling from st.secrets (Set this up in Streamlit Cloud Settings)
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        
        client = gspread.authorize(creds)
        return client.open("Asset_Damage_System")
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

gc = connect_gs()

# Stop execution if connection fails to prevent AttributeError
if gc is None:
    st.warning("Please configure your Google Sheets credentials in Streamlit Secrets.")
    st.stop()

# --- DATA HELPERS ---
def get_worksheet_data(sheet_name):
    ws = gc.worksheet(sheet_name)
    return pd.DataFrame(ws.get_all_records())

# --- AUTHENTICATION ---
def login():
    st.sidebar.title("🔐 Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    
    if st.sidebar.button("Login"):
        users_df = get_worksheet_data("Users")
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
    with st.form("asset_form", clear_on_submit=True):
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
    assets_df = get_worksheet_data("AssetRegistry")
    asset_list = assets_df['Asset Name'].tolist()
    
    with st.form("damage_form", clear_on_submit=True):
        case_no = st.text_input("Case Number (Reference)")
        asset_name = st.selectbox("Select Damaged Asset", asset_list)
        location = st.text_input("Location Details")
        gps = st.text_input("GPS Coordinates")
        date = st.date_input("Date of Incident")
        
        if st.form_submit_button("Submit Report"):
            ws = gc.worksheet("DamageReports")
            ws.append_row([case_no, asset_name, location, gps, str(date), st.session_state['user'], "Pending"])
            st.success("Report submitted successfully.")

def cost_estimation():
    st.header("💰 Engineering Cost Estimation")
    reports_df = get_worksheet_data("DamageReports")
    pending_cases = reports_df[reports_df['Status'] == 'Pending']['Case No'].tolist()
    
    if not pending_cases:
        st.info("No pending damage reports to estimate.")
        return

    case_select = st.selectbox("Select Case Number to Estimate", pending_cases)
    qty = st.number_input("Quantity Damaged", min_value=0.1)
    
    # Auto-fetch Unit Cost
    asset_name = reports_df[reports_df['Case No'] == case_select]['Asset Name'].values[0]
    registry_df = get_worksheet_data("AssetRegistry")
    unit_cost = registry_df[registry_df['Asset Name'] == asset_name]['Unit Cost'].values[0]
    
    subtotal = qty * unit_cost
    vat = subtotal * 0.15
    grand_total = subtotal + vat
    
    c1, c2 = st.columns(2)
    c1.metric("Unit Cost", f"${unit_cost:,.2f}")
    c2.metric("Grand Total (Incl. 15% VAT)", f"${grand_total:,.2f}")

    if st.button("Finalize and Save Estimation"):
        ws = gc.worksheet("Estimations")
        ws.append_row([case_select, qty, subtotal, vat, grand_total, st.session_state['user'], "No"])
        # Update status in DamageReports
        reports_ws = gc.worksheet("DamageReports")
        cell = reports_ws.find(case_select)
        reports_ws.update_cell(cell.row, 7, "Estimated") # Assuming 'Status' is column 7
        st.success("Estimation saved and status updated!")

def admin_panel():
    st.header("👥 User Management")
    with st.expander("Add New User"):
        new_u = st.text_input("New Username")
        new_p = st.text_input("New Password")
        new_r = st.selectbox("Role", ["Admin", "Safety", "Engineer", "Manager"])
        if st.button("Create User"):
            gc.worksheet("Users").append_row([new_u, new_p, new_r])
            st.success("User added.")
    
    users_df = get_worksheet_data("Users")
    st.dataframe(users_df)

# --- MAIN NAVIGATION ---
if 'logged_in' not in st.session_state:
    login()
else:
    st.sidebar.write(f"User: **{st.session_state['user']}** | Role: **{st.session_state['role']}**")
    task = st.sidebar.radio("Navigation", ["Dashboard", "Asset Registry", "Damage Reporting", "Cost Estimation", "Admin Panel"])
    
    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    if task == "Dashboard":
        st.title("📊 System Overview")
        df = get_worksheet_data("DamageReports")
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













