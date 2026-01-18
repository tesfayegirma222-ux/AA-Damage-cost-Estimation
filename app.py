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

# --- 3. DATA ENGINE (FIXED TOTAL VALUE CALCULATION) ---
def load_data(worksheet):
    if not worksheet: return pd.DataFrame()
    data = worksheet.get_all_values()
    if len(data) < 2: return pd.DataFrame()
    
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    
    # Convert numeric columns safely
    for col in df.columns:
        if any(k in col.lower() for k in ['qty', 'total', 'cost', 'value', 'life', 'age', 'func', 'non']):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # --- DYNAMIC TOTAL VALUE CORRECTION ---
    # Finding the columns to force-calculate Value
    q_col = next((c for c in df.columns if 'qty' in c.lower() or 'total' in c.lower()), None)
    u_col = next((c for c in df.columns if 'unit cost' in c.lower() or 'unitcost' in c.lower()), None)
    v_col = next((c for c in df.columns if 'value' in c.lower()), None)
    
    if q_col and u_col and v_col:
        # Force the math: Total Value = Quantity * Unit Cost
        df[v_col] = df[q_col] * df[u_col]
        
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

# --- 5. DASHBOARD (CORRECTED METRICS) ---
if menu == "📊 Dashboard":
    st.subheader("📊 System Health & Financial Analytics")
    
    if not df_inv.empty:
        v_col = next((c for c in df_inv.columns if 'value' in c.lower()), None)
        q_col = next((c for c in df_inv.columns if 'qty' in c.lower() or 'total' in c.lower()), None)
        f_col = next((c for c in df_inv.columns if 'func' in c.lower()), None)
        c_col = df_inv.columns[0]
        
        # --- TOP LEVEL METRICS ---
        m1, m2, m3 = st.columns(3)
        total_value = df_inv[v_col].sum() if v_col else 0
        m1.metric("Total Asset Value", f"{total_value:,.2f} Br")
        
        total_assets = df_inv[q_col].sum() if q_col else 0
        m2.metric("Total Assets (Qty)", int(total_assets))
        
        health = (df_inv[f_col].sum() / total_assets * 100) if total_assets > 0 else 0
        m3.metric("System Health", f"{health:.1f}%")

        st.divider()

        # --- VISUAL ANALYTICS ---
        l, r = st.columns(2)
        with l:
            st.markdown("#### 💰 Value Distribution by Category")
            fig_v = px.pie(df_inv, values=v_col, names=c_col, hole=0.4, 
                           color_discrete_sequence=px.colors.qualitative.Prism)
            st.plotly_chart(fig_v, use_container_width=True)

        with r:
            st.markdown("#### 🛠️ Operational Health Score (%)")
            h_df = df_inv.groupby(c_col).agg({q_col: 'sum', f_col: 'sum'}).reset_index()
            h_df['Health %'] = (h_df[f_col] / h_df[q_col] * 100).round(1)
            h_df = h_df.sort_values('Health %')
            fig_h = px.bar(h_df, x='Health %', y=c_col, orientation='h', color='Health %', 
                           color_continuous_scale='RdYlGn', range_color=[0, 100])
            st.plotly_chart(fig_h, use_container_width=True)

        st.divider()
        st.markdown("#### 🔍 Root Cause Analysis of Failures")
        if not df_maint.empty:
            fig_sun = px.sunburst(df_maint, path=['Category', 'Subsystem', 'Failure Cause'], 
                                  color='Category', title="Failure Hierarchy")
            st.plotly_chart(fig_sun, use_container_width=True)

# --- 6. REGISTRY & INVENTORY (Standardized) ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 New Asset Registration")
    with st.form("reg_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        reg_cat = c1.selectbox("Category", list(AAE_STRUCTURE.keys()))
        reg_sub = c2.selectbox("Subsystem", AAE_STRUCTURE[reg_cat])
        code = st.text_input("Asset Code")
        qty = st.number_input("Quantity", min_value=1)
        cost = st.number_input("Unit Cost (ETB)", min_value=0.0)
        if st.form_submit_button("✅ Register"):
            # Recalculate value before appending
            val = qty * cost
            inv_ws.append_row([reg_cat, reg_sub, code, "Nos", qty, qty, cost, val, 10, 0, 0])
            st.success(f"Registered {code} - Value: {val:,.2f} Br"); st.rerun()

elif menu == "🔎 Inventory Status":
    st.subheader("🔎 Master Registry")
    edited_df = st.data_editor(df_inv, use_container_width=True, hide_index=True)
    if st.button("💾 Sync and Recalculate Values"):
        v_col = next((c for c in edited_df.columns if 'value' in c.lower()), None)
        q_col = next((c for c in edited_df.columns if 'qty' in c.lower() or 'total' in c.lower()), None)
        u_col = next((c for c in edited_df.columns if 'unit cost' in c.lower() or 'unitcost' in c.lower()), None)
        if v_col and q_col and u_col:
            edited_df[v_col] = edited_df[q_col] * edited_df[u_col]
        inv_ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
        st.success("Synced successfully!"); st.rerun()

elif menu == "🛠️ Maintenance History":
    st.subheader("🛠️ Maintenance Technical Log")
    st.dataframe(df_maint, use_container_width=True)






































































































