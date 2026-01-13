import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Asset Damage System", layout="wide")

# --- CLOUD CONNECTION ---
def connect_gs():
    if not os.path.exists("credentials.json"):
        st.error("Missing 'credentials.json' file.")
        return None
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    return client.open("Asset_Damage_System")

try:
    gc = connect_gs()
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {e}")
    st.stop()

# --- HELPER FUNCTIONS ---
def get_df(sheet_name):
    ws = gc.worksheet(sheet_name)
    return pd.DataFrame(ws.get_all_records())

# --- MODULE 1: ASSET REGISTRY ---
def asset_registry_module():
    st.subheader("📋 Road Asset Inventory")
    
    with st.expander("➕ Add New Asset Type"):
        with st.form("new_asset"):
            col1, col2 = st.columns(2)
            name = col1.text_input("Asset Name")
            cat = col1.selectbox("Category", ["Safety", "Civil", "Electrical", "Signage"])
            unit = col2.selectbox("Unit", ["Meter", "Set", "Piece", "Sq Meter"])
            cost = col2.number_input("Standard Unit Cost", min_value=0.0)
            
            if st.form_submit_button("Save Asset"):
                ws = gc.worksheet("AssetRegistry")
                ws.append_row([len(ws.get_all_values()), name, cat, unit, cost])
                st.success("Asset added to registry.")
                st.rerun()

    df = get_df("AssetRegistry")
    st.dataframe(df, use_container_width=True)

# --- MODULE 2: DAMAGE REPORTING ---
def damage_reporting_module():
    st.subheader("🚨 Incident Reporting (Safety Management)")
    
    assets_df = get_df("AssetRegistry")
    asset_list = assets_df['Asset Name'].tolist()

    with st.form("damage_report"):
        case_no = st.text_input("Case Number")
        selected_asset = st.selectbox("Damaged Asset", asset_list)
        location = st.text_input("Location / KM Reference")
        gps = st.text_input("GPS Coordinates")
        desc = st.text_area("Description of Damage")
        
        if st.form_submit_button("Submit Incident Report"):
            ws = gc.worksheet("DamageReports")
            ws.append_row([case_no, selected_asset, location, gps, desc, 
                           datetime.now().strftime("%Y-%m-%d %H:%M"), 
                           st.session_state['user'], "Pending"])
            st.success("Report Submitted to Asset Manager")

# --- MODULE 3: COST ESTIMATION ---
def cost_estimation_module():
    st.subheader("💰 Engineering Cost Estimation")
    
    reports_df = get_df("DamageReports")
    pending_reports = reports_df[reports_df['Status'] == 'Pending']
    
    if pending_reports.empty:
        st.info("No pending damage reports requiring estimation.")
        return

    case_no = st.selectbox("Select Pending Case", pending_reports['Case No'].tolist())
    
    # Auto-fetch Asset Data
    asset_name = pending_reports[pending_reports['Case No'] == case_no]['Asset Name'].values[0]
    assets_df = get_df("AssetRegistry")
    unit_cost = assets_df[assets_df['Asset Name'] == asset_name]['Unit Cost'].values[0]
    unit_type = assets_df[assets_df['Asset Name'] == asset_name]['Unit'].values[0]

    st.info(f"Asset: **{asset_name}** | Standard Cost: **${unit_cost}** per {unit_type}")

    with st.form("estimation_form"):
        qty = st.number_input(f"Quantity Damaged ({unit_type})", min_value=0.0)
        engineer = st.text_input("Engineer Name", value=st.session_state['user'])
        
        # Calculation Logic
        total_base = qty * unit_cost
        vat = total_base * 0.15
        grand_total = total_base + vat
        
        if st.form_submit_button("Calculate & Submit"):
            # 1. Add to Estimation Sheet
            est_ws = gc.worksheet("Estimations")
            est_ws.append_row([case_no, qty, total_base, vat, grand_total, engineer, datetime.now().strftime("%Y-%m-%d")])
            
            # 2. Update Status in DamageReports
            reports_ws = gc.worksheet("DamageReports")
            cell = reports_ws.find(case_no)
            reports_ws.update_cell(cell.row, 8, "Estimated") # Column 8 is 'Status'
            
            st.success(f"Estimation Complete! Grand Total: ${grand_total:,.2f}")
            st.rerun()

# --- LOGIN SYSTEM ---
if 'logged_in' not in st.session_state:
    st.title("Road Asset Damage System")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            user_df = get_df("Users")
            match = user_df[(user_df['Username'] == u) & (user_df['Password'] == str(p))]
            if not match.empty:
                st.session_state['logged_in'] = True
                st.session_state['user'] = u
                st.session_state['role'] = match.iloc[0]['Role']
                st.rerun()
            else:
                st.error("Invalid credentials")
else:
    # --- SIDEBAR NAVIGATION ---
    st.sidebar.title(f"Welcome, {st.session_state['user']}")
    st.sidebar.write(f"Role: **{st.session_state['role']}**")
    
    menu = ["Dashboard", "Asset Registry", "Damage Reporting", "Cost Estimation"]
    if st.session_state['role'] == "Admin":
        menu.append("User Management")
    
    choice = st.sidebar.radio("Go to", menu)
    
    if st.sidebar.button("Logout"):
        del st.session_state['logged_in']
        st.rerun()

    # --- ROUTING ---
    if choice == "Dashboard":
        st.title("📊 Operational Dashboard")
        df = get_df("DamageReports")
        st.dataframe(df, use_container_width=True)
        
    elif choice == "Asset Registry":
        asset_registry_module()
        
    elif choice == "Damage Reporting":
        damage_reporting_module()
        
    elif choice == "Cost Estimation":
        cost_estimation_module()
        
    elif choice == "User Management":
        st.subheader("👥 System Users")
        st.dataframe(get_df("Users"))
