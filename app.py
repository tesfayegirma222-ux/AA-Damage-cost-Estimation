import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. EXPANDED AAE HIERARCHY ---
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

# --- 2. TECHNICAL ROOT CAUSE LIST ---
RCA_STANDARDS = {
    "Electric Power Source": ["Fuel Contamination", "AVR Failure", "Battery Dead", "Coolant Leak", "Alternator Short Circuit", "Oil Pressure Sensor Fault", "Utility Grid Outage"],
    "Electric Power Distribution": ["MCB Tripped", "Contact Burnout", "Cable Insulation Failure", "Phase Imbalance", "Loose Connection", "Busbar Overheating"],
    "UPS System": ["Battery Cell Swelling", "Inverter Circuit Failure", "Static Switch Fault", "DC Bus Overvoltage", "Fan Failure"],
    "CCTV System": ["BNC/RJ45 Connector Corrosion", "Power Supply Unit Fault", "Hard Drive Failure", "IP Conflict", "Lens Fogging", "Lightning Damage"],
    "Auto-Railing System": ["Motor Capacitor Failure", "Gearbox Jam", "Limit Switch Error", "Spring Tension Loss", "Controller Logic Error"],
    "HVAC System": ["Refrigerant Leak", "Compressor Failure", "Thermostat Malfunction", "Filter Clogging", "Capacitor Burnout"],
    "Illumination System": ["Lamp/LED Burnout", "Ballast/Driver Failure", "Photocell Sensor Clogging", "Contacting Coil Failure", "Underground Cable Fault"],
    "Electronic Display System": ["LED Module Pixel Loss", "Communication Card Timeout", "Switching Power Supply (SPS) Fault", "Controller Hang-up", "Flat Cable Loose"],
    "Pump System": ["Dry Run Protection Trip", "Impeller Clogging", "Mechanical Seal Leak", "Bearing Noise/Failure", "Float Switch Stuck"],
    "Overload System (WIM)": ["Load Cell Calibration Drift", "Piezoelectric Sensor Damage", "Interface Card Failure", "Signal Noise/Interference", "Grout Cracking"],
    "General": ["Vandalism", "Physical Accident", "Extreme Weather", "Unauthorized Access", "End of Life (Wear & Tear)"]
}

# --- 3. SECURE CONNECTION ---
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

# --- 5. UI SETUP ---
st.set_page_config(page_title="AAE Master Asset Portal", layout="wide")
df_inv = load_data(inv_ws)
df_maint = load_data(maint_ws)

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 30px; color: #1E3A8A; }
    .header-style { background: #1E3A8A; color: white; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 25px; }
    </style>
    <div class="header-style">
        <h1 style="margin:0;">Addis Ababa-Adama Expressway</h1>
        <p style="margin:0;">Electromechanical Master Database & RCA Analytics</p>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Dashboard", "🔎 Inventory Status", "📝 Register New Equipment", "🛠️ Maintenance History"])

# --- 6. DASHBOARD MODULE ---
if menu == "📊 Dashboard":
    if not df_inv.empty:
        v_col = df_inv.columns[7] if len(df_inv.columns) >= 8 else None
        q_col = next((c for c in df_inv.columns if 'qty' in c.lower()), df_inv.columns[4])
        f_col = next((c for c in df_inv.columns if 'func' in c.lower()), df_inv.columns[5])
        c_col = df_inv.columns[0]
        
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Total Asset Value (Col 8)", f"{df_inv[v_col].sum():,.2f} Br")
        m2.metric("📦 Equipment Count", int(df_inv[q_col].sum()))
        health = (df_inv[f_col].sum() / df_inv[q_col].sum() * 100) if df_inv[q_col].sum() > 0 else 0
        m3.metric("Global Health Score", f"{health:.1f}%")

        st.divider()
        l, r = st.columns(2)
        with l:
            st.markdown("### 💰 Investment Breakdown")
            fig_pie = px.pie(df_inv, values=v_col, names=c_col, hole=0.5, height=350)
            st.plotly_chart(fig_pie, use_container_width=True)
        with r:
            st.markdown("### 🛠️ Operational Health Score (%)")
            h_df = df_inv.groupby(c_col).agg({q_col: 'sum', f_col: 'sum'}).reset_index()
            h_df['Health %'] = (h_df[f_col] / h_df[q_col] * 100).round(1)
            fig_h = px.bar(h_df.sort_values('Health %'), x='Health %', y=c_col, orientation='h', 
                           text='Health %', color='Health %', color_continuous_scale='RdYlGn', 
                           height=350)
            fig_h.update_traces(texttemplate='%{text}%', textposition='outside')
            st.plotly_chart(fig_h, use_container_width=True)

# --- 7. DYNAMIC REGISTRATION MODULE ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 New Asset Registration")
    st.info("Select a category to see its specific subsystems.")
    
    # Selection logic outside the form to enable reactivity
    reg_col1, reg_col2 = st.columns(2)
    sel_reg_cat = reg_col1.selectbox("Major Category", list(AAE_STRUCTURE.keys()))
    sub_options = AAE_STRUCTURE.get(sel_reg_cat, [])
    sel_reg_sub = reg_col2.selectbox("Subsystem", sub_options)

    with st.form("reg_form", clear_on_submit=True):
        col_c, col_d, col_e = st.columns(3)
        reg_code = col_c.text_input("Asset Code (Unique ID)")
        reg_qty = col_d.number_input("Total Quantity", min_value=1, step=1)
        reg_cost = col_e.number_input("Unit Cost (ETB)", min_value=0.0, format="%.2f")
        
        col_f, col_g = st.columns(2)
        reg_unit = col_f.selectbox("Unit", ["Nos", "Sets", "Meters", "Km"])
        reg_life = col_g.number_input("Useful Life (Years)", min_value=1, value=10)
        
        if st.form_submit_button("✅ Register Asset"):
            if not reg_code:
                st.error("Asset Code is required.")
            else:
                total_val = reg_qty * reg_cost
                # Matches AAE Column Layout: Cat, Sub, Code, Unit, Qty, Func(Initial=Qty), Cost, TotalValue(Col8), Life, Age(0), NonFunc(0)
                new_asset = [sel_reg_cat, sel_reg_sub, reg_code, reg_unit, reg_qty, reg_qty, reg_cost, total_val, reg_life, 0, 0]
                inv_ws.append_row(new_asset)
                st.success(f"Successfully Registered {reg_code}! System Value: {total_val:,.2f} Br")
                st.rerun()

# --- 8. DYNAMIC MAINTENANCE LOG ---
elif menu == "🛠️ Maintenance History":
    st.subheader("🛠️ Technical RCA Maintenance Log")
    with st.expander("🚨 Log Equipment Failure", expanded=True):
        col_a, col_b = st.columns(2)
        m_cat = col_a.selectbox("Major Category", list(AAE_STRUCTURE.keys()))
        m_sub = col_b.selectbox("Subsystem", AAE_STRUCTURE.get(m_cat, []))
        
        with st.form("maint_form", clear_on_submit=True):
            cause_options = RCA_STANDARDS.get(m_cat, []) + RCA_STANDARDS["General"]
            m_cause = st.selectbox("Root Cause of Failure", cause_options)
            m_code = st.text_input("Asset Code")
            m_tech = st.text_input("Technician Name")
            
            if st.form_submit_button("Submit Technical Report"):
                if m_code and m_tech:
                    maint_ws.append_row([datetime.now().strftime("%Y-%m-%d"), m_cat, m_sub, m_code, m_cause, m_tech, "Pending"])
                    st.success("Log successful!"); st.rerun()

elif menu == "🔎 Inventory Status":
    st.subheader("🔎 Master Registry")
    if not df_inv.empty:
        edited_df = st.data_editor(df_inv, use_container_width=True, hide_index=True)
        if st.button("💾 Sync Database"):
            inv_ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
            st.success("Synced!"); st.rerun()
















































































































