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

# Sidebar
with st.sidebar:
    logo_url = "https://img.icons8.com/fluency/96/highway.png" 
    st.image(logo_url, width=120)
    st.title("Main Menu")
    menu = st.radio("Select Module", ["📊 Dashboard", "📝 Register New Asset", "🔎 Conditional Assessment", "🛠️ Maintenance Log"])
    st.divider()
    st.info("System: AAE-EMS v8.0")

# --- 4. DATA HANDLING ---
sh = init_connection()
inv_ws = sh.worksheet("Inventory")
maint_ws = sh.worksheet("Maintenance")

def get_safe_data(worksheet):
    data = worksheet.get_all_values()
    if not data: return pd.DataFrame()
    headers = [str(h).strip() for h in data[0]]
    return pd.DataFrame(data[1:], columns=headers) if len(data) > 1 else pd.DataFrame(columns=headers)

df_inv = get_safe_data(inv_ws)

# Numeric Cleaning
num_cols = ['Quantity', 'Unit Cost', 'Total Value', 'Expected Life', 'Current Age', 'Functional Qty', 'Non-Functional Qty']
for col in num_cols:
    if col in df_inv.columns:
        df_inv[col] = pd.to_numeric(df_inv[col], errors='coerce').fillna(0)

# --- 5. MODULE LOGIC ---

# DASHBOARD
if menu == "📊 Dashboard":
    if not df_inv.empty:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Enterprise Value", f"${df_inv['Total Value'].sum():,.2f}")
        
        total_q = df_inv['Quantity'].sum()
        func_q = df_inv['Functional Qty'].sum()
        health_pct = (func_q / total_q * 100) if total_q > 0 else 0
        m2.metric("Operational Health", f"{health_pct:.1f}%")
        
        m3.metric("Critical Failures", int(df_inv['Non-Functional Qty'].sum()), delta_color="inverse")
        
        aging_count = len(df_inv[df_inv['Current Age'] >= df_inv['Expected Life']])
        m4.metric("Aging Alerts", aging_count)

        st.divider()
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("📊 Asset Health by Category")
            cat_health = df_inv.groupby('Category').agg({'Functional Qty': 'sum', 'Quantity': 'sum'}).reset_index()
            cat_health['Health %'] = (cat_health['Functional Qty'] / cat_health['Quantity'] * 100).round(1)
            fig_h = px.bar(cat_health.sort_values('Health %'), x='Health %', y='Category', orientation='h', range_x=[0, 100])
            fig_h.update_traces(marker_color='#22C55E')
            st.plotly_chart(fig_h, use_container_width=True)

        with c2:
            st.subheader("💰 Financial Value by Category")
            cat_val = df_inv.groupby('Category')['Total Value'].sum().reset_index()
            fig_v = px.pie(cat_val, values='Total Value', names='Category', hole=0.4)
            st.plotly_chart(fig_v, use_container_width=True)
    else:
        st.info("Inventory is empty.")

# REGISTER
elif menu == "📝 Register New Asset":
    st.subheader("Asset Registration")
    cat_select = st.selectbox("Category", list(ASSET_CATEGORIES.keys()))
    sub_options = ASSET_CATEGORIES[cat_select]
    with st.form("reg_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        sub_select = c1.selectbox("Subsystem", sub_options)
        qty = c1.number_input("Quantity", min_value=1)
        u_cost = c2.number_input("Unit Cost", min_value=0.0)
        e_life = c1.number_input("Expected Life (Yrs)", min_value=1)
        c_age = c2.number_input("Current Age (Yrs)", min_value=0)
        if st.form_submit_button("✅ Register"):
            # Col order: Category, Asset Name, Asset Code, Unit, Qty, Status, Unit Cost, Total Value, Exp Life, Curr Age, Func, Non-Func
            inv_ws.append_row([cat_select, sub_select, "", "Nos", qty, "Functional", u_cost, qty*u_cost, e_life, c_age, qty, 0])
            st.success("Asset added.")
            st.rerun()

# ASSESSMENT (EDIT ALL)
elif menu == "🔎 Conditional Assessment":
    st.subheader("🔎 Comprehensive Inventory Update")
    if not df_inv.empty:
        df_edit = df_inv[["Category", "Asset Name", "Quantity", "Functional Qty", "Non-Functional Qty", "Unit Cost", "Expected Life", "Current Age"]].copy()
        
        edited_df = st.data_editor(
            df_edit,
            column_config={
                "Category": st.column_config.Column(disabled=True),
                "Asset Name": st.column_config.Column(disabled=True),
                "Unit Cost": st.column_config.NumberColumn("Unit Cost ($)", format="$%.2f"),
                "Quantity": st.column_config.NumberColumn("Total Qty"),
                "Functional Qty": st.column_config.NumberColumn("Func ✅"),
                "Non-Functional Qty": st.column_config.NumberColumn("Non-Func ❌"),
            },
            hide_index=True, use_container_width=True, key="full_editor"
        )

        if st.button("💾 Save Changes"):
            with st.spinner("Syncing Financials and Status..."):
                for index, row in edited_df.iterrows():
                    row_idx = index + 2
                    total_val = float(row['Quantity']) * float(row['Unit Cost'])
                    status = "Functional" if row['Functional Qty'] > 0 else "Non-Functional"
                    # Update Map: 5:Qty, 6:Status, 7:Unit Cost, 8:Total Value, 9:Exp Life, 10:Curr Age, 11:Func, 12:Non-Func
                    inv_ws.update_cell(row_idx, 5, int(row['Quantity']))
                    inv_ws.update_cell(row_idx, 6, status)
                    inv_ws.update_cell(row_idx, 7, float(row['Unit Cost']))
                    inv_ws.update_cell(row_idx, 8, total_val)
                    inv_ws.update_cell(row_idx, 9, int(row['Expected Life']))
                    inv_ws.update_cell(row_idx, 10, int(row['Current Age']))
                    inv_ws.update_cell(row_idx, 11, int(row['Functional Qty']))
                    inv_ws.update_cell(row_idx, 12, int(row['Non-Functional Qty']))
                st.success("Database fully updated!")
                st.rerun()
        
        st.divider()
        with st.expander("🗑️ Danger Zone - Delete Asset"):
            df_inv['Label'] = df_inv['Category'] + " | " + df_inv['Asset Name']
            to_del = st.selectbox("Select Asset to Remove", df_inv['Label'].tolist())
            if st.button("❌ Permanent Delete"):
                idx = df_inv[df_inv['Label'] == to_del].index[0]
                inv_ws.delete_rows(int(idx) + 2)
                st.rerun()

# MAINTENANCE
elif menu == "🛠️ Maintenance Log":
    st.subheader("🛠️ Log Maintenance")
    if not df_inv.empty:
        m_cat = st.selectbox("Category", sorted(df_inv["Category"].unique()))
        sub_list = df_inv[df_inv["Category"] == m_cat]["Asset Name"].unique()
        with st.form("m_form", clear_on_submit=True):
            target = st.selectbox("Subsystem", sub_list)
            qty = st.number_input("Qty", min_value=1)
            loc = st.text_input("Location (KM)")
            cost = st.number_input("Repair Cost", min_value=0.0)
            if st.form_submit_button("💾 Save"):
                maint_ws.append_row([m_cat, target, str(datetime.date.today()), qty, "Nos", loc, "Maintenance", "Service", cost])
                st.success("Log saved.")
                st.rerun()























































