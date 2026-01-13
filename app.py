import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. SECURE CONNECTION LOGIC ---
def connect_gs():
    try:
        # Define the required scopes
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # This matches the [gcp_service_account] header in your Secrets
        if "gcp_service_account" in st.secrets:
            creds_info = dict(st.secrets["gcp_service_account"])
            
            # Clean the private key to handle newline issues
            if "private_key" in creds_info:
                creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
                
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
            client = gspread.authorize(creds)
            
            # Open the sheet - Ensure the name matches your Google Sheet exactly
            return client.open("Asset_Damage_System")
        else:
            return "MISSING_SECRETS"
    except Exception as e:
        return str(e)

# --- 2. INITIALIZE AND CHECK CONNECTION ---
gc_result = connect_gs()

if gc_result == "MISSING_SECRETS":
    st.error("⚠️ Secrets key '[gcp_service_account]' not found in Settings.")
    st.info("Go to App Settings > Secrets and paste your TOML credentials.")
    st.stop()
elif isinstance(gc_result, str):
    st.error(f"❌ Connection Error: {gc_result}")
    st.stop()
else:
    gc = gc_result # Connection successful

# --- 3. DATA LOADERS ---
def get_data(worksheet_name):
    ws = gc.worksheet(worksheet_name)
    return pd.DataFrame(ws.get_all_records())

# --- 4. APP INTERFACE ---
if 'logged_in' not in st.session_state:
    st.title("🛡️ Asset Damage System Login")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            users_df = get_data("Users")
            match = users_df[(users_df['Username'] == u) & (users_df['Password'] == str(p))]
            if not match.empty:
                st.session_state.logged_in = True
                st.session_state.user = u
                st.session_state.role = match.iloc[0]['Role']
                st.rerun()
            else:
                st.error("Invalid Username or Password")
else:
    # Sidebar Navigation
    st.sidebar.title(f"User: {st.session_state.user}")
    choice = st.sidebar.radio("Navigation", ["Dashboard", "Asset Registry", "Damage Reporting", "Cost Estimation"])

    if st.sidebar.button("Logout"):
        del st.session_state.logged_in
        st.rerun()

    # --- ROUTING ---
    if choice == "Dashboard":
        st.title("📊 Incident Dashboard")
        st.dataframe(get_data("DamageReports"), use_container_width=True)

    elif choice == "Asset Registry":
        st.title("🏗️ Asset Registry")
        df = get_data("AssetRegistry")
        st.dataframe(df, use_container_width=True)
        
        with st.expander("➕ Register New Asset"):
            with st.form("new_asset"):
                name = st.text_input("Asset Name")
                unit = st.selectbox("Unit", ["Meter", "Piece", "Set"])
                cost = st.number_input("Unit Cost", min_value=0.0)
                if st.form_submit_button("Save"):
                    gc.worksheet("AssetRegistry").append_row([len(df)+1, name, "Road", unit, cost])
                    st.success("Asset Saved!")
                    st.rerun()

    elif choice == "Damage Reporting":
        st.title("🚨 Damage Reporting")
        assets = get_data("AssetRegistry")['Asset Name'].tolist()
        with st.form("report"):
            case = st.text_input("Case Number")
            asset = st.selectbox("Asset", assets)
            loc = st.text_input("Location")
            if st.form_submit_button("Submit"):
                gc.worksheet("DamageReports").append_row([case, asset, loc, datetime.now().strftime("%Y-%m-%d"), st.session_state.user, "Pending"])
                st.success("Report Submitted!")

    elif choice == "Cost Estimation":
        st.title("💰 Engineering Estimation")
        reports = get_data("DamageReports")
        pending = reports[reports['Status'] == 'Pending']
        
        if pending.empty:
            st.info("No pending reports.")
        else:
            case = st.selectbox("Select Case", pending['Case No'].tolist())
            qty = st.number_input("Quantity Damaged", min_value=0.1)
            
            # Auto-Calculation
            asset_name = reports[reports['Case No'] == case]['Asset Name'].values[0]
            registry = get_data("AssetRegistry")
            u_cost = registry[registry['Asset Name'] == asset_name]['Unit Cost'].values[0]
            
            total = qty * u_cost
            vat = total * 0.15
            grand = total + vat
            
            st.metric("Grand Total (Incl. 15% VAT)", f"${grand:,.2f}")
            
            if st.button("Finalize and Upload"):
                gc.worksheet("Estimations").append_row([case, qty, total, vat, grand, st.session_state.user])
                ws = gc.worksheet("DamageReports")
                cell = ws.find(case)
                ws.update_cell(cell.row, 6, "Estimated") # Update Status
                st.success("Cloud Updated!")
                st.rerun()







