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
    df = pd.DataFrame(data[1:], columns=data[0])
    
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
        <p style="margin:0;">Electromechanical Master Database & RCA Analytics</p>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["🔎 Inventory Status", "📝 Register New Equipment", "🛠️ Maintenance History", "📊 Dashboard"])

# --- 5. MODULE: INVENTORY ---
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
            # Columns: Category, Subsystem, Code, Unit, Total Qty, Functional, Unit Cost, Total Value, Life, Age, Non-Func
            inv_ws.append_row([cat, sub, code, "Nos", qty, qty, cost, qty*cost, 10, 0, 0])
            st.success("Registered!"); st.rerun()

# --- 7. MODULE: MAINTENANCE HISTORY ---
elif menu == "🛠️ Maintenance History":
    st.subheader("🛠️ Failure Reporting & Logs")
    with st.expander("➕ Log New Equipment Failure", expanded=True):
        with st.form("maint_form"):
            col1, col2, col3 = st.columns(3)
            m_cat = col1.selectbox("Category", list(AAE_STRUCTURE.keys()))
            m_sub = col2.selectbox("Subsystem", AAE_STRUCTURE[m_cat])
            m_code = col3.text_input("Asset Code")
            col4, col5 = st.columns(2)
            m_cause = col4.selectbox("Root Cause of Failure", FAIL_CAUSES)
            m_tech = col5.text_input("Technician Name")
            if st.form_submit_button("🚨 Submit Failure Report"):
                new_entry = [datetime.now().strftime("%Y-%m-%d"), m_cat, m_sub, m_code, m_cause, m_tech, "Pending"]
                maint_ws.append_row(new_entry)
                st.success("Failure logged!"); st.rerun()
    st.dataframe(df_maint, use_container_width=True)

# --- 8. DASHBOARD (INVENTORY + RCA + SYSTEM HEALTH) ---
elif menu == "📊 Dashboard":
    st.subheader("📊 System Health & Root Cause Analysis")
    
    if not df_inv.empty:
        # Columns identification
        c_col = df_inv.columns[0]
        q_col = next((c for c in df_inv.columns if 'qty' in c.lower() or 'total' in c.lower()), None)
        f_col = next((c for c in df_inv.columns if 'func' in c.lower()), None)
        v_col = next((c for c in df_inv.columns if 'value' in c.lower()), None)

        # Metrics Row
        m1, m2, m3 = st.columns(3)
        m1.metric("Total System Value", f"{df_inv[v_col].sum():,.2f} Br")
        m2.metric("Total Assets", int(df_inv[q_col].sum()))
        m3.metric("Overall Health", f"{(df_inv[f_col].sum()/df_inv[q_col].sum()*100):.1f}%")

        st.divider()
        
        # Row 1: Health Bar and RCA Pie
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown("#### 🛠️ System Health by Category (%)")
            h_df = df_inv.groupby(c_col).agg({q_col: 'sum', f_col: 'sum'}).reset_index()
            h_df['Health %'] = (h_df[f_col] / h_df[q_col] * 100).round(1)
            h_df = h_df.sort_values(by='Health %')
            
            fig_health = px.bar(h_df, x='Health %', y=c_col, orientation='h',
                               text=h_df['Health %'].apply(lambda x: f'{x}%'),
                               color='Health %', color_continuous_scale='RdYlGn', range_color=[0, 100])
            st.plotly_chart(fig_health, use_container_width=True)

        with col_right:
            st.markdown("#### 🔍 Root Cause Analysis (%)")
            if not df_maint.empty:
                rca_counts = df_maint['Failure Cause'].value_counts().reset_index()
                rca_counts.columns = ['Cause', 'Count']
                fig_rca = px.pie(rca_counts, values='Count', names='Cause', hole=0.4,
                                color_discrete_sequence=px.colors.sequential.Reds_r)
                st.plotly_chart(fig_rca, use_container_width=True)
            else:
                st.info("Log failures in 'Maintenance History' to see RCA data.")

        st.divider()
        
        # Row 2: Treemap Distribution
        st.markdown("#### 🗺️ Asset Inventory Mapping")
        st.plotly_chart(px.treemap(df_inv, path=[c_col, df_inv.columns[1]], values=q_col), use_container_width=True)



































































































