import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. SECURE CONNECTION LOGIC ---
def connect_gs():
    try:
        # Define the required scopes for both Sheets and Drive
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        if "gcp_service_account" in st.secrets:
            # 1. Convert the Secret object to a standard Python dictionary
            creds_info = dict(st.secrets["gcp_service_account"])
            
            # 2. FIX: The private_key often gets messed up when pasting into Streamlit
            # This line ensures it has the correct newline characters
            if "private_key" in creds_info:
                creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
            
            # 3. Create credentials from the dictionary
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
            
            # 4. Authorize and Open the Sheet
            client = gspread.authorize(creds)
            return client.open("Asset_Damage_System")
        else:
            st.error("⚠️ Secrets key '[gcp_service_account]' not found in Settings.")
            return None
    except Exception as e:
        # If we see <Response [200]>, this error block catches it
        st.error(f"❌ Connection Error: {e}")
        return None
        
        # Check for Secrets in Streamlit Cloud
        if "gcp_service_account" in st.secrets:
            # Convert Secrets to a standard dictionary
            creds_info = dict(st.secrets["gcp_service_account"])
            
            # CRITICAL: Fix the private key formatting (removes double backslashes)
            if "private_key" in creds_info:
                creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
            
            # Authenticate
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
            client = gspread.authorize(creds)
            
            # OPEN THE SHEET (Ensure the name matches EXACTLY)
            return client.open("Asset_Damage_System")
        else:
            st.error("⚠️ Secrets not found! Please paste your JSON in Settings > Secrets.")
            return None
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

# Initialize global connection
gc = connect_gs()

# Stop the app if connection fails
if gc is None:
    st.info("Check your Streamlit Secrets and Google Sheet sharing permissions.")
    st.stop()

# --- 2. DATA LOADERS ---
def get_data(worksheet_name):
    try:
        ws = gc.worksheet(worksheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error loading {worksheet_name}: {e}")
        return pd.DataFrame()

# --- 3. LOGIN & DASHBOARD ---
if 'logged_in' not in st.session_state:
    st.title("Road Asset Damage System")
    with st.form("login_panel"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            users_df = get_data("Users")
            if not users_df.empty:
                match = users_df[(users_df['Username'] == u) & (users_df['Password'] == str(p))]
                if not match.empty:
                    st.session_state.logged_in = True
                    st.session_state.user = u
                    st.session_state.role = match.iloc[0]['Role']
                    st.rerun()
                else:
                    st.error("Invalid Username or Password")
            else:
                st.error("User table is empty or inaccessible.")
else:
    # Sidebar Navigation
    st.sidebar.title(f"User: {st.session_state.user}")
    st.sidebar.write(f"Role: {st.session_state.role}")
    choice = st.sidebar.radio("Navigation", ["Dashboard", "Asset Registry", "Damage Reporting", "Cost Estimation"])

    if st.sidebar.button("Logout"):
        del st.session_state.logged_in
        st.rerun()

    # --- ROUTING ---
    if choice == "Dashboard":
        st.title("📊 Incident Dashboard")
        df = get_data("DamageReports")
        st.dataframe(df, use_container_width=True)

    elif choice == "Asset Registry":
        st.title("🏗️ Asset Registry")
        assets_df = get_data("AssetRegistry")
        st.dataframe(assets_df, use_container_width=True)
        
        with st.expander("Register New Asset"):
            with st.form("add_asset"):
                name = st.text_input("Asset Name")
                unit = st.selectbox("Unit", ["Meter", "Piece", "Set", "KM"])
                cost = st.number_input("Unit Cost", min_value=0.0)
                if st.form_submit_button("Save"):
                    gc.worksheet("AssetRegistry").append_row([len(assets_df)+1, name, "Road", unit, cost])
                    st.success("Asset Saved!")
                    st.rerun()

    elif choice == "Damage Reporting":
        st.title("🚨 Damage Reporting")
        assets_list = get_data("AssetRegistry")['Asset Name'].tolist()
        
        with st.form("report_form"):
            case_no = st.text_input("Case Number")
            asset_name = st.selectbox("Asset", assets_list)
            loc = st.text_input("Location (GPS/KM)")
            if st.form_submit_button("Submit"):
                gc.worksheet("DamageReports").append_row([
                    case_no, asset_name, loc, 
                    datetime.now().strftime("%Y-%m-%d"), 
                    st.session_state.user, "Pending"
                ])
                st.success("Report Submitted!")

    elif choice == "Cost Estimation":
        st.title("💰 Cost Estimation")
        reports = get_data("DamageReports")
        pending = reports[reports['Status'] == 'Pending']
        
        if pending.empty:
            st.info("No pending reports.")
        else:
            case = st.selectbox("Select Case", pending['Case No'].tolist())
            qty = st.number_input("Quantity Damaged", min_value=1.0)
            
            # Formula Logic
            asset_row = reports[reports['Case No'] == case].iloc[0]
            registry = get_data("AssetRegistry")
            unit_cost = registry[registry['Asset Name'] == asset_row['Asset Name']]['Unit Cost'].values[0]
            
            total = qty * unit_cost
            vat = total * 0.15
            grand = total + vat
            
            st.write(f"**Total (Excl VAT):** ${total:,.2f}")
            st.metric("Grand Total (Incl 15% VAT)", f"${grand:,.2f}")
            
            if st.button("Finalize and Update Cloud"):
                # Save to Estimations
                gc.worksheet("Estimations").append_row([case, qty, total, vat, grand, st.session_state.user])
                # Update Status in DamageReports
                ws = gc.worksheet("DamageReports")
                cell = ws.find(case)
                ws.update_cell(cell.row, 6, "Estimated") # Status Column
                st.success("Cloud Updated!")
                st.rerun()






