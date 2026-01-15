import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import io

# --- 1. EQUIPMENT STRUCTURE ---
EQUIPMENT_STRUCTURE = {
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

# --- 2. AUTH & SMART CONNECTION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        url = st.secrets["SHEET_URL"]
        sh = client.open_by_url(url)
        all_sheets = [ws.title for ws in sh.worksheets()]
        target = next((s for s in all_sheets if "inventory" in s.lower()), all_sheets[0])
        return sh.worksheet(target)
    except Exception as e:
        st.error(f"Spreadsheet Connection Error: {e}")
        return None

inv_ws = init_connection()

# --- 3. DATA ENGINE ---
def get_clean_data(worksheet):
    if not worksheet: return pd.DataFrame()
    data = worksheet.get_all_values()
    if len(data) < 2: return pd.DataFrame()
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers).replace('', None).dropna(how='all')
    num_cols = ['Quantity', 'Functional Qty', 'Non-Functional Qty']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0
    return df

df_inv = get_clean_data(inv_ws)

# --- 4. UI STYLING ---
st.set_page_config(page_title="AAE Asset Smart Portal", layout="wide")
st.markdown("""
    <style>
    .main-header { background-color: #1E3A8A; padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 25px;}
    .maintenance-card { background-color: #FEF2F2; border-left: 5px solid #EF4444; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    </style>
    <div class="main-header">
        <h1>Addis Ababa-Adama Expressway</h1>
        <p>Smart Electromechanical Management System</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Inventory Assessment", "🛠️ Maintenance Suggester", "📝 Register New Equipment"])

# --- 5. MODULE: SMART DASHBOARD ---
if menu == "📊 Smart Dashboard":
    if not df_inv.empty:
        m1, m2, m3 = st.columns(3)
        total_q = df_inv['Quantity'].sum()
        func_q = df_inv['Functional Qty'].sum()
        health = (func_q / total_q * 100) if total_q > 0 else 0
        
        m1.metric("Overall System Health", f"{health:.1f}%")
        m2.metric("Operational Units", int(func_q))
        m3.metric("Maintenance Required", int(df_inv['Non-Functional Qty'].sum()))

        st.divider()
        st.subheader("📊 Category Operational Health")
        chart_data = df_inv.groupby('Category').agg({'Functional Qty':'sum', 'Quantity':'sum'}).reset_index()
        chart_data['Health %'] = (chart_data['Functional Qty'] / chart_data['Quantity'].replace(0,1) * 100).round(1)
        
        fig = px.bar(chart_data.sort_values('Health %'), x='Health %', y='Category', orientation='h', 
                     range_x=[0, 105], text='Health %', color='Health %',
                     color_continuous_scale=['#EF4444', '#FACC15', '#22C55E'])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available. Please register equipment.")

# --- 6. MODULE: INVENTORY ASSESSMENT ---
elif menu == "🔎 Inventory Assessment":
    st.subheader("🔎 Status Update")
    if not df_inv.empty:
        st.markdown("Update **Functional Qty** to refresh system health.")
        edited_df = st.data_editor(
            df_inv[['Category', 'Asset Name', 'Quantity', 'Functional Qty', 'Non-Functional Qty']],
            hide_index=True, use_container_width=True,
            column_config={
                "Category": st.column_config.Column(disabled=True),
                "Asset Name": st.column_config.Column(disabled=True),
                "Quantity": st.column_config.NumberColumn("Total", disabled=True),
                "Functional Qty": st.column_config.NumberColumn("Working ✅", min_value=0),
                "Non-Functional Qty": st.column_config.NumberColumn("Broken ❌ (Auto)", disabled=True)
            }
        )
        if st.button("💾 Sync Updates"):
            with st.spinner("Syncing to Cloud..."):
                headers = [h.strip() for h in inv_ws.row_values(1)]
                f_idx = headers.index("Functional Qty")+1
                nf_idx = headers.index("Non-Functional Qty")+1
                for i, row in edited_df.iterrows():
                    sheet_row = int(df_inv.index[i]) + 2 
                    total = int(row['Quantity'])
                    f_val = min(int(row['Functional Qty']), total)
                    inv_ws.update_cell(sheet_row, f_idx, f_val)
                    inv_ws.update_cell(sheet_row, nf_idx, total - f_val)
                st.success("✅ Synced!"); st.rerun()

# --- 7. MODULE: MAINTENANCE SUGGESTER ---
elif menu == "🛠️ Maintenance Suggester":
    st.subheader("🛠️ Priority Maintenance List")
    broken_assets = df_inv[df_inv['Non-Functional Qty'] > 0].copy()
    
    if broken_assets.empty:
        st.success("🎉 All systems are 100% operational.")
    else:
        st.warning(f"Found {len(broken_assets)} items needing repair.")
        
        # Download Button
        csv = broken_assets.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Maintenance Report (CSV)", csv, "maintenance_list.csv", "text/csv")
        
        for _, row in broken_assets.iterrows():
            st.markdown(f"""
                <div class="maintenance-card">
                    <strong>{row['Category']}</strong> - {row['Asset Name']}<br>
                    <span style="color: #EF4444;">🔴 {int(row['Non-Functional Qty'])} Units Broken / Out of {int(row['Quantity'])} Total</span>
                </div>
            """, unsafe_allow_html=True)
        
        

# --- 8. MODULE: REGISTER NEW EQUIPMENT ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 Registration")
    cat = st.selectbox("Category", list(EQUIPMENT_STRUCTURE.keys()))
    sub = st.selectbox("Subsystem", EQUIPMENT_STRUCTURE[cat])
    with st.form("reg", clear_on_submit=True):
        qty = st.number_input("Quantity", min_value=1, step=1)
        if st.form_submit_button("✅ Register Hardware"):
            # Format: Category, Asset Name, Code, Unit, Qty, Status, U-Cost, T-Val, Life, Age, Func Qty, Non-Func Qty
            inv_ws.append_row([cat, sub, "", "Nos", qty, "Functional", 0, 0, 10, 0, qty, 0])
            st.success("Registered!"); st.rerun()










































































