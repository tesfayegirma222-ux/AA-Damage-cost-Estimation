import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. AAE HIERARCHY ---
AAE_STRUCTURE = {
    "Electric Power Source": ["Electric Utility", "Generator", "Solar Power System"],
    "Electric Power Distribution": ["ATS", "Main Breaker", "Distribution Panel", "Power Cable", "Transformer"],
    "UPS System": ["UPS Unit", "UPS Battery Bank", "Inverter"],
    "CCTV System": ["Lane Camera", "Booth Camera", "Road Camera", "PTZ Camera", "NVR/Server"],
    "Auto-Railing System": ["Barrier Gate Motor", "Barrier Controller", "Loop Detector", "Remote Control"],
    "HVAC System": ["Air Conditioning Unit", "Ventilation Fan", "Chiller"],
    "Illumination System": ["High Mast Light", "Road Light", "Booth Light", "Plaza Light", "Photocell Controller"],
    "Electronic Display System": ["VMS (Variable Message Sign)", "LED Notice Board", "Money Fee Display", "Passage Signal Lamp", "Fog Light"],
    "Pump System": ["Surface Water Pump", "Submersible Pump", "Fire Pump", "Pump Controller"],
    "Overload System (WIM)": ["Weight-In-Motion Sensor", "WIM Controller", "Inductive Loop", "Charging Controller"]
}

RCA_STANDARDS = {
    "Electric Power Source": ["Fuel Contamination", "AVR Failure", "Battery Dead", "Utility Grid Outage"],
    "General": ["Vandalism", "Physical Accident", "Extreme Weather", "Wear & Tear"]
}

# --- 2. CONNECTION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(st.secrets["SHEET_URL"])
        
        # Target Sheet1
        try:
            inv = sh.worksheet("Sheet1")
        except:
            inv = sh.get_worksheet(0)
            
        try:
            maint = sh.worksheet("Maintenance_Log")
        except:
            maint = sh.add_worksheet(title="Maintenance_Log", rows="1000", cols="6")
            maint.append_row(["Date", "Category", "Subsystem", "Asset Code", "Failure Cause", "Technician"])
        return inv, maint
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None, None

inv_ws, maint_ws = init_connection()

# --- 3. DATA ENGINE ---
def load_data(worksheet):
    if not worksheet: return pd.DataFrame()
    data = worksheet.get_all_values()
    if len(data) < 2: return pd.DataFrame()
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    for i, col in enumerate(df.columns):
        if any(k in col.lower() for k in ['qty', 'total', 'cost', 'value', 'func']) or i == 7:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

# --- 4. UI SETUP ---
st.set_page_config(page_title="AAE Master Asset Portal", layout="wide")
df_inv = load_data(inv_ws)
df_maint = load_data(maint_ws)

st.markdown("""
    <div style="background: #1E3A8A; color: white; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 25px;">
        <h1 style="margin:0;">Addis Ababa-Adama Expressway</h1>
        <p style="margin:0;">Electromechanical Master Database (Sheet1)</p>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Dashboard", "🔎 Inventory Status", "📝 Register New Equipment", "🛠️ Maintenance History"])

# --- 5. DASHBOARD ---
if menu == "📊 Dashboard":
    if df_inv.empty:
        st.warning("Inventory is currently empty. Please register equipment to see analytics.")
    else:
        v_col = df_inv.columns[7] if len(df_inv.columns) >= 8 else df_inv.columns[-1]
        q_col = next((c for c in df_inv.columns if 'qty' in c.lower()), df_inv.columns[4])
        f_col = next((c for c in df_inv.columns if 'func' in c.lower()), df_inv.columns[5])
        c_col = df_inv.columns[0]
        
        m1, m2, m3 = st.columns(3)
        val_sum = float(df_inv[v_col].sum())
        qty_sum = float(df_inv[q_col].sum())
        func_sum = float(df_inv[f_col].sum())
        
        m1.metric("💰 Total Value (Col 8)", f"{val_sum:,.2f} Br")
        m2.metric("📦 Total Count", int(qty_sum))
        health = (func_sum / qty_sum * 100) if qty_sum > 0 else 0
        m3.metric("Global Health Score", f"{health:.1f}%")

        l, r = st.columns(2)
        with l:
            st.plotly_chart(px.pie(df_inv, values=v_col, names=c_col, hole=0.5, height=350, title="Investment Breakdown"), use_container_width=True)
        with r:
            h_df = df_inv.groupby(c_col).agg({q_col: 'sum', f_col: 'sum'}).reset_index()
            h_df['Health %'] = (h_df[f_col] / h_df[q_col] * 100).round(1).fillna(0)
            fig_h = px.bar(h_df.sort_values('Health %'), x='Health %', y=c_col, orientation='h', text='Health %', color='Health %', color_continuous_scale='RdYlGn', height=350, title="Operational Health")
            fig_h.update_traces(texttemplate='%{text}%', textposition='outside')
            st.plotly_chart(fig_h, use_container_width=True)

# --- 6. REGISTRATION ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 New Asset Registration")
    c1, c2 = st.columns(2)
    reg_cat = c1.selectbox("Category", list(AAE_STRUCTURE.keys()))
    reg_sub = c2.selectbox("Subsystem", AAE_STRUCTURE.get(reg_cat, []))
    with st.form("reg_form", clear_on_submit=True):
        code = st.text_input("Asset Code")
        qty = st.number_input("Total Quantity", min_value=1)
        cost = st.number_input("Unit Cost (ETB)", min_value=0.0)
        if st.form_submit_button("✅ Register to Sheet1"):
            total_val = qty * cost
            inv_ws.append_row([reg_cat, reg_sub, code, "Nos", qty, qty, cost, total_val, 10, 0, 0])
            st.success("Registered!"); st.rerun()

elif menu == "🔎 Inventory Status":
    st.subheader("🔎 Master Registry (Sheet1)")
    if not df_inv.empty:
        edited_df = st.data_editor(df_inv, use_container_width=True, hide_index=True)
        if st.button("💾 Sync Database"):
            inv_ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
            st.success("Synced!"); st.rerun()

elif menu == "🛠️ Maintenance History":
    st.subheader("🛠️ Technical Failure Log")
    with st.form("maint_form"):
        m_cat = st.selectbox("Category", list(AAE_STRUCTURE.keys()))
        m_sub = st.selectbox("Subsystem", AAE_STRUCTURE.get(m_cat, []))
        m_code = st.text_input("Asset Code")
        m_tech = st.text_input("Technician Name")
        if st.form_submit_button("Submit"):
            maint_ws.append_row([datetime.now().strftime("%Y-%m-%d"), m_cat, m_sub, m_code, "Generic", m_tech])
            st.success("Logged!"); st.rerun()

















































































































