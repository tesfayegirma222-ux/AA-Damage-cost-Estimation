import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. CONNECTION LOGIC (Using Secrets) ---
def connect_gs():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Pulling from Streamlit Cloud Secrets
        if "gcp_service_account" in st.secrets:
            creds_info = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
            client = gspread.authorize(creds)
            # Make sure the name matches your Google Sheet exactly
            return client.open("Asset_Damage_System")
        else:
            st.error("⚠️ Secrets not found! Paste your JSON in Streamlit Cloud Settings.")
            return None
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

# Initialize the connection globally
gc = connect_gs()

# CRITICAL: Stop the app if the connection fails to prevent AttributeError
if gc is None:
    st.info("Please configure your Google Sheet Secrets to continue.")
    st.stop()

# --- 2. DATA LOADERS ---
def get_data(worksheet_name):
    ws = gc.worksheet(worksheet_name)
    return pd.DataFrame(ws.get_all_records())

# --- 3. UI MODULES ---
def asset_registry():
    st.title("🏗️ Asset Registry")
    df = get_data("AssetRegistry")
    st.dataframe(df, use_container_width=True)
    
    with st.expander("Register New Asset"):
        with st.form("add_asset"):
            name = st.text_input("Asset Name")
            unit = st.selectbox("Unit", ["Meter", "Piece", "Set", "KM"])
            cost = st.number_input("Unit Cost", min_value=0.0)
            if st.form_submit_button("Save"):
                gc.worksheet("AssetRegistry").append_row([len(df)+1, name, "Road", unit, cost])
                st.success("Asset Saved!")
                st.rerun()

def damage_reporting():
    st.title("🚨 Damage Reporting")
    assets = get_data("AssetRegistry")['Asset Name'].tolist()
    
    with st.form("incident_report"):
        case = st.text_input("Case Number")
        asset = st.selectbox("Select Asset", assets)
        loc = st.text_input("Location/GPS")
        if st.form_submit_button("Submit Report"):
            gc.worksheet("DamageReports").append_row([case, asset, loc, datetime.now().strftime("%Y-%m-%d"), st.session_state.user, "Pending"])
            st.success("Report Submitted!")

def cost_estimation():
    st.title("💰 Engineering Estimation")
    reports = get_data("DamageReports")
    pending = reports[reports['Status'] == 'Pending']
    
    if pending.empty:
        st.info("No pending reports.")
    else:
        case = st.selectbox("Select Case", pending['Case No'].tolist())
        qty = st.number_input("Quantity Damaged", min_value=1.0)
        
        # Auto-Calculation Logic
        asset_name = reports[reports['Case No'] == case]['Asset Name'].values[0]
        registry = get_data("AssetRegistry")
        u_cost = registry[registry['Asset Name'] == asset_name]['Unit Cost'].values[0]
        
        total = qty * u_cost
        vat = total * 0.15
        grand = total + vat
        
        st.write(f"**Subtotal:** ${total:.2f} | **VAT (15%):** ${vat:.2f}")
        st.metric("Grand Total", f"${grand:.2f}")
        
        if st.button("Finalize Estimation"):
            gc.worksheet("Estimations").append_row([case, qty, total, vat, grand, st.session_state.user])
            # Update Status in DamageReports
            ws = gc.worksheet("DamageReports")
            cell = ws.find(case)
            ws.update_cell(cell.row, 6, "Estimated") # Status column
            st.success("Estimation Uploaded!")

# --- 4. LOGIN & MAIN APP ---
if 'logged_in' not in st.session_state:
    st.header("Login to Asset Damage System")
    user_input = st.text_input("Username")
    pass_input = st.text_input("Password", type="password")
    
    if st.button("Login"):
        users = get_data("Users")
        match = users[(users['Username'] == user_input) & (users['Password'] == str(pass_input))]
        if not match.empty:
            st.session_state.logged_in = True
            st.session_state.user = user_input
            st.session_state.role = match.iloc[0]['Role']
            st.rerun()
        else:
            st.error("Invalid Username or Password")
else:
    st.sidebar.title(f"User: {st.session_state.user}")
    choice = st.sidebar.radio("Navigation", ["Dashboard", "Asset Registry", "Damage Reporting", "Cost Estimation"])
    
    if st.sidebar.button("Logout"):
        del st.session_state.logged_in
        st.rerun()

    if choice == "Dashboard":
        st.write("### All Incident Reports")
        st.dataframe(get_data("DamageReports"), use_container_width=True)
    elif choice == "Asset Registry":
        asset_registry()
    elif choice == "Damage Reporting":
        damage_reporting()
    elif choice == "Cost Estimation":
        cost_estimation()
