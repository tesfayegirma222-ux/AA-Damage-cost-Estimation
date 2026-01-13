import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- 1. CONFIGURATION: ASSET STRUCTURE ---
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

# --- 2. AUTH & CONNECTION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        url = st.secrets["SHEET_URL"]
        return client.open_by_url(url)
    except Exception as e:
        st.error(f"Configuration Error: {e}")
        st.stop()

# --- 3. THEMED UI SETUP ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")

# Custom CSS for Blue Header and Cards
st.markdown("""
    <style>
    .main-header {
        background-color: #1E3A8A;
        padding: 25px;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stMetric {
        background-color: #ffffff;
        border-left: 5px solid #1E3A8A;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
    <div class="main-header">
        <h1>Addis Ababa-Adama Expressway</h1>
        <p style='font-size: 1.2rem;'>Electromechanical Asset Management System</p>
    </div>
    """, unsafe_allow_html=True)

# Sidebar Navigation
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/highway.png", width=80)
    st.title("Main Menu")
    menu = st.radio(
        "Select Module",
        ["📊 Executive Dashboard", "🔎 Asset Browser", "📝 Register New Asset", "🛠️ Maintenance Log"]
    )
    st.divider()
    st.info("System: AAE-EMS v2.0")

# Load Data
sh = init_connection()
try:
    inv_ws = sh.worksheet("Inventory")
    maint_ws = sh.worksheet("Maintenance")
except Exception:
    st.error("Worksheets 'Inventory' or 'Maintenance' not found. Check Google Sheet tab names.")
    st.stop()

df_inv = pd.DataFrame(inv_ws.get_all_records())
df_maint = pd.DataFrame(maint_ws.get_all_records())

# --- 4. MODULE LOGIC ---

# MODULE 1: EXECUTIVE DASHBOARD
if menu == "📊 Executive Dashboard":
    if not df_inv.empty:
        # Defensive Data Cleaning (Fixes KeyError and Calculation Errors)
        for col in ['Total Value', 'Quantity', 'Current Life', 'Expected Life']:
            if col in df_inv.columns:
                df_inv[col] = pd.to_numeric(df_inv[col], errors='coerce').fillna(0)

        # KPI Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Enterprise Value", f"${df_inv['Total Value'].sum():,.0f}")
        
        health_pct = (len(df_inv[df_inv['Status']=='Functional']) / len(df_inv) * 100) if not df_inv.empty else 0
        m2.metric("Operational Health", f"{health_pct:.1f}%")
        
        non_func = len(df_inv[df_inv['Status']=='Non-Functional'])
        m3.metric("Critical Failures", non_func, delta="- Action Required" if non_func > 0 else None, delta_color="inverse")
        
        aging = len(df_inv[df_inv['Current Life'] >= df_inv['Expected Life']])
        m4.metric("Aging Alerts", aging)
        
        st.divider()
        col_left, col_right = st.columns(2)
        
        with col_left:
            fig1 = px.bar(df_inv, y="Category", color="Status", orientation='h', 
                          title="Asset Condition by Category",
                          color_discrete_map={"Functional": "#10B981", "Non-Functional": "#EF4444"})
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_right:
            fig2 = px.bar(df_inv, x="Asset Name", y="Current Life", color="Category", 
                          title="Asset Age Distribution (Years)")
            st.plotly_chart(fig2, use_container_width=True)
            
        if not df_maint.empty:
            st.subheader("Root Cause Analysis (Maintenance History)")
            fig3 = px.pie(df_maint, names='Root Cause', hole=0.4, 
                         color_discrete_sequence=px.colors.qualitative.Bold)
            st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Inventory is empty. Use the Register Asset module to add data.")

# MODULE 2: ASSET BROWSER
elif menu == "🔎 Asset Browser":
    st.subheader("Search & Export Inventory")
    search = st.text_input("🔍 Filter by any Keyword (Code, Name, Category, etc.)")
    if not df_inv.empty:
        mask = df_inv.apply(lambda row: search.lower() in str(row).lower(), axis=1)
        filtered_df = df_inv[mask]
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        st.download_button("📥 Export CSV", data=filtered_df.to_csv(index=False), file_name="AAE_Asset_Inventory.csv")

# MODULE 3: REGISTER NEW ASSET (DYNAMIC DROWPDOWN FIX)
elif menu == "📝 Register New Asset":
    st.subheader("Register New Electromechanical Asset")
    
    # 1. Selection outside form for instant rerun
    cat_select = st.selectbox("Select Main System Category", list(ASSET_CATEGORIES.keys()))
    sub_options = ASSET_CATEGORIES[cat_select]
    
    with st.form("registry_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        subsystem = c1.selectbox("Select Subsystem", sub_options)
        asset_code = c2.text_input("Asset Code (e.g., AAE-CCTV-101)")
        
        unit = c1.selectbox("Unit", ["Nos", "Set", "Units", "Meters"])
        qty = c2.number_input("Total Quantity", min_value=1, step=1)
        
        u_cost = c1.number_input("Unit Cost", min_value=0.0)
        status = c2.radio("Functionality Status", ["Functional", "Non-Functional"], horizontal=True)
        
        exp_life = c1.number_input("Expected Service Life (Years)", min_value=1)
        cur_life = c2.number_input("Current Asset Life (Years)", min_value=0)
        
        if st.form_submit_button("✅ Save Asset to Registry"):
            total_val = qty * u_cost
            inv_ws.append_row([cat_select, subsystem, asset_code, unit, qty, 
                               status, u_cost, total_val, exp_life, cur_life])
            st.success(f"Asset {asset_code} successfully added!")
            st.rerun()

# MODULE 4: MAINTENANCE LOG
elif menu == "🛠️ Maintenance Log":
    st.subheader("Record Maintenance Activity")
    if not df_inv.empty:
        with st.form("maint_entry", clear_on_submit=True):
            m_code = st.selectbox("Select Asset Code", df_inv["Asset Code"].unique())
            m_root = st.selectbox("Root Cause Analysis", ["Wear and Tear", "Power Surge", "Lack of Service", "Environmental", "Accidental"])
            m_desc = st.text_area("Details of Work Performed")
            m_val = st.number_input("Maintenance/Repair Cost", min_value=0.0)
            
            if st.form_submit_button("💾 Save Maintenance Record"):
                maint_ws.append_row([m_code, str(datetime.date.today()), m_root, m_desc, m_val])
                st.success(f"Record for {m_code} saved successfully.")
                st.rerun()
    else:
        st.warning("Please register assets before logging maintenance.")

























