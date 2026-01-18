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

# --- 3. DATA ENGINE (SPECIFIC COLUMN 8 TARGETING) ---
def load_data(worksheet):
    if not worksheet: return pd.DataFrame()
    data = worksheet.get_all_values()
    if len(data) < 2: return pd.DataFrame()
    
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    
    # Force Column 8 (index 7) to be numeric for Total Cost
    if len(df.columns) >= 8:
        val_col_name = df.columns[7] # 0-based index 7 is Column 8
        df[val_col_name] = pd.to_numeric(df[val_col_name], errors='coerce').fillna(0)
    
    # Convert other numeric columns (Qty, Functional etc)
    for col in df.columns:
        if any(k in col.lower() for k in ['qty', 'total', 'cost', 'func']):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

# --- 4. UI SETUP ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
df_inv = load_data(inv_ws)
df_maint = load_data(maint_ws)

st.markdown("""
    <div style="background: #1E3A8A; color: white; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
        <h2 style="margin:0;">Addis Ababa-Adama Expressway</h2>
        <p style="margin:0;">Electromechanical Asset Management System</p>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Dashboard", "🔎 Inventory Status", "📝 Register New Equipment", "🛠️ Maintenance History"])

# --- 5. DASHBOARD (SUMMING COLUMN 8) ---
if menu == "📊 Dashboard":
    st.subheader("📊 System Health & Financial Analytics")
    
    if not df_inv.empty:
        # Define columns based on position
        val_col = df_inv.columns[7] if len(df_inv.columns) >= 8 else None
        q_col = next((c for c in df_inv.columns if 'qty' in c.lower()), df_inv.columns[4])
        f_col = next((c for c in df_inv.columns if 'func' in c.lower()), df_inv.columns[5])
        
        # --- TOP LEVEL METRICS ---
        m1, m2, m3 = st.columns(3)
        
        # SUMMING COLUMN 8
        total_value_sum = df_inv[val_col].sum() if val_col else 0
        m1.metric("Total Asset Value", f"{total_value_sum:,.2f} Br")
        
        total_qty = df_inv[q_col].sum()
        m2.metric("Total Assets (Qty)", int(total_qty))
        
        health_score = (df_inv[f_col].sum() / total_qty * 100) if total_qty > 0 else 0
        m3.metric("Overall System Health", f"{health_score:.1f}%")

        st.divider()

        # --- CHARTS ---
        l, r = st.columns(2)
        with l:
            st.markdown("#### 💰 Financial Value by Category (Col 8)")
            fig_pie = px.pie(df_inv, values=val_col, names=df_inv.columns[0], hole=0.4,
                            color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)

        with r:
            st.markdown("#### 🛠️ Operational Health Score (%)")
            h_df = df_inv.groupby(df_inv.columns[0]).agg({q_col: 'sum', f_col: 'sum'}).reset_index()
            h_df['Health %'] = (h_df[f_col] / h_df[q_col] * 100).round(1)
            fig_bar = px.bar(h_df.sort_values('Health %'), x='Health %', y=df_inv.columns[0], 
                             orientation='h', color='Health %', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_bar, use_container_width=True)

# --- 6. REGISTRATION (ENSURING DATA GOES TO COL 8) ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 New Asset Registration")
    with st.form("reg_form"):
        c1, c2 = st.columns(2)
        cat = c1.selectbox("Category", list(AAE_STRUCTURE.keys()))
        sub = c2.selectbox("Subsystem", AAE_STRUCTURE[cat])
        code = st.text_input("Asset Code")
        qty = st.number_input("Quantity", min_value=1)
        cost = st.number_input("Unit Cost (ETB)", min_value=0.0)
        
        if st.form_submit_button("✅ Register Asset"):
            total_val = qty * cost
            # APPENDING: Cat, Sub, Code, Unit, Qty, Func, UnitCost, TotalValue (Col 8), Life, Age, NonFunc
            new_row = [cat, sub, code, "Nos", qty, qty, cost, total_val, 10, 0, 0]
            inv_ws.append_row(new_row)
            st.success(f"Registered! Column 8 Value: {total_val:,.2f} Br")
            st.rerun()

# Rest of the modules (Inventory Status, Maintenance History) remain unchanged...







































































































