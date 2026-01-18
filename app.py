import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. AAE OFFICIAL HIERARCHY ---
AAE_STRUCTURE = {
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

FAIL_CAUSES = ["Power Surge", "Wear & Tear", "Vandalism", "Accident", "Environmental (Dust/Heat)", "Software Error", "Battery Failure", "Unknown"]

# --- 2. SECURE CONNECTION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(st.secrets["SHEET_URL"])
        
        # Get Inventory Sheet
        inv = next((s for s in sh.worksheets() if "inventory" in s.title.lower()), sh.get_worksheet(0))
        
        # Get or Create Maintenance Sheet
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
    df = pd.DataFrame(data[1:], columns=data[0])
    
    # Numeric conversion for Inventory
    for col in df.columns:
        if any(k in col.lower() for k in ['qty', 'total', 'cost', 'value', 'life', 'age', 'func', 'non']):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

# --- 4. UI SETUP ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
df_inv = load_data(inv_ws)
df_maint = load_data(maint_ws)

st.markdown("""
    <div style="background: #1E3A8A; color: white; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
        <h2 style="margin:0;">Addis Ababa-Adama Expressway</h2>
        <p style="margin:0;">Electromechanical Master Database & Maintenance Log</p>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["🔎 Inventory Status", "📝 Register New Equipment", "🛠️ Maintenance History", "📊 Dashboard"])

# --- 5. MODULE: INVENTORY (Shortened for brevity, remains same as previous) ---
if menu == "🔎 Inventory Status":
    st.subheader("🔎 Master Registry")
    if df_inv.empty: st.warning("Database empty.")
    else:
        edited_df = st.data_editor(df_inv, use_container_width=True, hide_index=True)
        if st.button("💾 Sync Inventory"):
            inv_ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
            st.success("Synced!"); st.rerun()

# --- 6. MODULE: REGISTRATION ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 New Asset Onboarding")
    with st.form("reg_form"):
        c1, c2 = st.columns(2)
        cat = c1.selectbox("Category", list(AAE_STRUCTURE.keys()))
        sub = c2.selectbox("Subsystem", AAE_STRUCTURE[cat])
        code = st.text_input("Asset Code")
        qty = st.number_input("Quantity", min_value=1)
        cost = st.number_input("Unit Cost (ETB)", min_value=0.0)
        if st.form_submit_button("Add Asset"):
            inv_ws.append_row([cat, sub, code, "Nos", qty, qty, cost, qty*cost, 10, 0, 0])
            st.success("Registered!"); st.rerun()

# --- 7. MODULE: MAINTENANCE HISTORY (NEW) ---
elif menu == "🛠️ Maintenance History":
    st.subheader("🛠️ Failure Reporting & Logs")
    
    with st.expander("➕ Log New Equipment Failure", expanded=True):
        with st.form("maint_form"):
            col1, col2, col3 = st.columns(3)
            m_cat = col1.selectbox("Category", list(AAE_STRUCTURE.keys()), key="m_cat")
            m_sub = col2.selectbox("Subsystem", AAE_STRUCTURE[m_cat], key="m_sub")
            m_code = col3.text_input("Asset Code (e.g. AAE-CCTV-001)")
            
            col4, col5 = st.columns(2)
            m_cause = col4.selectbox("Root Cause of Failure", FAIL_CAUSES)
            m_tech = col5.text_input("Reported By / Technician")
            
            if st.form_submit_button("🚨 Submit Failure Report"):
                new_entry = [datetime.now().strftime("%Y-%m-%d"), m_cat, m_sub, m_code, m_cause, m_tech, "Pending"]
                maint_ws.append_row(new_entry)
                st.success("Failure logged in history!"); st.rerun()
    
    st.divider()
    st.write("### Recent Maintenance Logs")
    st.dataframe(df_maint, use_container_width=True)

# --- 8. DASHBOARD (UPDATED WITH RCA) ---
elif menu == "📊 Dashboard":
    st.subheader("📊 System Health & Root Cause Analysis")
    
    if not df_inv.empty:
        # Inventory Metrics
        v_c = next((c for c in df_inv.columns if 'value' in c.lower()), None)
        tot_v = df_inv[v_c].sum() if v_c else 0
        st.metric("Total System Value", f"{tot_v:,.2f} Br")
        
        st.divider()
        
        row1_col1, row1_col2 = st.columns(2)
        
        with row1_col1:
            # 1. Financial Distribution
            st.plotly_chart(px.pie(df_inv, values=v_c, names=df_inv.columns[0], hole=.4, title="Asset Value by Category"), use_container_width=True)
        
        with row1_col2:
            # 2. ROOT CAUSE ANALYSIS (The requested feature)
            st.markdown("#### 🔍 Root Cause Analysis (%)")
            if not df_maint.empty:
                rca_counts = df_maint['Failure Cause'].value_counts().reset_index()
                rca_counts.columns = ['Cause', 'Count']
                fig_rca = px.pie(rca_counts, values='Count', names='Cause', 
                                title="Primary Reasons for Failure",
                                color_discrete_sequence=px.colors.sequential.Reds_r)
                st.plotly_chart(fig_rca, use_container_width=True)
            else:
                st.info("No failure data available yet for RCA.")

        st.divider()
        
        # 3. FAILURE HEATMAP BY CATEGORY
        if not df_maint.empty:
            st.markdown("#### 📈 Failure Frequency by System & Subsystem")
            fig_tree = px.treemap(df_maint, path=['Category', 'Subsystem', 'Failure Cause'], title="Maintenance Incident Mapping")
            st.plotly_chart(fig_tree, use_container_width=True)


































































































