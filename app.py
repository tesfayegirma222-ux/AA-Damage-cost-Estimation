import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. AAE OFFICIAL HIERARCHY & RCA STANDARDS ---
AAE_STRUCTURE = {
    "Electric Power Source": ["Electric Utility", "Generator"],
    "Auto-Railing System": ["Barrier Gate", "Controller"],
    "Illumination System": ["High Mast Light", "Compound Light", "Road Light", "Booth Light", "Plaza Light"],
    "Electronic Display System": ["Canopy Light", "VMS", "LED Notice Board", "Fog Light"],
    "Pump System": ["Surface Water Pump", "Submersible Pump"],
    "Overload System (WIM)": ["Weight-In-Motion Sensor", "WIM Controller"]
}

RCA_STANDARDS = {
    "Electric Power Source": ["Fuel Contamination", "Battery Drain", "AVR Failure", "Coolant Leak", "Alternator Fault"],
    "Auto-Railing System": ["Motor Burnout", "Limit Switch Misalignment", "Loop Detector Fault", "Mechanical Obstruction"],
    "Illumination System": ["Lamp Burnout", "Ballast Failure", "Photocell Fault", "Cable Insulation Breakdown", "MCB Tripping"],
    "Electronic Display System": ["Communication Timeout", "LED Module Failure", "Power Supply Unit (PSU) Fault", "Overheating"],
    "Pump System": ["Dry Running", "Impeller Clogging", "Seal Leakage", "Phase Loss", "Pressure Switch Fault"],
    "Overload System (WIM)": ["Sensor Calibration Drift", "Piezoelectric Damage", "Grounding Issue", "Inductive Loop Fault"],
    "General": ["Power Surge", "Vandalism", "Accident", "Wear & Tear", "Software Error", "Unknown"]
}

# --- 2. SECURE CONNECTION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(st.secrets["SHEET_URL"])
        inv = next((s for s in sh.worksheets() if "inventory" in s.title.lower()), sh.get_worksheet(0))
        try:
            maint = sh.worksheet("Maintenance_Log")
        except:
            maint = sh.add_worksheet(title="Maintenance_Log", rows="1000", cols="10")
            maint.append_row(["Date", "Category", "Subsystem", "Asset Code", "Failure Cause", "Technician", "Status"])
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
    
    # Process numeric columns (Targeting Column 8/Index 7 for Value)
    for i, col in enumerate(df.columns):
        if any(k in col.lower() for k in ['qty', 'total', 'cost', 'value', 'func']) or i == 7:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

# --- 4. UI SETUP ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
df_inv = load_data(inv_ws)
df_maint = load_data(maint_ws)

st.markdown("""
    <div style="background: #1E3A8A; color: white; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
        <h2 style="margin:0;">Addis Ababa-Adama Expressway</h2>
        <p style="margin:0;">Electromechanical Master Database (Live Status)</p>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Dashboard", "🔎 Inventory Status", "📝 Register New Equipment", "🛠️ Maintenance History"])

# --- 5. DASHBOARD MODULE ---
if menu == "📊 Dashboard":
    st.subheader("📊 System Health & Financial Analytics")
    if not df_inv.empty:
        # Identify columns by index/name
        v_col = df_inv.columns[7] if len(df_inv.columns) >= 8 else None
        q_col = next((c for c in df_inv.columns if 'qty' in c.lower()), df_inv.columns[4])
        f_col = next((c for c in df_inv.columns if 'func' in c.lower()), df_inv.columns[5])
        c_col = df_inv.columns[0]
        
        # Metrics
        m1, m2, m3 = st.columns(3)
        total_val = df_inv[v_col].sum() if v_col else 0
        m1.metric("Total Asset Value", f"{total_val:,.2f} Br")
        m2.metric("Total Assets (Qty)", int(df_inv[q_col].sum()))
        
        health_overall = (df_inv[f_col].sum() / df_inv[q_col].sum() * 100) if df_inv[q_col].sum() > 0 else 0
        m3.metric("Overall System Health", f"{health_overall:.1f}%")

        st.divider()
        l, r = st.columns(2)
        with l:
            st.markdown("#### 💰 Financial Weight (Col 8)")
            st.plotly_chart(px.pie(df_inv, values=v_col, names=c_col, hole=0.4), use_container_width=True)

        with r:
            st.markdown("#### 🛠️ Operational Health Score (%)")
            h_df = df_inv.groupby(c_col).agg({q_col: 'sum', f_col: 'sum'}).reset_index()
            h_df['Health %'] = (h_df[f_col] / h_df[q_col] * 100).round(1)
            h_df = h_df.sort_values('Health %')
            
            # Bar Chart with explicit score labels
            fig_health = px.bar(h_df, x='Health %', y=c_col, orientation='h', 
                               text='Health %', color='Health %', 
                               color_continuous_scale='RdYlGn', range_color=[0, 100])
            fig_health.update_traces(texttemplate='%{text}%', textposition='outside')
            st.plotly_chart(fig_health, use_container_width=True)

# --- 6. REGISTRY MODULE ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 New Asset Registration")
    with st.form("reg_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        cat = col1.selectbox("Category", list(AAE_STRUCTURE.keys()))
        sub = col2.selectbox("Subsystem", AAE_STRUCTURE[cat])
        code = st.text_input("Asset Code")
        qty = st.number_input("Quantity", min_value=1)
        cost = st.number_input("Unit Cost (ETB)", min_value=0.0)
        if st.form_submit_button("✅ Register"):
            total_v = qty * cost
            inv_ws.append_row([cat, sub, code, "Nos", qty, qty, cost, total_v, 10, 0, 0])
            st.success(f"Registered {code} at {total_v:,.2f} Br"); st.rerun()

# --- 7. INVENTORY STATUS ---
elif menu == "🔎 Inventory Status":
    st.subheader("🔎 Master Registry")
    if not df_inv.empty:
        edited_df = st.data_editor(df_inv, use_container_width=True, hide_index=True)
        if st.button("💾 Sync Database"):
            inv_ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
            st.success("Synced!"); st.rerun()

# --- 8. MAINTENANCE HISTORY ---
elif menu == "🛠️ Maintenance History":
    st.subheader("🛠️ Technical Failure Log")
    with st.expander("🚨 Report Failure"):
        with st.form("m_form"):
            m_cat = st.selectbox("Category", list(AAE_STRUCTURE.keys()))
            m_sub = st.selectbox("Subsystem", AAE_STRUCTURE[m_cat])
            m_cause = st.selectbox("Root Cause", RCA_STANDARDS.get(m_cat, []) + RCA_STANDARDS["General"])
            m_code = st.text_input("Asset Code")
            if st.form_submit_button("Submit"):
                maint_ws.append_row([datetime.now().strftime("%Y-%m-%d"), m_cat, m_sub, m_code, m_cause, "System", "Pending"])
                st.success("Logged!"); st.rerun()
    st.dataframe(df_maint, use_container_width=True)








































































































