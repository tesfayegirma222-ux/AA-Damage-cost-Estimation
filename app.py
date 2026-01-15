import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- 1. EQUIPMENT DATABASE STRUCTURE ---
# This ensures your specific categories and subsystems are locked in
EQUIPMENT_MAP = {
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
        st.error(f"Setup Error: {e}")
        st.stop()

sh = init_connection()
inv_ws = sh.worksheet("Inventory")
maint_ws = sh.worksheet("Maintenance")

# --- 3. DATA ENGINE ---
def get_safe_data(worksheet):
    data = worksheet.get_all_values()
    if not data or len(data) < 1: return pd.DataFrame()
    headers = [" ".join(str(h).split()) for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    num_cols = ['Quantity', 'Functional Qty', 'Non-Functional Qty', 'Current Age', 'Expected Life']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

df_inv = get_safe_data(inv_ws)

# --- 4. UI STYLE ---
st.set_page_config(page_title="AAE Asset Smart Portal", layout="wide")
st.markdown("""
    <style>
    .main-header { background-color: #1E3A8A; padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px;}
    </style>
    <div class="main-header">
        <h1>Addis Ababa-Adama Expressway</h1>
        <p>Electromechanical Equipment Management System</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Inventory Assessment", "📝 Register New Asset", "🛠️ Maintenance Log"])

# --- 5. MODULE: SMART DASHBOARD ---
if menu == "📊 Smart Dashboard":
    if not df_inv.empty:
        m1, m2, m3 = st.columns(3)
        total_q = df_inv['Quantity'].sum()
        func_q = df_inv['Functional Qty'].sum()
        health_pct = (func_q / total_q * 100) if total_q > 0 else 0
        
        m1.metric("Overall Operational Health", f"{health_pct:.1f}%")
        m2.metric("Working Units", int(func_q))
        m3.metric("Down Units", int(df_inv['Non-Functional Qty'].sum()))

        st.divider()
        st.subheader("📊 System Health by Category")
        
        # Calculate Health per Category
        cat_sum = df_inv.groupby('Category').agg({'Functional Qty': 'sum', 'Quantity': 'sum'}).reset_index()
        cat_sum['Health %'] = (cat_sum['Functional Qty'] / cat_sum['Quantity'].replace(0, 1) * 100).round(1)
        
        # Color Logic
        cat_sum['Status'] = pd.cut(cat_sum['Health %'], bins=[-1, 50, 80, 101], labels=['Critical', 'Warning', 'Healthy'])
        
        fig = px.bar(cat_sum.sort_values('Health %'), x='Health %', y='Category', orientation='h', 
                     range_x=[0, 100], text='Health %', color='Status',
                     color_discrete_map={'Healthy': '#22C55E', 'Warning': '#FACC15', 'Critical': '#EF4444'})
        st.plotly_chart(fig, use_container_width=True)

# --- 6. MODULE: INVENTORY ASSESSMENT ---
elif menu == "🔎 Inventory Assessment":
    st.subheader("🔎 Update Equipment Status")
    st.info("Input the number of Functional units. Broken units and Status will update automatically.")
    
    if not df_inv.empty:
        edit_view = df_inv[['Category', 'Asset Name', 'Quantity', 'Functional Qty', 'Non-Functional Qty']]
        
        updated_df = st.data_editor(
            edit_view, 
            hide_index=True, 
            use_container_width=True, 
            key="equipment_editor",
            column_config={
                "Quantity": st.column_config.NumberColumn("Total", disabled=True),
                "Functional Qty": st.column_config.NumberColumn("Functional ✅", min_value=0),
                "Non-Functional Qty": st.column_config.NumberColumn("Broken ❌ (Auto)", disabled=True)
            }
        )

        if st.button("💾 Sync Updates to Dashboard"):
            with st.spinner("Updating records..."):
                headers = [" ".join(h.split()) for h in inv_ws.row_values(1)]
                idx_f = headers.index("Functional Qty") + 1
                idx_nf = headers.index("Non-Functional Qty") + 1
                idx_s = headers.index("Status") + 1
                
                for i, row in updated_df.iterrows():
                    sheet_row = i + 2
                    total = int(row['Quantity'])
                    f_val = min(int(row['Functional Qty']), total) # Prevent over-counting
                    nf_val = total - f_val
                    stat_text = "Functional" if f_val == total else "Partial/Non-Functional"
                    
                    inv_ws.update_cell(sheet_row, idx_f, f_val)
                    inv_ws.update_cell(sheet_row, idx_nf, nf_val)
                    inv_ws.update_cell(sheet_row, idx_s, stat_text)
                    
                st.success("✅ Dashboard Updated!")
                st.rerun()

# --- 7. MODULE: REGISTER NEW ASSET ---
elif menu == "📝 Register New Asset":
    st.subheader("Add New Equipment to Inventory")
    col1, col2 = st.columns(2)
    
    with col1:
        cat_choice = st.selectbox("Select Category", list(EQUIPMENT_MAP.keys()))
    with col2:
        sub_choice = st.selectbox("Select Subsystem", EQUIPMENT_MAP[cat_choice])
        
    with st.form("new_asset_form"):
        qty = st.number_input("Total Quantity", min_value=1, step=1)
        age = st.number_input("Current Age (Years)", min_value=0)
        life = st.number_input("Expected Life (Years)", min_value=1, value=10)
        
        if st.form_submit_button("Register Equipment"):
            # Columns: Category, Asset Name, Code, Unit, Qty, Status, U-Cost, T-Val, Exp-Life, Age, Func, Non-Func
            inv_ws.append_row([cat_choice, sub_choice, "", "Nos", qty, "Functional", 0, 0, life, age, qty, 0])
            st.success(f"{sub_choice} added to {cat_choice}!")
            st.rerun()

# --- 8. MAINTENANCE LOG ---
elif menu == "🛠️ Maintenance Log":
    st.subheader("Equipment Maintenance History")
    df_m = get_safe_data(maint_ws)
    st.dataframe(df_m, use_container_width=True)




































































