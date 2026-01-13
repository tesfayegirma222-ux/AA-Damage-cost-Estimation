import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="Asset Damage System", layout="wide", page_icon="🏗️")

# --- GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def connect_gs():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # 1. Convert st.secrets to a regular dict (to avoid 'item assignment' error)
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # 2. Fix private key formatting
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        # 3. Authorize
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # 4. Open the workbook
        return client.open("Asset_Damage_System")
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

gc = connect_gs()

# Stop app if connection fails
if gc is None:
    st.info("💡 Please ensure the Service Account email is added as an 'Editor' to your Google Sheet.")
    st.stop()

# --- DATA HELPERS ---
def get_data(sheet_name):
    """Fetch data from a specific worksheet as a DataFrame."""
    try:
        ws = gc.worksheet(sheet_name)
        return pd.DataFrame(ws.get_all_records())
    except Exception as e:
        st.error(f"Error reading {sheet_name}: {e}")
        return pd.DataFrame()

# --- AUTHENTICATION ---
def login():
    st.sidebar.title("🔐 Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    
    if st.sidebar.button("Login"):
        users_df = get_data("Users")
        if not users_df.empty:
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
            # ID is set by counting rows
            ws.append_row([len(ws.get_all_values()), name, category, unit, cost])
            st.success(f"Asset '{name}' added successfully!")

def damage_reporting():
    st.header("🚨 Damage Reporting")
    assets_df = get_data("AssetRegistry")
    
    if assets_df.empty:
        st.warning("No assets found. Please register assets first.")
        return

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
            st.success(f"Report {case_no} submitted successfully.")

def cost_estimation():
    st.header("💰 Engineering Cost Estimation")
    reports_df = get_data("DamageReports")
    
    if reports_df.empty:
        st.info("No damage reports found.")
        return

    pending_cases = reports_df[reports_df['Status'] == 'Pending']['Case No'].tolist()
    
    if not pending_cases:
        st.info("No pending damage reports to estimate.")
        return

    case_select = st.selectbox("Select Case Number to Estimate", pending_cases)
    qty = st.number_input("Quantity Damaged", min_value=0.1, format="%.2f")
    
    # Auto-fetch Unit Cost from Registry
    asset_name = reports_df[reports_df['Case No'] == case_select]['Asset Name'].values[0]
    registry_df = get_data("AssetRegistry")
    unit_cost = registry_df[registry_df['Asset Name'] == asset_name]['Unit Cost'].values[0]
    
    subtotal = qty * unit_cost
    vat = subtotal * 0.15
    grand_total = subtotal + vat
    
    col1, col2 = st.columns(2)
    col1.metric("Unit Cost", f"${unit_cost:,.2f}")
    col2.metric("Total (Inc. VAT)", f"${grand_total:,.2f}")

    if st.button("Finalize and Save Estimation"):
        # Save to Estimations sheet
        ws_est = gc.worksheet("Estimations")
        ws_est.append_row([case_select, qty, subtotal, vat, grand_total, st.session_state['user'], "No"])
        
        # Update Status in DamageReports
        ws_rep = gc.worksheet("DamageReports")
        cell = ws_rep.find(str(case_select))
        ws_rep.update_cell(cell.row, 7, "Estimated") # Status is Column 7
        
        st.success("Estimation saved and Case Status updated!")
        st.cache_resource.clear() # Clear cache to refresh data

def admin_panel():
    st.header("👥 User Management")
    with st.expander("Add New User"):
        new_u = st.text_input("New Username")
        new_p = st.text_input("New Password")
        new_r = st.selectbox("Role", ["Admin", "Safety", "Engineer", "Manager"])
        if st.button("Create User"):
            gc.worksheet("Users").append_row([new_u, new_p, new_r])
            st.success(f"User {new_u} created.")
    
    st.subheader("Current Users")
    st.dataframe(get_data("Users"), use_container_width=True)

# --- MAIN NAVIGATION ---
if 'logged_in' not in st.session_state:
    login()
else:
    st.sidebar.info(f"👤 **{st.session_state['user']}** ({st.session_state['role']})")
    task = st.sidebar.radio("Go to:", ["Dashboard", "Asset Registry", "Damage Reporting", "Cost Estimation", "Admin Panel"])
    
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    if task == "Dashboard":
        st.title("📊 System Overview")
        df = get_data("DamageReports")
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.write("No data available yet.")

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
            st.error("Access Denied: Admins Only.")
            















