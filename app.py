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

# --- 3. UI THEME & BLUE HEADER ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")

st.markdown("""
    <style>
    .main-header {
        background-color: #1E3A8A;
        padding: 25px;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
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
    menu = st.radio("Select Module", ["📊 Dashboard", "📝 Register New Asset", "🔎 Conditional Assessment", "🛠️ Maintenance Log"])
    st.divider()
    st.info("System: AAE-EMS v3.2")

# --- 4. DATA HANDLING & ERROR FIXING ---
sh = init_connection()
inv_ws = sh.worksheet("Inventory")
maint_ws = sh.worksheet("Maintenance")

# LOAD & STRIP HEADERS (Fixes KeyError)
df_inv = pd.DataFrame(inv_ws.get_all_records())
df_inv.columns = [c.strip() for c in df_inv.columns] 

df_maint = pd.DataFrame(maint_ws.get_all_records())
df_maint.columns = [c.strip() for c in df_maint.columns]

# Ensure Numeric Safety
num_cols = ['Total Value', 'Quantity', 'Current Life', 'Expected Life']
for col in num_cols:
    if col in df_inv.columns:
        df_inv[col] = pd.to_numeric(df_inv[col], errors='coerce').fillna(0)

# --- 5. MODULE LOGIC ---

# MODULE: DASHBOARD
if menu == "📊 Dashboard":
    if not df_inv.empty:
        m1, m2, m3, m4 = st.columns(4)
        total_val = df_inv['Total Value'].sum() if 'Total Value' in df_inv.columns else 0
        m1.metric("Enterprise Value", f"${total_val:,.0f}")
        
        health_pct = (len(df_inv[df_inv['Status']=='Functional']) / len(df_inv) * 100) if 'Status' in df_inv.columns else 0
        m2.metric("Operational Health", f"{health_pct:.1f}%")
        
        non_func = len(df_inv[df_inv['Status']=='Non-Functional']) if 'Status' in df_inv.columns else 0
        m3.metric("Critical Failures", non_func, delta="- Repairs Needed" if non_func > 0 else None, delta_color="inverse")
        
        # FIXED AGING CALCULATION
        aging = 0
        if 'Current Life' in df_inv.columns and 'Expected Life' in df_inv.columns:
            aging = len(df_inv[df_inv['Current Life'] >= df_inv['Expected Life']])
        m4.metric("Aging Alerts", aging)

        st.divider()
        st.subheader("📋 System Health Summary")
        summary = df_inv.groupby(['Category', 'Status'])['Quantity'].sum().unstack(fill_value=0)
        for s in ['Functional', 'Non-Functional']:
            if s not in summary.columns: summary[s] = 0
        summary['Total Qty'] = summary['Functional'] + summary['Non-Functional']
        summary['Health %'] = (summary['Functional'] / summary['Total Qty'] * 100).round(1)
        st.dataframe(summary.sort_values('Health %'), use_container_width=True)
    else:
        st.info("Registry is currently empty.")

# MODULE: REGISTER NEW ASSET
elif menu == "📝 Register New Asset":
    st.subheader("Asset Hardware Entry")
    cat_select = st.selectbox("Select Category", list(ASSET_CATEGORIES.keys()))
    sub_options = ASSET_CATEGORIES[cat_select]
    
    with st.form("reg_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        sub_select = c1.selectbox("Subsystem", sub_options)
        asset_code = c2.text_input("Asset Code")
        qty = c1.number_input("Quantity", min_value=1)
        u_cost = c2.number_input("Unit Cost", min_value=0.0)
        unit = c1.selectbox("Unit", ["Nos", "Set", "Units", "Meters"])
        e_life = c2.number_input("Expected Life (Yrs)", min_value=1)
        c_life = c1.number_input("Current Age (Yrs)", min_value=0)
        
        if st.form_submit_button("✅ Register Hardware"):
            inv_ws.append_row([cat_select, sub_select, asset_code, unit, qty, "Functional", u_cost, qty*u_cost, e_life, c_life])
            st.success("Asset recorded.")
            st.rerun()

# MODULE: CONDITIONAL ASSESSMENT (INTERACTIVE ROW SELECTION)
elif menu == "🔎 Conditional Assessment":
    st.subheader("Manual Status Update Dashboard")
    if not df_inv.empty:
        st.info("Directly select Functional or Non-Functional in the 'Status' column below, then click Save.")
        
        # Prepare Data Editor
        df_edit = df_inv[["Category", "Asset Name", "Asset Code", "Status"]].copy()
        edited_df = st.data_editor(
            df_edit,
            column_config={
                "Status": st.column_config.SelectboxColumn("Current Condition", options=["Functional", "Non-Functional"], required=True),
                "Category": st.column_config.Column(disabled=True),
                "Asset Name": st.column_config.Column(disabled=True),
                "Asset Code": st.column_config.Column(disabled=True),
            },
            hide_index=True,
            use_container_width=True
        )

        if st.button("💾 Save All Changes to Google Sheets"):
            with st.spinner("Updating Database..."):
                for index, row in edited_df.iterrows():
                    if row['Status'] != df_inv.iloc[index]['Status']:
                        inv_ws.update_cell(index + 2, 6, row['Status'])
                st.success("Updates successful!")
                st.rerun()
    else:
        st.warning("No assets registered.")

# MODULE: MAINTENANCE LOG
elif menu == "🛠️ Maintenance Log":
    st.subheader("Maintenance History")
    if not df_inv.empty:
        with st.form("m_form", clear_on_submit=True):
            m_code = st.selectbox("Asset Code", df_inv["Asset Code"].unique())
            m_cause = st.selectbox("Root Cause", ["Wear and Tear", "Power Surge", "Lack of Service", "Environmental", "Accidental"])
            m_desc = st.text_area("Details")
            m_cost = st.number_input("Repair Cost", min_value=0.0)
            if st.form_submit_button("💾 Save Record"):
                maint_ws.append_row([m_code, str(datetime.date.today()), m_cause, m_desc, m_cost])
                st.success("Log saved.")
                st.rerun()
































