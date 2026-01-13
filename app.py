import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. SECURE CONNECTION TO GOOGLE SHEETS ---
def get_gspread_client():
    # In Streamlit Cloud, store your JSON credentials in "Secrets"
    # In Local, you can use a file path
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    try:
        # Tries to load from Streamlit Secrets (for Cloud deployment)
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    except:
        # Fallback for local testing - replace with your filename
        creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
    
    return gspread.authorize(creds)

# --- 2. ASSET CATEGORIES DEFINITION ---
ASSET_STRUCTURE = {
    "Electric Power Source": ["Electric Utility", "Generator"],
    "Electric Power Distribution": ["ATS", "Breakers", "Power Cable", "Main Breakers", "DP"],
    "UPS System": ["UPS", "UPS Battery"],
    "CCTV System": ["Lane Camera", "Booth Camera", "Road Camera", "Plaza Camera"],
    "Auto-Railing System": ["Auto-Railing"],
    "Automatic Voltage Regulator": ["AVR"],
    "HVAC System": ["Air Conditioning System"],
    "Illumination System": ["High Mast Light", "Compound Light", "Road Light", "Booth Light", "Plaza Light"],
    "Electronic Display System": ["Canopy Light", "VMS", "LED Notice Board", "Fog Light", "Money Fee Display", "Passage Signal Lamp"],
    "Pump System": ["Surface Water Pump", "Submersible Pump"],
    "Weight-In-Motion (WIM)": ["WIM System"]
}

# --- 3. UI LAYOUT ---
st.set_page_config(page_title="EM Asset Manager", layout="wide")
st.title("⚡ Electro-Mechanical Asset Management")

# Sidebar for sheet selection
sheet_url = st.sidebar.text_input("Google Sheet URL", "Enter your Spreadsheet URL here")

if not sheet_url or "https" not in sheet_url:
    st.warning("Please enter a valid Google Sheet URL to begin.")
    st.stop()

# Load Data
client = get_gspread_client()
sh = client.open_by_url(sheet_url)
inventory_sheet = sh.get_worksheet(0) # First Tab: Inventory
maint_sheet = sh.get_worksheet(1)      # Second Tab: Maintenance

df_inv = pd.DataFrame(inventory_sheet.get_all_records())
df_maint = pd.DataFrame(maint_sheet.get_all_records())

tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📦 Inventory Entry", "🛠️ Maintenance Log"])

# --- TAB 1: DASHBOARD ---
with tab1:
    if not df_inv.empty:
        # Metrics
        total_val = df_inv['Total Asset Value'].sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("Enterprise Asset Value", f"${total_val:,.2f}")
        col2.metric("Total Assets", len(df_inv))
        col3.metric("Non-Functional", len(df_inv[df_inv['Status'] == 'Non-Functional']))

        st.divider()

        # Horizontal Bar: Asset Condition by Category
        fig_cond = px.bar(
            df_inv, 
            y="Category", 
            color="Status", 
            orientation='h',
            title="Asset Condition by Category",
            color_discrete_map={"Functional": "#2ecc71", "Non-Functional": "#e74c3c"}
        )
        st.plotly_chart(fig_cond, use_container_width=True)

        # Vertical Bar: Subsystem Life Status
        df_inv['Life Remaining'] = df_inv['Expected Service Life'] - df_inv['Current Asset Life']
        fig_life = px.bar(
            df_inv, 
            x="Asset Name", 
            y="Current Asset Life", 
            color="Category",
            title="Asset Age Distribution (Current Life)",
            text="Asset Code"
        )
        st.plotly_chart(fig_life, use_container_width=True)

        # Root Cause Analysis (RCA) from Maintenance Records
        if not df_maint.empty:
            st.subheader("Root Cause Analysis (from Maintenance Logs)")
            rca_counts = df_maint['Root Cause'].value_counts().reset_index()
            fig_rca = px.pie(rca_counts, values='count', names='Root Cause', hole=0.4)
            st.plotly_chart(fig_rca)
    else:
        st.info("No asset data found. Please add assets in the Inventory Entry tab.")

# --- TAB 2: INVENTORY ENTRY ---
with tab2:
    st.header("Register New Asset")
    with st.form("entry_form"):
        c1, c2 = st.columns(2)
        cat = c1.selectbox("Category", list(ASSET_STRUCTURE.keys()))
        sub = c1.selectbox("Asset Name (Subsystem)", ASSET_STRUCTURE[cat])
        code = c2.text_input("Asset Code")
        unit = c2.selectbox("Unit", ["Set", "Nos", "Meters", "Units"])
        
        qty = c1.number_input("Total Quantity", min_value=1)
        u_cost = c2.number_input("Unit Cost", min_value=0.0)
        status = c1.selectbox("Functionality Status", ["Functional", "Non-Functional"])
        
        exp_life = c2.number_input("Expected Service Life (Years)", min_value=1)
        cur_life = c1.number_input("Current Asset Life (Years)", min_value=0)

        if st.form_submit_button("Submit Asset"):
            new_row = [cat, sub, code, unit, qty, status, u_cost, qty*u_cost, exp_life, cur_life]
            inventory_sheet.append_row(new_row)
            st.success("Asset recorded!")
            st.rerun()

# --- TAB 3: MAINTENANCE LOG ---
with tab3:
    st.header("Log Maintenance Activity")
    with st.form("maint_form"):
        m_asset = st.selectbox("Select Asset Code", df_inv['Asset Code'].unique() if not df_inv.empty else ["None"])
        m_cause = st.selectbox("Root Cause of Issue", ["Wear & Tear", "Electrical Surge", "Vandalism", "Environmental Factors", "Operational Error"])
        m_details = st.text_area("Maintenance Details")
        m_cost = st.number_input("Maintenance Cost", min_value=0.0)
        
        if st.form_submit_button("Log Record"):
            maint_row = [m_asset, m_cause, m_details, m_cost]
            maint_sheet.append_row(maint_row)
            st.success("Maintenance history updated.")
            st.rerun()
            

















