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
    "Automatic Voltage Regulator": ["AVR"],
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
        # Load from Streamlit Secrets
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    except Exception as e:
        st.error("GCP Service Account Secrets not found. Check your Streamlit Cloud settings.")
        st.stop()
    
    client = gspread.authorize(creds)
    
    if "SHEET_URL" in st.secrets:
        url = st.secrets["SHEET_URL"]
    else:
        st.warning("SHEET_URL not found in Secrets. Please add it to your Streamlit Cloud Secrets.")
        st.stop()
        
    return client.open_by_url(url)

# --- 3. DATA HANDLING ---
def get_worksheets(sh):
    # Inventory Sheet Logic
    try:
        inv_ws = sh.worksheet("Inventory")
    except:
        inv_ws = sh.add_worksheet(title="Inventory", rows="500", cols="10")
        inv_ws.append_row(["Category", "Asset Name", "Asset Code", "Unit", "Quantity", 
                           "Status", "Unit Cost", "Total Value", "Expected Life", "Current Life"])
    
    # Maintenance Sheet Logic
    try:
        maint_ws = sh.worksheet("Maintenance")
    except:
        maint_ws = sh.add_worksheet(title="Maintenance", rows="1000", cols="5")
        maint_ws.append_row(["Asset Code", "Date", "Root Cause", "Details", "Cost"])
        
    return inv_ws, maint_ws

# --- 4. UI SETUP ---
st.set_page_config(page_title="Electro-Mech Asset Pro", layout="wide")
st.title("🏗️ Electro-Mechanical Asset Management System")

# Initialize Connection
sh = init_connection()
inv_ws, maint_ws = get_worksheets(sh)

# Load DataFrames
df_inv = pd.DataFrame(inv_ws.get_all_records())
df_maint = pd.DataFrame(maint_ws.get_all_records())

tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📦 Register Asset", "🛠️ Maintenance Log"])

# --- TAB 1: DASHBOARD ---
with tab1:
    if not df_inv.empty:
        # KPI Metrics
        total_val = df_inv["Total Value"].sum()
        offline = len(df_inv[df_inv['Status'] == 'Non-Functional'])
        aging = len(df_inv[df_inv['Current Life'] >= df_inv['Expected Life']])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Enterprise Value", f"${total_val:,.2f}")
        c2.metric("Non-Functional Assets", offline, delta=f"{offline} repairs needed", delta_color="inverse")
        c3.metric("End-of-Life Alerts", aging, help="Assets reaching or exceeding expected service life")

        st.divider()
        
        # Charts
        col_left, col_right = st.columns(2)
        with col_left:
            # Horizontal Bar: Category Health
            fig_cat = px.bar(df_inv, y="Category", color="Status", orientation='h',
                             title="Asset Condition by Category",
                             color_discrete_map={"Functional": "#2ecc71", "Non-Functional": "#e74c3c"})
            st.plotly_chart(fig_cat, use_container_width=True)

        with col_right:
            # Vertical Bar: Subsystem Age
            fig_sub = px.bar(df_inv, x="Asset Name", y="Current Life", color="Category",
                             title="Subsystem Condition (Asset Age)",
                             labels={"Current Life": "Years in Service"})
            st.plotly_chart(fig_sub, use_container_width=True)

        # Root Cause Analysis (RCA)
        if not df_maint.empty:
            st.subheader("Root Cause Analysis (from Maintenance Records)")
            fig_rca = px.pie(df_maint, names='Root Cause', hole=0.4, 
                             color_discrete_sequence=px.colors.qualitative.Set3)
            st.plotly_chart(fig_rca, use_container_width=True)
    else:
        st.info("No records found. Please enter your first asset in the Register Asset tab.")

# --- TAB 2: REGISTER ASSET (DYNAMIC FILTERING) ---
with tab2:
    st.header("Asset Registration Form")
    
    # Dynamic Filtering Logic
    # We place Category selection outside the form so it triggers an instant rerun for the subsystem list
    selected_cat = st.selectbox("1. Select Main Category", list(ASSET_CATEGORIES.keys()))
    available_subsystems = ASSET_CATEGORIES[selected_cat]
    
    with st.form("registry_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        
        subsystem = col_a.selectbox("2. Select Subsystem", available_subsystems)
        asset_code = col_b.text_input("Asset Code (Unique ID)")
        
        unit = col_a.selectbox("Unit", ["Nos", "Set", "Units", "Meters"])
        qty = col_b.number_input("Total Quantity", min_value=1, step=1)
        
        u_cost = col_a.number_input("Unit Cost", min_value=0.0)
        exp_life = col_b.number_input("Expected Service Life (Years)", min_value=1)
        
        cur_life = col_a.number_input("Current Asset Life (Years)", min_value=0)
        status = col_b.radio("Status", ["Functional", "Non-Functional"], horizontal=True)
        
        if st.form_submit_button("Register Asset"):
            total_val = qty * u_cost
            inv_ws.append_row([selected_cat, subsystem, asset_code, unit, qty, 
                               status, u_cost, total_val, exp_life, cur_life])
            st.success(f"Registered {asset_code} successfully!")
            st.rerun()

# --- TAB 3: MAINTENANCE LOG ---
with tab3:
    st.header("Maintenance History Entry")
    if df_inv.empty:
        st.warning("Please add an asset in the Register tab before logging maintenance.")
    else:
        with st.form("maint_form", clear_on_submit=True):
            m_code = st.selectbox("Select Asset Code", df_inv["Asset Code"].unique())
            m_date = st.date_input("Maintenance Date")
            m_cause = st.selectbox("Root Cause Analysis", 
                                   ["Wear and Tear", "Power Surge", "Lack of Service", 
                                    "Environmental Factor", "Operational Error", "Accidental Damage"])
            m_detail = st.text_area("Work Performed Details")
            m_cost = st.number_input("Repair Cost", min_value=0.0)
            
            if st.form_submit_button("Submit Maintenance Log"):
                maint_ws.append_row([m_code, str(m_date), m_cause, m_detail, m_cost])
                st.success(f"Maintenance log for {m_code} saved.")
                st.rerun()
            





















