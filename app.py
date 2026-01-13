import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. SETTINGS & ASSET STRUCTURE ---
ASSET_STRUCTURE = {
    "Electric Power Source": ["Electric Utility", "Generator"],
    "Electric Power Distribution": ["ATS", "Breakers", "Power Cable", "Main Breakers", "DP"],
    "UPS System": ["UPS", "UPS Battery"],
    "CCTV System": ["Lane Camera", "Booth Camera", "Road Camera", "Plaza Camera"],
    "Auto-Railing System": ["Auto-Railing"],
    "HVAC System": ["Air Conditioning System"],
    "Illumination System": ["High Mast Light", "Compound Light", "Road Light", "Booth Light", "Plaza Light"],
    "Electronic Display System": ["Canopy Light", "VMS", "LED Notice Board", "Fog Light", "Money Fee Display", "Passage Signal Lamp"],
    "Pump System": ["Surface Water Pump", "Submersible Pump"],
    "Weight-In-Motion (WIM)": ["WIM System"]
}

# --- 2. AUTHENTICATION ---
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    # Reads from Streamlit Secrets
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    except Exception as e:
        st.error("GCP Service Account Secrets not found!")
        st.stop()
    return gspread.authorize(creds)

# --- 3. SHEET INITIALIZATION ---
def get_worksheets(client, url):
    sh = client.open_by_url(url)
    
    # Get or Create Inventory Sheet
    try:
        inv_ws = sh.worksheet("Inventory")
    except:
        inv_ws = sh.add_worksheet(title="Inventory", rows="100", cols="10")
        inv_ws.append_row(["Category", "Asset Name", "Asset Code", "Unit", "Quantity", 
                           "Status", "Unit Cost", "Total Value", "Expected Life", "Current Life"])
    
    # Get or Create Maintenance Sheet
    try:
        maint_ws = sh.worksheet("Maintenance")
    except:
        maint_ws = sh.add_worksheet(title="Maintenance", rows="100", cols="5")
        maint_ws.append_row(["Asset Code", "Date", "Root Cause", "Details", "Cost"])
        
    return inv_ws, maint_ws

# --- 4. APP INTERFACE ---
st.set_page_config(page_title="Asset Manager", layout="wide")
st.title("🏗️ Electro-Mechanical Asset Management")

# Check for URL in Secrets, fallback to Sidebar
if "SHEET_URL" in st.secrets:
    sheet_url = st.secrets["SHEET_URL"]
else:
    sheet_url = st.sidebar.text_input("Spreadsheet URL", help="Add this to Secrets to hide this box.")

if not sheet_url:
    st.info("Please provide the Google Sheet URL in the sidebar or secrets.")
    st.stop()

# Load Data
client = get_gspread_client()
inventory_sheet, maint_sheet = get_worksheets(client, sheet_url)

df_inv = pd.DataFrame(inventory_sheet.get_all_records())
df_maint = pd.DataFrame(maint_sheet.get_all_records())

tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "➕ Add Asset", "🔧 Maintenance Log"])

# --- TAB 1: DASHBOARD ---
with tab1:
    if not df_inv.empty:
        # Key Metrics
        total_enterprise_value = df_inv["Total Value"].sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("Enterprise Asset Value", f"${total_enterprise_value:,.2f}")
        col2.metric("Total Assets", len(df_inv))
        col3.metric("Non-Functional", len(df_inv[df_inv['Status'] == 'Non-Functional']))
        
        st.divider()
        
        # Row 1: Condition and Lifecycle
        c1, c2 = st.columns(2)
        with c1:
            fig_cond = px.bar(df_inv, y="Category", color="Status", orientation='h', 
                             title="Asset Condition by Category",
                             color_discrete_map={"Functional": "#2ecc71", "Non-Functional": "#e74c3c"})
            st.plotly_chart(fig_cond, use_container_width=True)
            
        with c2:
            fig_life = px.bar(df_inv, x="Asset Name", y="Current Life", color="Category",
                             title="Subsystem Condition (Current Age vs Asset Name)")
            st.plotly_chart(fig_life, use_container_width=True)

        # Row 2: RCA
        if not df_maint.empty:
            st.subheader("Root Cause Analysis (Maintenance History)")
            fig_rca = px.pie(df_maint, names='Root Cause', hole=0.4, title="Dominant Failure Causes")
            st.plotly_chart(fig_rca)
    else:
        st.warning("No data found. Please add assets in the next tab.")

# --- TAB 2: INVENTORY ENTRY ---
with tab2:
    st.header("New Asset Registration")
    with st.form("asset_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        category = col_a.selectbox("Main System", list(ASSET_STRUCTURE.keys()))
        subsystem = col_a.selectbox("Subsystem", ASSET_STRUCTURE[category])
        code = col_b.text_input("Asset Code (Unique ID)")
        unit = col_b.selectbox("Unit", ["Nos", "Set", "Meters", "Units"])
        
        qty = col_a.number_input("Total Quantity", min_value=1, step=1)
        u_cost = col_b.number_input("Unit Cost", min_value=0.0)
        
        exp_life = col_a.number_input("Expected Service Life (Years)", min_value=1)
        cur_life = col_b.number_input("Current Asset Life (Years)", min_value=0)
        
        status = col_a.radio("Functionality Status", ["Functional", "Non-Functional"])
        
        if st.form_submit_button("Save Asset"):
            total_val = qty * u_cost
            new_row = [category, subsystem, code, unit, qty, status, u_cost, total_val, exp_life, cur_life]
            inventory_sheet.append_row(new_row)
            st.success(f"Asset {code} added successfully!")
            st.rerun()

# --- TAB 3: MAINTENANCE LOG ---
with tab3:
    st.header("Enter Maintenance Record")
    if df_inv.empty:
        st.error("Add assets first before logging maintenance.")
    else:
        with st.form("maint_form", clear_on_submit=True):
            m_code = st.selectbox("Select Asset Code", df_inv["Asset Code"].unique())
            m_date = st.date_input("Date of Work")
            m_cause = st.selectbox("Root Cause", ["Wear and Tear", "Power Surge", "Lack of Service", "Environmental", "Accidental", "Operational Error"])
            m_detail = st.text_area("Maintenance Details")
            m_cost = st.number_input("Maintenance Cost", min_value=0.0)
            
            if st.form_submit_button("Log Maintenance"):
                maint_row = [m_code, str(m_date), m_cause, m_detail, m_cost]
                maint_sheet.append_row(maint_row)
                st.success("Maintenance history updated!")
                st.rerun()
            



















