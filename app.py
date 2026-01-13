import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. SECURE CONNECTION LOGIC ---
def connect_gs():
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        if "gcp_service_account" in st.secrets:
            creds_info = dict(st.secrets["gcp_service_account"])
            
            # Key cleaning for Streamlit formatting
            if "private_key" in creds_info:
                creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
            
            creds = Credentials.from_service_account_info(creds_info, scopes=scope)
            client = gspread.authorize(creds)
            
            # --- CRITICAL CHANGE: OPEN BY ID ---
            # Paste the long ID from your URL here
            # URL format: docs.google.com/spreadsheets/d/YOUR_ID_HERE/edit
            sheet_id = "YOUR_SPREADSHEET_ID_HERE" 
            return client.open_by_key(sheet_id)
        else:
            return "MISSING_SECRETS"
    except gspread.exceptions.SpreadsheetNotFound:
        return "ERROR: Spreadsheet not found. Did you share it with the service account email?"
    except gspread.exceptions.APIError as e:
        return f"ERROR: Google API Error. Is the Sheets API enabled? {e}"
    except Exception as e:
        return str(e)

# Initialize global connection
gc_result = connect_gs()

if gc_result == "MISSING_SECRETS":
    st.error("⚠️ Secrets key '[gcp_service_account]' not found in Settings.")
    st.stop()
elif isinstance(gc_result, str):
    st.error(f"❌ Connection Issue: {gc_result}")
    st.info("Check 1: Share the sheet with your Service Account email as Editor.")
    st.info("Check 2: Ensure Google Sheets & Drive APIs are 'Enabled' in Google Cloud Console.")
    st.stop()
else:
    gc = gc_result

# --- 2. DATA UTILITY ---
def get_data(worksheet_name):
    ws = gc.worksheet(worksheet_name)
    return pd.DataFrame(ws.get_all_records())

# --- 3. LOGIN & APP LOGIC ---
if 'logged_in' not in st.session_state:
    st.title("🛡️ Asset Damage Management")
    with st.form("login"):
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
    st.sidebar.title(f"User: {st.session_state.user}")
    choice = st.sidebar.radio("Navigation", ["Dashboard", "Asset Registry", "Damage Reporting", "Cost Estimation"])

    if st.sidebar.button("Logout"):
        del st.session_state.logged_in
        st.rerun()

    if choice == "Dashboard":
        st.header("📊 Incident Dashboard")
        st.dataframe(get_data("DamageReports"), use_container_width=True)

    elif choice == "Asset Registry":
        st.header("🏗️ Asset Inventory")
        df = get_data("AssetRegistry")
        st.dataframe(df, use_container_width=True)
        
        with st.expander("Register New Asset"):
            with st.form("new_asset"):
                name = st.text_input("Asset Name")
                unit = st.selectbox("Unit", ["Meter", "Piece", "Set"])
                cost = st.number_input("Unit Cost", min_value=0.0)
                if st.form_submit_button("Save"):
                    gc.worksheet("AssetRegistry").append_row([len(df)+1, name, "General", unit, cost])
                    st.success("Asset Saved!")
                    st.rerun()

    elif choice == "Damage Reporting":
        st.header("🚨 Incident Reporting")
        assets = get_data("AssetRegistry")['Asset Name'].tolist()
        with st.form("report"):
            case = st.text_input("Case Number")
            asset = st.selectbox("Damaged Asset", assets)
            loc = st.text_input("Location")
            if st.form_submit_button("Submit"):
                gc.worksheet("DamageReports").append_row([case, asset, loc, datetime.now().strftime("%Y-%m-%d"), st.session_state.user, "Pending"])
                st.success("Report Submitted!")

    elif choice == "Cost Estimation":
        st.header("💰 Engineering Cost Evaluation")
        reports = get_data("DamageReports")
        pending = reports[reports['Status'] == 'Pending']
        
        if pending.empty:
            st.info("No pending reports.")
        else:
            case = st.selectbox("Select Case", pending['Case No'].tolist())
            qty = st.number_input("Quantity Damaged", min_value=0.1)
            
            asset_name = reports[reports['Case No'] == case]['Asset Name'].values[0]
            reg = get_data("AssetRegistry")
            u_cost = reg[reg['Asset Name'] == asset_name]['Unit Cost'].values[0]
            
            total = qty * u_cost
            vat = total * 0.15
            grand = total + vat
            
            st.metric("Grand Total (Incl. 15% VAT)", f"${grand:,.2f}")
            
            if st.button("Finalize Estimation"):
                gc.worksheet("Estimations").append_row([case, qty, total, vat, grand, st.session_state.user])
                ws = gc.worksheet("DamageReports")
                cell = ws.find(case)
                ws.update_cell(cell.row, 6, "Estimated")
                st.success("Estimation Finalized!")
                st.rerun()











