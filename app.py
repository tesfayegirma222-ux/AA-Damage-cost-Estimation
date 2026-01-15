import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- 1. CONFIGURATION: ASSET CATEGORIES ---
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

# --- 3. UI THEME ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
st.markdown("""
    <style>
    .main-header { background-color: #1E3A8A; padding: 25px; border-radius: 12px; color: white; text-align: center; margin-bottom: 25px; }
    .stMetric { background-color: #ffffff; border-left: 5px solid #1E3A8A; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    <div class="main-header">
        <h1>Addis Ababa-Adama Expressway</h1>
        <p style='font-size: 1.2rem;'>Electromechanical Asset Management System</p>
    </div>
    """, unsafe_allow_html=True)

sh = init_connection()
inv_ws = sh.worksheet("Inventory")
maint_ws = sh.worksheet("Maintenance")

# --- 4. DATA HANDLING (FIXES KEYERROR & CONNECTS HEALTH) ---
def get_safe_data(worksheet):
    data = worksheet.get_all_values()
    if not data or len(data) < 1: return pd.DataFrame()
    
    # Clean headers to remove invisible spaces
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    
    # Ensure critical columns exist for the Health Chart
    req_cols = ['Category', 'Asset Name', 'Quantity', 'Functional Qty', 'Non-Functional Qty', 'Total Value']
    for col in req_cols:
        if col not in df.columns: df[col] = 0
            
    # Convert to numeric for calculation
    num_cols = ['Quantity', 'Functional Qty', 'Non-Functional Qty', 'Total Value', 'Unit Cost', 'Current Age', 'Expected Life']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

df_inv = get_safe_data(inv_ws)

# --- 5. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/highway.png", width=100)
    st.title("AAE-EMS Menu")
    menu = st.radio("Select Module", ["📊 Dashboard", "📝 Register New Asset", "🔎 Conditional Assessment", "🛠️ Maintenance Log"])

# --- 6. MODULE: DASHBOARD ---
if menu == "📊 Dashboard":
    if not df_inv.empty:
        # TOP METRICS
        m1, m2, m3, m4 = st.columns(4)
        total_q = df_inv['Quantity'].sum()
        func_q = df_inv['Functional Qty'].sum()
        health_pct = (func_q / total_q * 100) if total_q > 0 else 0
        
        m1.metric("Enterprise Value", f"${df_inv['Total Value'].sum():,.2f}")
        m2.metric("Operational Health", f"{health_pct:.1f}%")
        m3.metric("Broken Assets", int(df_inv['Non-Functional Qty'].sum()))
        m4.metric("Aging Alerts", len(df_inv[df_inv['Current Age'] >= df_inv['Expected Life']]))

        st.subheader("📊 System Health (Operational Status)")
        
        # AGGREGATE HEALTH PER CATEGORY (Connected to Assessment)
        cat_sum = df_inv.groupby('Category').agg({'Functional Qty': 'sum', 'Quantity': 'sum'}).reset_index()
        cat_sum['Health Status %'] = (cat_sum['Functional Qty'] / cat_sum['Quantity'].replace(0, 1) * 100).round(1)
        
        fig = px.bar(cat_sum.sort_values('Health Status %'), x='Health Status %', y='Category', 
                     orientation='h', range_x=[0, 100], text='Health Status %')
        fig.update_traces(marker_color='#22C55E', texttemplate='%{text}%', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Inventory is empty.")

# --- 7. MODULE: CONDITIONAL ASSESSMENT (FIXED TABLE & SAVE) ---
elif menu == "🔎 Conditional Assessment":
    st.subheader("🔎 Operational Status Assessment Table")
    st.info("Update Functional/Non-Functional counts below. Click Save to update the Dashboard Health Chart.")
    
    if not df_inv.empty:
        # Define the editable table view
        edit_cols = ["Category", "Asset Name", "Quantity", "Functional Qty", "Non-Functional Qty"]
        edited_df = st.data_editor(
            df_inv[edit_cols],
            column_config={
                "Category": st.column_config.Column(disabled=True),
                "Asset Name": st.column_config.Column(disabled=True),
                "Quantity": st.column_config.NumberColumn("Total Registered", disabled=True),
                "Functional Qty": st.column_config.NumberColumn("Functional ✅", min_value=0),
                "Non-Functional Qty": st.column_config.NumberColumn("Broken ❌", min_value=0),
            },
            hide_index=True, use_container_width=True, key="assess_table"
        )

        if st.button("💾 Save Assessment & Sync Dashboard"):
            with st.spinner("Pushing health data to Google Sheets..."):
                headers_clean = [h.strip() for h in inv_ws.row_values(1)]
                try:
                    idx_f = headers_clean.index("Functional Qty") + 1
                    idx_nf = headers_clean.index("Non-Functional Qty") + 1
                    idx_s = headers_clean.index("Status") + 1
                    
                    for i, row in edited_df.iterrows():
                        sheet_row = i + 2
                        f_val = int(row['Functional Qty'])
                        nf_val = int(row['Non-Functional Qty'])
                        status = "Functional" if f_val > 0 else "Non-Functional"
                        
                        inv_ws.update_cell(sheet_row, idx_f, f_val)
                        inv_ws.update_cell(sheet_row, idx_nf, nf_val)
                        inv_ws.update_cell(sheet_row, idx_s, status)
                        
                    st.success("✅ Records synced! Check Dashboard for live updates.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync Error: {e}")

# --- 8. MODULE: REGISTER NEW ASSET ---
elif menu == "📝 Register New Asset":
    st.subheader("📝 Register New Asset")
    cat_select = st.selectbox("Category", list(ASSET_CATEGORIES.keys()))
    with st.form("reg_form", clear_on_submit=True):
        sub_select = st.selectbox("Subsystem", ASSET_CATEGORIES[cat_select])
        c1, c2 = st.columns(2)
        qty = c1.number_input("Total Quantity", min_value=1)
        u_cost = c2.number_input("Unit Cost ($)", min_value=0.0)
        e_life = c1.number_input("Expected Life (Yrs)", min_value=1)
        c_age = c2.number_input("Current Age (Yrs)", min_value=0)
        if st.form_submit_button("✅ Register Hardware"):
            inv_ws.append_row([cat_select, sub_select, "", "Nos", qty, "Functional", u_cost, qty*u_cost, e_life, c_age, qty, 0])
            st.success("Asset recorded.")
            st.rerun()

# --- 9. MODULE: MAINTENANCE LOG ---
elif menu == "🛠️ Maintenance Log":
    st.subheader("🛠️ Log Maintenance Activity")
    m_cat = st.selectbox("Category", sorted(df_inv["Category"].unique()) if not df_inv.empty else [])
    with st.form("m_form", clear_on_submit=True):
        target = st.selectbox("Subsystem", df_inv[df_inv["Category"] == m_cat]["Asset Name"].unique() if not df_inv.empty else [])
        qty = st.number_input("Qty Fixed", min_value=1)
        cost = st.number_input("Repair Cost ($)", min_value=0.0)
        if st.form_submit_button("💾 Save Log"):
            maint_ws.append_row([m_cat, target, str(datetime.date.today()), qty, "Nos", "", "Repair", "Routine", cost])
            st.success("Log saved.")
            st.rerun()
































































