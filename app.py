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
    logo_url = "https://img.icons8.com/fluency/96/highway.png" 
    st.image(logo_url, width=120)
    st.title("Main Menu")
    menu = st.radio("Select Module", ["📊 Dashboard", "📝 Register New Asset", "🔎 Conditional Assessment", "🛠️ Maintenance Log"])
    st.divider()
    st.caption("Addis Ababa-Adama Expressway")
    st.info("System: AAE-EMS v6.5")

# --- 4. DATA HANDLING & CRASH PREVENTION ---
sh = init_connection()
inv_ws = sh.worksheet("Inventory")
maint_ws = sh.worksheet("Maintenance")

def get_safe_data(worksheet):
    """Prevents GSpreadException by validating data presence before processing"""
    data = worksheet.get_all_values()
    if not data:
        return pd.DataFrame()
    headers = [str(h).strip() for h in data[0]]
    if len(data) > 1:
        return pd.DataFrame(data[1:], columns=headers)
    return pd.DataFrame(columns=headers)

# Load Data
df_inv = get_safe_data(inv_ws)
df_maint = get_safe_data(maint_ws)

# Numeric Safety & Dynamic Column Initialization
num_cols = ['Total Value', 'Quantity', 'Current Life', 'Expected Life', 'Functional Qty', 'Non-Functional Qty']
for col in num_cols:
    if col in df_inv.columns:
        df_inv[col] = pd.to_numeric(df_inv[col], errors='coerce').fillna(0)
    elif col in ['Functional Qty', 'Non-Functional Qty'] and not df_inv.empty:
        df_inv[col] = df_inv.apply(lambda x: pd.to_numeric(x['Quantity'], errors='coerce') if x['Status'] == 'Functional' and col == 'Functional Qty' else 0, axis=1)

# --- 5. MODULE LOGIC ---

# MODULE: DASHBOARD
if menu == "📊 Dashboard":
    if not df_inv.empty:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Enterprise Value", f"${df_inv['Total Value'].sum():,.0f}")
        total_q = df_inv['Quantity'].sum()
        func_q = df_inv['Functional Qty'].sum() if 'Functional Qty' in df_inv.columns else 0
        health_pct = (func_q / total_q * 100) if total_q > 0 else 0
        m2.metric("Operational Health", f"{health_pct:.1f}%")
        m3.metric("Critical Failures", int(df_inv['Non-Functional Qty'].sum()), delta_color="inverse")
        aging = len(df_inv[df_inv['Current Life'] >= df_inv['Expected Life']]) if 'Current Life' in df_inv.columns else 0
        m4.metric("Aging Alerts", aging)

        st.divider()
        st.subheader("📊 System Health by Category")
        cat_summary = df_inv.groupby('Category').agg({'Functional Qty': 'sum', 'Quantity': 'sum'}).reset_index()
        cat_summary['Health %'] = (cat_summary['Functional Qty'] / cat_summary['Quantity'] * 100).round(1)

        fig = px.bar(cat_summary.sort_values('Health %'), x='Health %', y='Category', orientation='h',
                     color='Health %', color_continuous_scale='RdYlGn', range_x=[0, 100], text='Health %')
        fig.update_layout(height=400, margin=dict(l=20, r=20, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("🔍 View Subsystem Details"):
            st.dataframe(df_inv[['Category', 'Asset Name', 'Quantity', 'Functional Qty', 'Non-Functional Qty']], use_container_width=True)
    else:
        st.info("Inventory is empty.")

# MODULE: REGISTER NEW ASSET
elif menu == "📝 Register New Asset":
    st.subheader("Asset Registration")
    cat_select = st.selectbox("Category", list(ASSET_CATEGORIES.keys()))
    sub_options = ASSET_CATEGORIES[cat_select]
    with st.form("reg_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        sub_select = c1.selectbox("Subsystem", sub_options)
        qty = c1.number_input("Total Quantity", min_value=1)
        u_cost = c2.number_input("Unit Cost", min_value=0.0)
        unit = c1.selectbox("Unit", ["Nos", "Set", "Units", "Meters"])
        e_life = c1.number_input("Expected Life (Yrs)", min_value=1)
        c_life = c2.number_input("Current Age (Yrs)", min_value=0)
        if st.form_submit_button("✅ Register Hardware"):
            inv_ws.append_row([cat_select, sub_select, "", unit, qty, "Functional", u_cost, qty*u_cost, e_life, c_life, qty, 0])
            st.success("Asset recorded.")
            st.rerun()

# MODULE: CONDITIONAL ASSESSMENT
elif menu == "🔎 Conditional Assessment":
    st.subheader("Quantity Assessment")
    if not df_inv.empty:
        df_edit = df_inv[["Category", "Asset Name", "Quantity", "Functional Qty", "Non-Functional Qty"]].copy()
        edited_df = st.data_editor(df_edit, column_config={
                "Quantity": st.column_config.NumberColumn("Total", disabled=True),
                "Functional Qty": st.column_config.NumberColumn("Functional ✅", min_value=0),
                "Non-Functional Qty": st.column_config.NumberColumn("Non-Functional ❌", min_value=0),
                "Category": st.column_config.Column(disabled=True), "Asset Name": st.column_config.Column(disabled=True),
            }, hide_index=True, use_container_width=True)
        if st.button("💾 Save All Changes"):
            for index, row in edited_df.iterrows():
                row_idx = index + 2
                new_status = "Functional" if row['Functional Qty'] > 0 else "Non-Functional"
                inv_ws.update_cell(row_idx, 6, new_status)
                inv_ws.update_cell(row_idx, 11, int(row['Functional Qty']))
                inv_ws.update_cell(row_idx, 12, int(row['Non-Functional Qty']))
            st.success("Synced!")
            st.rerun()

# MODULE: MAINTENANCE LOG
elif menu == "🛠️ Maintenance Log":
    st.subheader("🛠️ Log Maintenance")
    if not df_inv.empty:
        m_cat = st.selectbox("Category Filter", sorted(df_inv["Category"].unique()))
        filtered_sub = df_inv[df_inv["Category"] == m_cat]["Asset Name"].unique()
        with st.form("m_form", clear_on_submit=True):
            m_target = st.selectbox("Subsystem", filtered_sub)
            c1, c2, c3 = st.columns(3)
            m_qty = c1.number_input("Qty", min_value=1)
            m_unit = c2.selectbox("Unit", ["Nos", "Set", "Units", "Meters"])
            m_loc = c3.text_input("Location (KM)")
            m_cause = st.selectbox("Cause", ["Wear and Tear", "Power Surge", "Lack of Service", "Environmental", "Accidental"])
            m_desc = st.text_area("Description")
            m_cost = st.number_input("Cost", min_value=0.0)
            if st.form_submit_button("💾 Save"):
                maint_ws.append_row([m_cat, m_target, str(datetime.date.today()), m_qty, m_unit, m_loc, m_cause, m_desc, m_cost])
                st.success("Log saved.")
                st.rerun()


















































