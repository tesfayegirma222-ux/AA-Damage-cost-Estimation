import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. AAE OFFICIAL HIERARCHY ---
AAE_STRUCTURE = {
    "Electric Power Source": ["Electric Utility", "Generator", "Solar Power System"],
    "Electric Power Distribution": ["ATS", "Main Breaker", "Distribution Panel", "Power Cable", "Transformer"],
    "UPS System": ["UPS Unit", "UPS Battery Bank", "Inverter"],
    "CCTV System": ["Lane Camera", "Booth Camera", "Road Camera", "PTZ Camera", "NVR/Server"],
    "Auto-Railing System": ["Barrier Gate Motor", "Barrier Controller", "Loop Detector", "Remote Control"],
    "HVAC System": ["Air Conditioning Unit", "Ventilation Fan", "Chiller"],
    "Illumination System": ["High Mast Light", "Road Light", "Booth Light", "Plaza Light", "Photocell Controller"],
    "Electronic Display System": ["VMS", "LED Notice Board", "Money Fee Display", "Passage Signal Lamp", "Fog Light"],
    "Pump System": ["Surface Water Pump", "Submersible Pump", "Fire Pump", "Pump Controller"],
    "Overload System (WIM)": ["Weight-In-Motion Sensor", "WIM Controller", "Inductive Loop", "Charging Controller"]
}

# --- 2. TECHNICAL ROOT CAUSES ---
RCA_STANDARDS = {
    "Electric Power Source": ["Fuel Contamination", "AVR Failure", "Battery Dead", "Coolant Leak", "Alternator Short", "Utility Outage"],
    "Electric Power Distribution": ["MCB Tripped", "Contact Burnout", "Insulation Failure", "Phase Imbalance", "Loose Connection"],
    "UPS System": ["Battery Swelling", "Inverter Failure", "Static Switch Fault", "Fan Failure"],
    "CCTV System": ["Connector Corrosion", "Power Supply Fault", "HDD Failure", "IP Conflict", "Lens Fogging"],
    "Auto-Railing System": ["Motor Capacitor", "Gearbox Jam", "Limit Switch Error", "Spring Tension Loss"],
    "HVAC System": ["Refrigerant Leak", "Compressor Failure", "Thermostat Fault", "Filter Clogging"],
    "Illumination System": ["Lamp Burnout", "Ballast Failure", "Photocell Sensor Clogged", "Cable Fault"],
    "Electronic Display System": ["LED Module Pixel Loss", "Comm Card Timeout", "SPS Fault", "Controller Hang-up"],
    "Pump System": ["Dry Run Protection", "Impeller Clogging", "Seal Leak", "Bearing Failure", "Float Switch Stuck"],
    "Overload System (WIM)": ["Load Cell Drift", "Piezo Damage", "Interface Card Fault", "Signal Noise"],
    "General": ["Vandalism", "Physical Accident", "Extreme Weather", "Wear & Tear"]
}

# --- 3. SECURE CONNECTION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(st.secrets["SHEET_URL"])
        
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

# --- 4. DATA ENGINE ---
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

# --- 5. PROFESSIONAL UI STYLING ---
st.set_page_config(page_title="AAE Executive Portal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-header {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        color: white; padding: 1.5rem; border-radius: 12px;
        text-align: center; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    div[data-testid="stMetricValue"] { font-size: 28px !important; font-weight: 700 !important; color: #1e3a8a !important; }
    div[data-testid="metric-container"] {
        background: white; padding: 15px; border-radius: 10px;
        border-left: 5px solid #3b82f6; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    </style>
    <div class="main-header">
        <h1 style="margin:0; font-size: 24px;">AAE ELECTROMECHANICAL EXECUTIVE PORTAL</h1>
        <p style="margin:0; opacity: 0.9;">System Integrity & Asset Management Control</p>
    </div>
""", unsafe_allow_html=True)

df_inv = load_data(inv_ws)
df_maint = load_data(maint_ws)

menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Asset Registry", "📝 Add New Asset", "🛠️ Failure Logs"])

# --- 6. SMART DASHBOARD ---
if menu == "📊 Smart Dashboard":
    if df_inv.empty:
        st.info("Inventory Empty. Use 'Add New Asset' to begin.")
    else:
        v_col = df_inv.columns[7]
        q_col = next((c for c in df_inv.columns if 'qty' in c.lower()), df_inv.columns[4])
        f_col = next((c for c in df_inv.columns if 'func' in c.lower()), df_inv.columns[5])
        c_col = df_inv.columns[0]
        
        k1, k2, k3, k4 = st.columns(4)
        val_sum = float(df_inv[v_col].sum())
        qty_sum = float(df_inv[q_col].sum())
        health = (df_inv[f_col].sum() / qty_sum * 100) if qty_sum > 0 else 0
        incidents = len(df_maint) if not df_maint.empty else 0
        
        k1.metric("💰 Portfolio Value", f"{val_sum:,.0f} Br")
        k2.metric("📦 Active Assets", f"{int(qty_sum)}")
        k3.metric("🏥 Health Index", f"{health:.1f}%")
        k4.metric("🚨 Total Incidents", incidents)

        st.divider()
        col_left, col_right = st.columns([4, 6])
        
        with col_left:
            st.markdown("#### 💎 Investment Distribution")
            fig_pie = px.pie(df_inv, values=v_col, names=c_col, hole=0.6, template="plotly_white")
            fig_pie.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_right:
            st.markdown("#### ⚡ System Health Score")
            h_df = df_inv.groupby(c_col).agg({q_col: 'sum', f_col: 'sum'}).reset_index()
            h_df['Health %'] = (h_df[f_col] / h_df[q_col] * 100).round(1).fillna(0)
            
            fig_bar = px.bar(h_df.sort_values('Health %'), x='Health %', y=c_col, orientation='h', 
                             text='Health %', color='Health %', 
                             color_continuous_scale='RdYlGn', range_x=[0, 120])
            fig_bar.update_traces(texttemplate='%{text}%', textposition='outside', 
                                  marker_line_color='rgb(30, 58, 138)', marker_line_width=1.5)
            fig_bar.update_layout(yaxis_title=None, xaxis_visible=False, height=350, 
                                  margin=dict(t=20, b=20), coloraxis_showscale=False,
                                  plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_bar, use_container_width=True)

# --- 7. DYNAMIC ADD ASSET ---
elif menu == "📝 Add New Asset":
    st.subheader("📝 New Equipment Registration")
    c1, c2 = st.columns(2)
    sel_cat = c1.selectbox("Major Category", list(AAE_STRUCTURE.keys()))
    sel_sub = c2.selectbox("Subsystem", AAE_STRUCTURE.get(sel_cat, []))
    with st.form("reg_form", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        a_code = f1.text_input("Asset Code")
        a_qty = f2.number_input("Quantity", min_value=1)
        a_cost = f3.number_input("Unit Cost (Br)", min_value=0.0)
        if st.form_submit_button("🚀 Commit to Sheet1"):
            if a_code:
                inv_ws.append_row([sel_cat, sel_sub, a_code, "Nos", a_qty, a_qty, a_cost, a_qty*a_cost, 10, 0, 0])
                st.success(f"Asset {a_code} Registered!"); st.rerun()

# --- 8. DYNAMIC FAILURE LOGS ---
elif menu == "🛠️ Failure Logs":
    st.subheader("🛠️ Technical Incident Logging")
    l1, l2 = st.columns(2)
    m_cat = l1.selectbox("Major Category", list(AAE_STRUCTURE.keys()))
    m_sub = l2.selectbox("Subsystem", AAE_STRUCTURE.get(m_cat, []))
    with st.form("maint_form", clear_on_submit=True):
        m_cause = st.selectbox("Root Cause", RCA_STANDARDS.get(m_cat, []) + RCA_STANDARDS["General"])
        m_code = st.text_input("Asset Code")
        m_tech = st.text_input("Technician")
        if st.form_submit_button("⚠️ Log Failure"):
            if m_code and m_tech:
                maint_ws.append_row([datetime.now().strftime("%Y-%m-%d"), m_cat, m_sub, m_code, m_cause, m_tech])
                st.success("Incident Logged!"); st.rerun()
    st.divider()
    if not df_maint.empty:
        st.dataframe(df_maint.sort_values(by=df_maint.columns[0], ascending=False), use_container_width=True, hide_index=True)

elif menu == "🔎 Asset Registry":
    st.subheader("🔎 Master Registry (Sheet1)")
    if not df_inv.empty:
        edited_df = st.data_editor(df_inv, use_container_width=True, hide_index=True)
        if st.button("💾 Sync Sheet1"):
            inv_ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
            st.success("Data Synced!"); st.rerun()



















































































































