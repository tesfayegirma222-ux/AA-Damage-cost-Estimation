import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURATION: EXACT ASSET STRUCTURE ---
ASSET_CATEGORIES = {
    "Electric Power Source": ["Electric Utility", "Generator"],
    "Electric Power Distribution": ["ATS", "Breakers", "Power Cable", "Main Breakers", "DP"],
    "UPS System": ["UPS", "UPS Battery"],
    "CCTV System": ["Lane Camera", "Booth Camera", "Road Camera", "Plaza Camera"],
    "Auto-Railing System": ["Barrier Gate", "Controller"],
    "HVAC System": ["Air Conditioning System"],
    "Illumination System": ["High Mast Light", "Compound Light", "Road Light", "Booth Light", "Plaza Light"],
    "Electronic Display System": ["Canopy Light", "VMS", "LED Notice Board", "Fog Light", "Money Fee Display", "Passage Signal Lamp"],
    "Pump System": ["Surface Water Pump", "Submersible Pump"],
    "WIM System": ["Weight-In-Motion Sensor", "WIM Controller"]
}

# --- 2. AUTHENTICATION & CONNECTION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        # Priority 1: Check Streamlit Secrets (for Deployment)
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    except:
        # Priority 2: Check Local JSON (for development)
        creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
    
    client = gspread.authorize(creds)
    
    # URL PERSISTENCE: Get from secrets
    if "SHEET_URL" in st.secrets:
        url = st.secrets["SHEET_URL"]
    else:
        st.error("Please add SHEET_URL to your Streamlit Secrets.")
        st.stop()
        
    sh = client.open_by_url(url)
    return sh

# --- 3. TAB INITIALIZATION ---
def get_worksheets(sh):
    try:
        inv_ws = sh.worksheet("Inventory")
    except:
        inv_ws = sh.add_worksheet(title="Inventory", rows="100", cols="10")
        inv_ws.append_row(["Category", "Asset Name", "Asset Code", "Unit", "Quantity", 
                           "Status", "Unit Cost", "Total Value", "Expected Life", "Current Life"])
    
    try:
        maint_ws = sh.worksheet("Maintenance")
    except:
        maint_ws = sh.add_worksheet(title="Maintenance", rows="100", cols="5")
        maint_ws.append_row(["Asset Code", "Date", "Root Cause", "Details", "Cost"])
        
    return inv_ws, maint_ws

# --- 4. APP LAYOUT ---
st.set_page_config(page_title="Asset Manager Pro", layout="wide")
st.title("🚜 Electro-Mechanical Asset Inventory System")

sh = init_connection()
inv_ws, maint_ws = get_worksheets(sh)

# Load Data into DataFrames
df_inv = pd.DataFrame(inv_ws.get_all_records())
df_maint = pd.DataFrame(maint_ws.get_all_records())

tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "➕ Register Asset", "🛠️ Maintenance Log"])

# --- TAB 1: DASHBOARD ---
with tab1:
    if not df_inv.empty:
        # Key Metrics
        total_enterprise_value = df_inv["Total Value"].sum()
        non_functional = len(df_inv[df_inv['Status'] == 'Non-Functional'])
        
        # Calculate Life Alerts (Critical Assets)
        critical_assets = df_inv[df_inv['Current Life'] >= df_inv['Expected Life']]
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Enterprise Asset Value", f"${total_enterprise_value:,.2f}")
        m2.metric("Assets Offline", non_functional, delta="- Action Required" if non_functional > 0 else None, delta_color="inverse")
        m3.metric("Life Alerts", len(critical_assets), help="Assets that exceeded their expected service life")

        st.divider()
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            # Horizontal Bar: Condition by Category
            fig_cat = px.bar(df_inv, y="Category", color="Status", orientation='h',
                             title="Asset Condition by Category",
                             color_discrete_map={"Functional": "#2ecc71", "Non-Functional": "#e74c3c"})
            st.plotly_chart(fig_cat, use_container_width=True)

        with col_right:
            # Vertical Bar: Subsystem Condition (Age vs Asset Name)
            fig_sub = px.bar(df_inv, x="Asset Name", y="Current Life", color="Category",
                             title="Subsystem Age Distribution",
                             labels={"Current Life": "Years in Service"})
            st.plotly_chart(fig_sub, use_container_width=True)

        # Root Cause Analysis (RCA)
        if not df_maint.empty:
            st.subheader("Root Cause Analysis (Maintenance History)")
            fig_rca = px.pie(df_maint, names='Root Cause', hole=0.4, 
                             color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_rca, use_container_width=True)
    else:
        st.info("The inventory is empty. Start by registering assets in the 'Register Asset' tab.")

# --- TAB 2: REGISTER ASSET ---
with tab2:
    st.header("Asset Registry Form")
    with st.form("registry_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        
        category = c1.selectbox("Main System Category", list(ASSET_CATEGORIES.keys()))
        subsystem = c1.selectbox("Asset Name (Subsystem)", ASSET_CATEGORIES[category])
        asset_code = c2.text_input("Asset Code (e.g., CCTV-LANE-001)")
        unit = c2.selectbox("Unit", ["Nos", "Set", "Units", "Meters"])
        
        qty = c1.number_input("Total Quantity", min_value=1, step=1)
        u_cost = c2.number_input("Unit Cost", min_value=0.0)
        
        exp_life = c1.number_input("Expected Service Life (Years)", min_value=1)
        cur_life = c2.number_input("Current Asset Life (Years)", min_value=0)
        
        status = c1.radio("Functionality Status", ["Functional", "Non-Functional"], horizontal=True)
        
        if st.form_submit_button("Register Asset"):
            total_val = qty * u_cost
            inv_ws.append_row([category, subsystem, asset_code, unit, qty, status, u_cost, total_val, exp_life, cur_life])
            st.success(f"Asset {asset_code} successfully registered!")
            st.rerun()

# --- TAB 3: MAINTENANCE LOG ---
with tab3:
    st.header("Maintenance & Repair Log")
    if df_inv.empty:
        st.warning("Please add assets to the inventory first.")
    else:
        with st.form("maint_form", clear_on_submit=True):
            m_code = st.selectbox("Select Asset to Maintain", df_inv["Asset Code"].unique())
            m_date = st.date_input("Date of Maintenance")
            m_cause = st.selectbox("Root Cause Analysis", 
                                   ["Wear and Tear", "Power Surge", "Lack of Cleaning/Service", 
                                    "Environmental Impact", "Mechanical Failure", "Accidental Damage"])
            m_detail = st.text_area("Description of Work Performed")
            m_cost = st.number_input("Maintenance Cost", min_value=0.0)
            
            if st.form_submit_button("Log Maintenance Record"):
                maint_ws.append_row([m_code, str(m_date), m_cause, m_detail, m_cost])
                st.success("Maintenance entry recorded.")
                st.rerun()
            




















