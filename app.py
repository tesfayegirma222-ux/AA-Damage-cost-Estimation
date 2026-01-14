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
    st.info("System: AAE-EMS v4.5")

# --- 4. DATA HANDLING & SAFE HEADER STRIP ---
sh = init_connection()
inv_ws = sh.worksheet("Inventory")
maint_ws = sh.worksheet("Maintenance")

# Load Inventory & Maintenance with Safe Strip
df_inv = pd.DataFrame(inv_ws.get_all_records())
df_inv.columns = [str(c).strip() for c in df_inv.columns] 

df_maint = pd.DataFrame(maint_ws.get_all_records())
df_maint.columns = [str(c).strip() for c in df_maint.columns]

# Numeric Safety & Logic for Quantities
num_cols = ['Total Value', 'Quantity', 'Current Life', 'Expected Life', 'Functional Qty', 'Non-Functional Qty']
for col in num_cols:
    if col in df_inv.columns:
        df_inv[col] = pd.to_numeric(df_inv[col], errors='coerce').fillna(0)
    elif col in ['Functional Qty', 'Non-Functional Qty']:
        # Default initialization if columns don't exist in Sheet yet
        df_inv[col] = df_inv.apply(lambda x: x['Quantity'] if x['Status'] == 'Functional' and col == 'Functional Qty' else 0, axis=1)

# --- 5. MODULE LOGIC ---

# MODULE: DASHBOARD
if menu == "📊 Dashboard":
    if not df_inv.empty:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Enterprise Value", f"${df_inv['Total Value'].sum():,.0f}")
        
        # Health calculation based on quantity ratio
        total_q = df_inv['Quantity'].sum()
        func_q = df_inv['Functional Qty'].sum() if 'Functional Qty' in df_inv.columns else 0
        health_pct = (func_q / total_q * 100) if total_q > 0 else 0
        
        m2.metric("Operational Health", f"{health_pct:.1f}%")
        m3.metric("Critical Failures", int(df_inv['Non-Functional Qty'].sum()), delta_color="inverse")
        
        aging = len(df_inv[df_inv['Current Life'] >= df_inv['Expected Life']]) if 'Current Life' in df_inv.columns else 0
        m4.metric("Aging Alerts", aging)

        st.divider()
        st.subheader("📊 System Health Visualization")
        
        summary = df_inv.groupby(['Category', 'Asset Name']).agg({'Functional Qty': 'sum', 'Quantity': 'sum'}).reset_index()
        summary['Health %'] = (summary['Functional Qty'] / summary['Quantity'] * 100).round(1)
        summary['Display Name'] = summary['Category'] + " - " + summary['Asset Name']

        fig = px.bar(summary.sort_values('Health %'), x='Health %', y='Display Name', orientation='h',
                     color='Health %', color_continuous_scale='RdYlGn', range_x=[0, 100], text='Health %')
        fig.update_layout(height=max(400, len(summary)*30), margin=dict(l=20, r=20, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

# MODULE: REGISTER NEW ASSET
elif menu == "📝 Register New Asset":
    st.subheader("Asset Registration")
    cat_select = st.selectbox("Category", list(ASSET_CATEGORIES.keys()))
    sub_options = ASSET_CATEGORIES[cat_select]
    with st.form("reg_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        sub_select = c1.selectbox("Subsystem", sub_options)
        asset_code = c2.text_input("Asset Code")
        qty = c1.number_input("Total Quantity", min_value=1)
        u_cost = c2.number_input("Unit Cost", min_value=0.0)
        unit = c1.selectbox("Unit", ["Nos", "Set", "Units", "Meters"])
        e_life = c2.number_input("Expected Life (Yrs)", min_value=1)
        c_life = c1.number_input("Current Age (Yrs)", min_value=0)
        
        if st.form_submit_button("✅ Register Hardware"):
            # New registration defaults all to Functional
            inv_ws.append_row([cat_select, sub_select, asset_code, unit, qty, "Functional", u_cost, qty*u_cost, e_life, c_life, qty, 0])
            st.success("Asset registered.")
            st.rerun()

# MODULE: CONDITIONAL ASSESSMENT (QUANTITY EDITING)
elif menu == "🔎 Conditional Assessment":
    st.subheader("Manual Quantity Assessment")
    if not df_inv.empty:
        st.info("Edit **Functional** and **Non-Functional** counts. The system tracks the **Total Registered** for reference.")
        
        df_edit = df_inv[["Category", "Asset Name", "Asset Code", "Quantity", "Functional Qty", "Non-Functional Qty"]].copy()
        
        edited_df = st.data_editor(
            df_edit,
            column_config={
                "Quantity": st.column_config.NumberColumn("Total Registered", disabled=True),
                "Functional Qty": st.column_config.NumberColumn("Functional ✅", min_value=0, step=1),
                "Non-Functional Qty": st.column_config.NumberColumn("Non-Functional ❌", min_value=0, step=1),
                "Category": st.column_config.Column(disabled=True),
                "Asset Name": st.column_config.Column(disabled=True),
                "Asset Code": st.column_config.Column(disabled=True),
            },
            hide_index=True, use_container_width=True
        )

        if st.button("💾 Save All Changes"):
            with st.spinner("Updating Database..."):
                for index, row in edited_df.iterrows():
                    orig = df_inv.iloc[index]
                    if row['Functional Qty'] != orig['Functional Qty'] or row['Non-Functional Qty'] != orig['Non-Functional Qty']:
                        row_idx = index + 2
                        new_status = "Functional" if row['Functional Qty'] > 0 else "Non-Functional"
                        # Update Status, Functional Qty, and Non-Functional Qty columns
                        inv_ws.update_cell(row_idx, 6, new_status) # Status
                        inv_ws.update_cell(row_idx, 11, int(row['Functional Qty'])) # Column K
                        inv_ws.update_cell(row_idx, 12, int(row['Non-Functional Qty'])) # Column L
                st.success("Updates successful!")
                st.rerun()

# MODULE: MAINTENANCE LOG
elif menu == "🛠️ Maintenance Log":
    st.subheader("Maintenance Entry")
    if not df_inv.empty:
        with st.form("m_form", clear_on_submit=True):
            m_code = st.selectbox("Asset Code", df_inv["Asset Code"].unique())
            m_cause = st.selectbox("Root Cause", ["Wear and Tear", "Power Surge", "Lack of Service", "Environmental", "Accidental"])
            m_desc = st.text_area("Details")
            m_cost = st.number_input("Repair Cost", min_value=0.0)
            if st.form_submit_button("💾 Save Record"):
                maint_ws.append_row([m_code, str(datetime.date.today()), m_cause, m_desc, m_cost])
                st.success("Log recorded.")
                st.rerun()





































