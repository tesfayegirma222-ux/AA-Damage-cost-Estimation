import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import datetime

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

# --- 2. THEMED HEADER & NAVIGATION ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")

# Custom CSS for Blue Header and Styling
st.markdown("""
    <style>
    .main-header {
        background-color: #1E3A8A;
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
    }
    .stMetric {
        background-color: #ffffff;
        border-left: 5px solid #1E3A8A;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    </style>
    <div class="main-header">
        <h1>Addis Ababa-Adama Expressway</h1>
        <p>Electromechanical Asset Management System</p>
    </div>
    """, unsafe_allow_html=True)

# Sidebar Navigation Menu
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/highway.png", width=80)
    st.title("Navigation")
    menu = st.radio(
        "Select Module",
        ["📊 Dashboard", "🔎 Asset Browser", "📝 Register New Asset", "🛠️ Maintenance Log"]
    )
    st.divider()
    st.info("Authorized Personnel Only")

# --- 3. AUTH & CONNECTION ---
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

sh = init_connection()
# Access worksheets (Assumes they are named 'Inventory' and 'Maintenance')
inv_ws = sh.worksheet("Inventory")
maint_ws = sh.worksheet("Maintenance")
df_inv = pd.DataFrame(inv_ws.get_all_records())
df_maint = pd.DataFrame(maint_ws.get_all_records())

# --- 4. MODULE LOGIC ---

# MODULE 1: DASHBOARD
if menu == "📊 Dashboard":
    if not df_inv.empty:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Asset Value", f"${df_inv['Total Value'].sum():,.0f}")
        m2.metric("Operational Health", f"{(len(df_inv[df_inv['Status']=='Functional'])/len(df_inv))*100:.1f}%")
        m3.metric("Critical Failures", len(df_inv[df_inv['Status']=='Non-Functional']))
        m4.metric("Aging Assets", len(df_inv[df_inv['Current Life'] >= df_inv['Expected Life']]))
        
        st.divider()
        col_left, col_right = st.columns(2)
        with col_left:
            fig1 = px.bar(df_inv, y="Category", color="Status", orientation='h', 
                          title="System Condition by Category",
                          color_discrete_map={"Functional": "#10B981", "Non-Functional": "#EF4444"})
            st.plotly_chart(fig1, use_container_width=True)
        with col_right:
            fig2 = px.bar(df_inv, x="Asset Name", y="Current Life", color="Category", 
                          title="Subsystem Life Distribution (Years)")
            st.plotly_chart(fig2, use_container_width=True)
            
        if not df_maint.empty:
            st.subheader("Root Cause Analysis (Maintenance History)")
            fig3 = px.pie(df_maint, names='Root Cause', hole=0.4, color_discrete_sequence=px.colors.qualitative.Bold)
            st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No data available. Please register assets.")

# MODULE 2: ASSET BROWSER
elif menu == "🔎 Asset Browser":
    st.subheader("Search & Export Inventory")
    search = st.text_input("🔍 Search by Asset Code, Category, or Name")
    if not df_inv.empty:
        mask = df_inv.apply(lambda row: search.lower() in str(row).lower(), axis=1)
        filtered_df = df_inv[mask]
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        st.download_button("📥 Export CSV", data=filtered_df.to_csv(index=False), file_name="AAE_Inventory.csv")

# MODULE 3: REGISTER NEW ASSET
elif menu == "📝 Register New Asset":
    st.subheader("Asset Registration Registry")
    # Dynamic logic for subsystems
    selected_cat = st.selectbox("1. Main Category", list(ASSET_CATEGORIES.keys()))
    sub_options = ASSET_CATEGORIES[selected_cat]
    
    with st.form("reg_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        subsystem = c1.selectbox("2. Subsystem", sub_options)
        code = c2.text_input("Asset Code (Unique ID)")
        qty = c1.number_input("Quantity", min_value=1)
        u_cost = c2.number_input("Unit Cost", min_value=0.0)
        exp_life = c1.number_input("Expected Life (Yrs)", min_value=1)
        cur_life = c2.number_input("Current Age (Yrs)", min_value=0)
        unit = c1.selectbox("Unit", ["Nos", "Set", "Units", "Meters"])
        status = c2.radio("Functionality Status", ["Functional", "Non-Functional"], horizontal=True)
        
        if st.form_submit_button("Save to Registry"):
            inv_ws.append_row([selected_cat, subsystem, code, unit, qty, status, u_cost, qty*u_cost, exp_life, cur_life])
            st.success("Asset added successfully!")
            st.rerun()

# MODULE 4: MAINTENANCE LOG
elif menu == "🛠️ Maintenance Log":
    st.subheader("Maintenance History Recording")
    if not df_inv.empty:
        with st.form("maint_form", clear_on_submit=True):
            m_code = st.selectbox("Asset Code", df_inv["Asset Code"].unique())
            m_cause = st.selectbox("Root Cause", ["Wear and Tear", "Power Surge", "Lack of Service", "Environmental", "Accidental"])
            m_desc = st.text_area("Details of Work")
            m_cost = st.number_input("Repair Cost", min_value=0.0)
            if st.form_submit_button("Submit Maintenance Record"):
                maint_ws.append_row([m_code, str(datetime.date.today()), m_cause, m_desc, m_cost])
                st.success("Record Saved.")
                st.rerun()

























