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
        m3.metric("🏥 Global Health Score", f"{health:.1f}%")

        st.divider()
        l, r = st.columns(2)
        with l:
            st.markdown("### 💰 Investment Breakdown")
            fig_pie = px.pie(df_inv, values=v_col, names=c_col, hole=0.5, template="plotly_white", height=350)
            fig_pie.update_layout(margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_pie, use_container_width=True)
        with r:
            st.markdown("### 🛠️ Operational Health Score (%)")
            h_df = df_inv.groupby(c_col).agg({q_col: 'sum', f_col: 'sum'}).reset_index()
            h_df['Health %'] = (h_df[f_col] / h_df[q_col] * 100).round(1)
            fig_h = px.bar(h_df.sort_values('Health %'), x='Health %', y=c_col, orientation='h', 
                           text='Health %', color='Health %', color_continuous_scale='RdYlGn', 
                           height=350, template="plotly_white")
            fig_h.update_traces(texttemplate='%{text}%', textposition='outside')
            fig_h.update_layout(margin=dict(l=20, r=20, t=20, b=20), yaxis_title=None, xaxis_title=None)
            st.plotly_chart(fig_h, use_container_width=True)

        st.divider()
        st.markdown("### 🔍 Root Cause Analysis (Deep-Dive)")
        if not df_maint.empty:
            fig_sun = px.sunburst(df_maint, path=['Category', 'Subsystem', 'Failure Cause'], color='Category', template="plotly_white")
            st.plotly_chart(fig_sun, use_container_width=True)

# --- 7. MAINTENANCE LOG (DYNAMIC LOGIC) ---
elif menu == "🛠️ Maintenance History":
    st.subheader("🛠️ Technical RCA Maintenance Log")
    with st.expander("🚨 Log Equipment Failure", expanded=True):
        col_a, col_b = st.columns(2)
        sel_cat = col_a.selectbox("Major Category", list(AAE_STRUCTURE.keys()))
        sel_sub = col_b.selectbox("Subsystem", AAE_STRUCTURE.get(sel_cat, []))
        
        with st.form("maint_form", clear_on_submit=True):
            col_c, col_d = st.columns(2)
            sel_cause = col_c.selectbox("Root Cause of Failure", RCA_STANDARDS.get(sel_cat, []) + RCA_STANDARDS["General"])
            asset_code = col_d.text_input("Asset Code")
            
            col_e, col_f = st.columns(2)
            tech_name = col_e.text_input("Technician Name")
            f_date = col_f.date_input("Incident Date", datetime.now())
            
            if st.form_submit_button("Submit Technical Report"):
                if asset_code and tech_name:
                    maint_ws.append_row([f_date.strftime("%Y-%m-%d"), sel_cat, sel_sub, asset_code, sel_cause, tech_name, "Pending"])
                    st.success(f"Log successful for {asset_code}"); st.rerun()
                else:
                    st.error("Please fill Asset Code and Technician.")

    st.divider()
    st.dataframe(df_maint.sort_values(by=df_maint.columns[0], ascending=False), use_container_width=True, hide_index=True)

# --- 8. REMAINING MODULES ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 New Asset Registration")
    with st.form("reg_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        reg_cat = c1.selectbox("Category", list(AAE_STRUCTURE.keys()))
        reg_sub = c2.selectbox("Subsystem", AAE_STRUCTURE[reg_cat])
        reg_code = st.text_input("Asset Code")
        reg_qty = st.number_input("Quantity", min_value=1)
        reg_cost = st.number_input("Unit Cost (ETB)", min_value=0.0)
        if st.form_submit_button("✅ Register"):
            total_val = reg_qty * reg_cost
            inv_ws.append_row([reg_cat, reg_sub, reg_code, "Nos", reg_qty, reg_qty, reg_cost, total_val, 10, 0, 0])
            st.success(f"Success! Column 8 Value: {total_val:,.2f} Br"); st.rerun()

elif menu == "🔎 Inventory Status":
    st.subheader("🔎 Master Registry Management")
    if not df_inv.empty:
        edited_df = st.data_editor(df_inv, use_container_width=True, hide_index=True)
        if st.button("💾 Sync Database"):
            inv_ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
            st.success("Synced!"); st.rerun()











































































































