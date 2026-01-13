import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- 1. ASSET STRUCTURE CONFIGURATION ---
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

# --- 2. GOOGLE SHEETS CONNECTION ---
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

# --- 3. PROFESSIONAL UI & BLUE HEADER ---
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

# Sidebar Navigation Menu
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/highway.png", width=80)
    st.title("Main Menu")
    menu = st.radio("Select Module", [
        "📊 Dashboard", 
        "📝 Register New Asset", 
        "🔎 Conditional Assessment", 
        "🛠️ Maintenance Log"
    ])
    st.divider()
    st.info("Authorized Access Only")

# --- 4. DATA LOADING & CLEANING ---
sh = init_connection()
inv_ws = sh.worksheet("Inventory")
maint_ws = sh.worksheet("Maintenance")

df_inv = pd.DataFrame(inv_ws.get_all_records())
df_inv.columns = [c.strip() for c in df_inv.columns] # Defensive Header Cleaning

df_maint = pd.DataFrame(maint_ws.get_all_records())
df_maint.columns = [c.strip() for c in df_maint.columns]

# Ensure Numeric columns are safe for calculation
num_cols = ['Total Value', 'Quantity', 'Current Life', 'Expected Life']
for col in num_cols:
    if col in df_inv.columns:
        df_inv[col] = pd.to_numeric(df_inv[col], errors='coerce').fillna(0)

# --- 5. MODULE LOGIC ---

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    if not df_inv.empty:
        m1, m2, m3, m4 = st.columns(4)
        total_val = df_inv['Total Value'].sum() if 'Total Value' in df_inv.columns else 0
        m1.metric("Enterprise Value", f"${total_val:,.0f}")
        
        health_pct = (len(df_inv[df_inv['Status']=='Functional']) / len(df_inv) * 100) if 'Status' in df_inv.columns else 0
        m2.metric("Operational Health", f"{health_pct:.1f}%")
        
        non_func_count = len(df_inv[df_inv['Status']=='Non-Functional'])
        m3.metric("Critical Failures", non_func_count, delta="- Repairs Needed" if non_func_count > 0 else None, delta_color="inverse")
        
        aging = len(df_inv[df_inv['Current Life'] >= df_inv['Expected Life']]) if 'Current Life' in df_inv.columns else 0
        m4.metric("Aging Alerts", aging)

        st.divider()
        st.subheader("📋 System Health & Quantity Summary")
        
        summary = df_inv.groupby(['Category', 'Status'])['Quantity'].sum().unstack(fill_value=0)
        for s in ['Functional', 'Non-Functional']:
            if s not in summary.columns: summary[s] = 0
        summary['Total Qty'] = summary['Functional'] + summary['Non-Functional']
        summary['Health Score'] = (summary['Functional'] / summary['Total Qty'] * 100).round(1)
        
        st.dataframe(
            summary.sort_values('Health Score'),
            use_container_width=True,
            column_config={"Health Score": st.column_config.ProgressColumn("Health %", format="%.1f%%", min_value=0, max_value=100)}
        )
    else:
        st.info("Registry is currently empty.")

# --- REGISTER NEW ASSET ---
elif menu == "📝 Register New Asset":
    st.subheader("Hardware Registration Registry")
    cat_select = st.selectbox("1. Category", list(ASSET_CATEGORIES.keys()))
    sub_options = ASSET_CATEGORIES[cat_select]
    
    with st.form("reg_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        sub_select = c1.selectbox("2. Subsystem", sub_options)
        asset_code = c2.text_input("Asset Code (Unique ID)")
        qty = c1.number_input("Quantity", min_value=1)
        u_cost = c2.number_input("Unit Cost", min_value=0.0)
        unit = c1.selectbox("Unit", ["Nos", "Set", "Units", "Meters"])
        e_life = c2.number_input("Expected Life (Yrs)", min_value=1)
        c_life = c1.number_input("Current Age (Yrs)", min_value=0)
        
        if st.form_submit_button("✅ Register to Database"):
            # Initial Status is set to Functional automatically
            inv_ws.append_row([cat_select, sub_select, asset_code, unit, qty, "Functional", u_cost, qty*u_cost, e_life, c_life])
            st.success(f"Asset {asset_code} saved.")
            st.rerun()

# --- CONDITIONAL ASSESSMENT (MANUAL STATUS UPDATE) ---
elif menu == "🔎 Conditional Assessment":
    st.subheader("Manual Status Update Dashboard")
    if not df_inv.empty:
        # Top Update Form
        st.write("### ✍️ Change Asset Condition")
        search_code = st.selectbox("Select Asset Code", df_inv["Asset Code"].unique())
        asset_data = df_inv[df_inv["Asset Code"] == search_code].iloc[0]
        
        # Identity Card
        st.markdown(f"""
            <div style="background-color: #f0f4f8; padding: 15px; border-radius: 8px; border-left: 5px solid #1E3A8A;">
                <b>Category:</b> {asset_data['Category']} | <b>Subsystem:</b> {asset_data['Asset Name']}<br>
                <b>Current Status:</b> <span style="color: {'#10B981' if asset_data['Status'] == 'Functional' else '#EF4444'};">{asset_data['Status']}</span>
            </div>
        """, unsafe_allow_html=True)
        
        with st.form("status_update"):
            new_status = st.radio("Updated Functional Condition", ["Functional", "Non-Functional"], 
                                  index=0 if asset_data['Status'] == "Functional" else 1, horizontal=True)
            if st.form_submit_button("💾 Update Status in Sheets"):
                row_idx = df_inv.index[df_inv['Asset Code'] == search_code].tolist()[0] + 2
                inv_ws.update_cell(row_idx, 6, new_status) # Update Status Column
                st.success(f"Status for {search_code} updated to {new_status}!")
                st.rerun()

        st.divider()
        # Bottom Asset Table
        st.write("### 📋 Live Inventory Table")
        st.dataframe(df_inv[["Category", "Asset Name", "Asset Code", "Status", "Quantity"]], use_container_width=True, hide_index=True)
    else:
        st.warning("No assets registered.")

# --- MAINTENANCE LOG ---
elif menu == "🛠️ Maintenance Log":
    st.subheader("Asset Repair History")
    if not df_inv.empty:
        with st.form("m_form", clear_on_submit=True):
            m_code = st.selectbox("Asset Code", df_inv["Asset Code"].unique())
            m_cause = st.selectbox("Root Cause", ["Wear and Tear", "Power Surge", "Lack of Service", "Environmental", "Accidental"])
            m_desc = st.text_area("Details")
            m_cost = st.number_input("Repair Cost", min_value=0.0)
            if st.form_submit_button("💾 Save Maintenance Record"):
                maint_ws.append_row([m_code, str(datetime.date.today()), m_cause, m_desc, m_cost])
                st.success("Log recorded.")
                st.rerun()






























