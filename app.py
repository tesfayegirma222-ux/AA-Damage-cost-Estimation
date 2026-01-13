import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURATION: EXPRESSWAY ASSET STRUCTURE ---
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

# --- 2. AUTHENTICATION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    except Exception:
        st.error("GCP Secrets not found. Please add 'gcp_service_account' to Streamlit Secrets.")
        st.stop()
    
    client = gspread.authorize(creds)
    
    if "SHEET_URL" in st.secrets:
        url = st.secrets["SHEET_URL"]
    else:
        st.error("SHEET_URL not found in Secrets.")
        st.stop()
        
    return client.open_by_url(url)

# --- 3. SHEET INITIALIZATION ---
def get_worksheets(sh):
    try:
        inv_ws = sh.worksheet("Inventory")
    except:
        inv_ws = sh.add_worksheet(title="Inventory", rows="1000", cols="10")
        inv_ws.append_row(["Category", "Asset Name", "Asset Code", "Unit", "Quantity", 
                           "Status", "Unit Cost", "Total Value", "Expected Life", "Current Life"])
    try:
        maint_ws = sh.worksheet("Maintenance")
    except:
        maint_ws = sh.add_worksheet(title="Maintenance", rows="1000", cols="5")
        maint_ws.append_row(["Asset Code", "Date", "Root Cause", "Details", "Cost"])
    return inv_ws, maint_ws

# --- 4. APP INTERFACE ---
st.set_page_config(page_title="AA-Adama Expressway Assets", layout="wide")

# Expressway Branding
st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>Addis Ababa-Adama Expressway</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center; color: #374151;'>Electromechanical Asset Management System</h3>", unsafe_allow_html=True)
st.divider()

# Load Data
sh = init_connection()
inv_ws, maint_ws = get_worksheets(sh)
df_inv = pd.DataFrame(inv_ws.get_all_records())
df_maint = pd.DataFrame(maint_ws.get_all_records())

tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📦 Asset Registry", "🛠️ Maintenance Log"])

# --- TAB 1: DASHBOARD ---
with tab1:
    if not df_inv.empty:
        # KPI Row
        c1, c2, c3, c4 = st.columns(4)
        total_value = df_inv["Total Value"].sum()
        non_func = len(df_inv[df_inv['Status'] == 'Non-Functional'])
        aging = len(df_inv[df_inv['Current Life'] >= df_inv['Expected Life']])
        
        c1.metric("Total Enterprise Value", f"${total_value:,.2f}")
        c2.metric("Total Assets", len(df_inv))
        c3.metric("Non-Functional", non_func, delta="- Repair Required" if non_func > 0 else None, delta_color="inverse")
        c4.metric("Aging Alerts", aging)

        st.divider()
        
        # Charts
        col_a, col_b = st.columns(2)
        with col_a:
            fig1 = px.bar(df_inv, y="Category", color="Status", orientation='h', 
                          title="Asset Condition by Category",
                          color_discrete_map={"Functional": "#10B981", "Non-Functional": "#EF4444"})
            st.plotly_chart(fig1, use_container_width=True)
        with col_b:
            fig2 = px.bar(df_inv, x="Asset Name", y="Current Life", color="Category", 
                          title="Subsystem Condition (Current Life in Years)")
            st.plotly_chart(fig2, use_container_width=True)

        if not df_maint.empty:
            st.subheader("Root Cause Analysis (Maintenance Trends)")
            fig3 = px.pie(df_maint, names='Root Cause', hole=0.4, color_discrete_sequence=px.colors.qualitative.Bold)
            st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Inventory is currently empty. Please register assets to view dashboard.")

# --- TAB 2: ASSET REGISTRY (DYNAMIC SUBSYSTEMS) ---
with tab2:
    st.subheader("New Asset Entry")
    
    # Selection logic outside the form for immediate reactivity
    cat_selection = st.selectbox("1. Select Main System Category", list(ASSET_CATEGORIES.keys()))
    sub_options = ASSET_CATEGORIES[cat_selection]
    
    with st.form("entry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        sub_selection = col1.selectbox("2. Select Subsystem", sub_options)
        asset_code = col2.text_input("Asset Code (e.g., AAE-CCTV-001)")
        
        unit = col1.selectbox("Unit", ["Nos", "Set", "Meters", "Units"])
        qty = col2.number_input("Total Quantity", min_value=1, step=1)
        
        u_cost = col1.number_input("Unit Cost", min_value=0.0)
        status = col2.radio("Status", ["Functional", "Non-Functional"], horizontal=True)
        
        e_life = col1.number_input("Expected Service Life (Years)", min_value=1)
        c_life = col2.number_input("Current Asset Life (Years)", min_value=0)
        
        if st.form_submit_button("Submit to Registry"):
            total_v = qty * u_cost
            inv_ws.append_row([cat_selection, sub_selection, asset_code, unit, qty, 
                               status, u_cost, total_v, e_life, c_life])
            st.success(f"Asset {asset_code} registered under {cat_selection}.")
            st.rerun()

# --- TAB 3: MAINTENANCE LOG ---
with tab3:
    st.subheader("Add Maintenance History")
    if not df_inv.empty:
        with st.form("maint_log", clear_on_submit=True):
            m_code = st.selectbox("Select Asset Code", df_inv["Asset Code"].unique())
            m_date = st.date_input("Maintenance Date")
            m_root = st.selectbox("Root Cause Analysis", ["Wear and Tear", "Power Surge", "Lack of Service", "Environmental", "Accidental"])
            m_desc = st.text_area("Maintenance Details")
            m_val = st.number_input("Cost of Repair", min_value=0.0)
            
            if st.form_submit_button("Save Maintenance Record"):
                maint_ws.append_row([m_code, str(m_date), m_root, m_desc, m_val])
                st.success("Record saved successfully.")
                st.rerun()
























