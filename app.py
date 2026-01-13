import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. ASSET DATA STRUCTURE (UNTOUCHED) ---
ASSET_CATEGORIES = {
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

# --- 2. AUTH & CONNECTION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        url = st.secrets["SHEET_URL"]
        return client.open_by_url(url)
    except Exception as e:
        st.error(f"Configuration Error: {e}")
        st.stop()

# --- 3. UI ENHANCEMENTS (SMART CSS) ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    h1 { color: #1E3A8A; font-family: 'Helvetica Neue', sans-serif; }
    .status-functional { color: #10B981; font-weight: bold; }
    .status-nonfunctional { color: #EF4444; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# Branding Header
col_logo, col_title = st.columns([1, 4])
with col_title:
    st.title("Addis Ababa-Adama Expressway")
    st.subheader("Electromechanical Asset Management Portal")

# Load Data
sh = init_connection()
# (Automatic Worksheet Check logic remains here...)
inv_ws = sh.worksheet("Inventory")
maint_ws = sh.worksheet("Maintenance")
df_inv = pd.DataFrame(inv_ws.get_all_records())
df_maint = pd.DataFrame(maint_ws.get_all_records())

# --- 4. NAVIGATION ---
tabs = st.tabs(["📊 Executive Dashboard", "🔎 Asset Browser", "📝 Register New", "🛠️ Log Maintenance"])

# --- TAB 1: EXECUTIVE DASHBOARD ---
with tabs[0]:
    if not df_inv.empty:
        # Smart KPIs
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Enterprise Value", f"${df_inv['Total Value'].sum():,.0f}")
        m2.metric("Health Index", f"{(len(df_inv[df_inv['Status']=='Functional'])/len(df_inv))*100:.1f}%")
        m3.metric("Critical Failures", len(df_inv[df_inv['Status']=='Non-Functional']))
        m4.metric("Aging Assets", len(df_inv[df_inv['Current Life'] >= df_inv['Expected Life']]))
        
        st.divider()
        
        # Visual Analytics
        c1, c2 = st.columns(2)
        with c1:
            fig1 = px.bar(df_inv, x="Category", color="Status", 
                          title="System Availability Status", barmode="group",
                          color_discrete_map={"Functional": "#10B981", "Non-Functional": "#EF4444"})
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            fig2 = px.scatter(df_inv, x="Current Life", y="Total Value", color="Category", 
                              size="Quantity", hover_name="Asset Name", title="Asset Value vs. Lifecycle Stage")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("System Ready. No data found in registry.")

# --- TAB 2: ASSET BROWSER (NEW SMART FEATURE) ---
with tabs[1]:
    st.subheader("Inventory Explorer")
    search_query = st.text_input("🔍 Search by Asset Code or Subsystem")
    
    if not df_inv.empty:
        filtered_df = df_inv[df_inv.apply(lambda row: search_query.lower() in str(row).lower(), axis=1)]
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        
        # CSV Export
        csv = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Report (CSV)", data=csv, file_name="AAE_Asset_Report.csv", mime="text/csv")

# --- TAB 3: REGISTER NEW (FIXED DYNAMIC DROP DOWN) ---
with tabs[2]:
    st.subheader("Asset Registration")
    
    # Selection logic outside form for immediate reactivity
    cat_select = st.selectbox("System Category", list(ASSET_CATEGORIES.keys()))
    sub_options = ASSET_CATEGORIES[cat_select]
    
    with st.form("reg_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        sub_select = col1.selectbox("Subsystem", sub_options)
        asset_code = col2.text_input("Asset ID Code")
        
        qty = col1.number_input("Quantity", min_value=1)
        u_cost = col2.number_input("Unit Cost", min_value=0.0)
        
        e_life = col1.number_input("Expected Life (Yrs)", min_value=1)
        c_life = col2.number_input("Current Age (Yrs)", min_value=0)
        
        status = col1.select_slider("Functionality Status", options=["Non-Functional", "Functional"], value="Functional")
        unit = col2.selectbox("Unit", ["Nos", "Set", "Units", "Meters"])
        
        if st.form_submit_button("✅ Register Asset to Expressway Database"):
            inv_ws.append_row([cat_select, sub_select, asset_code, unit, qty, status, u_cost, qty*u_cost, e_life, c_life])
            st.success("Asset added successfully.")
            st.rerun()

# --- TAB 4: MAINTENANCE LOG ---
with tabs[3]:
    st.subheader("Maintenance History")
    if not df_inv.empty:
        with st.form("m_form", clear_on_submit=True):
            m_asset = st.selectbox("Asset Code", df_inv["Asset Code"].unique())
            m_cause = st.selectbox("Root Cause", ["Wear and Tear", "Power Surge", "Lack of Service", "Environmental", "Accidental"])
            m_desc = st.text_area("Work Description")
            m_cost = st.number_input("Repair Cost", min_value=0.0)
            
            if st.form_submit_button("🔧 Log Repair Work"):
                import datetime
                maint_ws.append_row([m_asset, str(datetime.date.today()), m_cause, m_desc, m_cost])
                st.success("Maintenance Record Saved.")
                st.rerun()
























