import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. ASSET DATA STRUCTURE ---
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

# --- 2. AUTHENTICATION & CONNECTION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    except Exception as e:
        st.error("GCP Service Account Secrets not found. Ensure they are added to Streamlit Cloud.")
        st.stop()
    
    client = gspread.authorize(creds)
    
    if "SHEET_URL" in st.secrets:
        url = st.secrets["SHEET_URL"]
    else:
        st.warning("SHEET_URL not found in Secrets. Please add it to Streamlit Cloud.")
        st.stop()
        
    return client.open_by_url(url)

# --- 3. WORKSHEET INITIALIZATION ---
def get_worksheets(sh):
    try:
        inv_ws = sh.worksheet("Inventory")
    except:
        inv_ws = sh.add_worksheet(title="Inventory", rows="1000", cols="10")
        inv_ws.append_row(["Category", "Asset Name", "Asset Code", "Unit", "Quantity", 
                           "Status", "Unit Cost", "Total Value", "Expected Life", "Current Life"])
    
    try:
        maint_ws = sh.worksheet("Maintenance")
    except:
        maint_ws = sh.add_worksheet(title="Maintenance", rows="1000", cols="5")
        maint_ws.append_row(["Asset Code", "Date", "Root Cause", "Details", "Cost"])
        
    return inv_ws, maint_ws

# --- 4. UI SETUP ---
st.set_page_config(page_title="Asset Manager", layout="wide")
st.title("⚙️ Electro-Mechanical Asset Management")

sh = init_connection()
inv_ws, maint_ws = get_worksheets(sh)

df_inv = pd.DataFrame(inv_ws.get_all_records())
df_maint = pd.DataFrame(maint_ws.get_all_records())

tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "➕ Register Asset", "🛠️ Maintenance Log"])

# --- TAB 1: DASHBOARD ---
with tab1:
    if not df_inv.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Asset Value", f"${df_inv['Total Value'].sum():,.2f}")
        col2.metric("Offline Assets", len(df_inv[df_inv['Status'] == 'Non-Functional']))
        col3.metric("Critical Age Alerts", len(df_inv[df_inv['Current Life'] >= df_inv['Expected Life']]))

        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            # Horizontal Bar: Category Condition
            fig1 = px.bar(df_inv, y="Category", color="Status", orientation='h',
                          title="Asset Condition by Category",
                          color_discrete_map={"Functional": "#27ae60", "Non-Functional": "#e74c3c"})
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            # Vertical Bar: Subsystem Condition
            fig2 = px.bar(df_inv, x="Asset Name", y="Current Life", color="Category",
                          title="Subsystem Age Distribution")
            st.plotly_chart(fig2, use_container_width=True)

        if not df_maint.empty:
            st.subheader("Root Cause Analysis")
            fig3 = px.pie(df_maint, names='Root Cause', hole=0.3)
            st.plotly_chart(fig3)
    else:
        st.info("Inventory is empty.")

# --- TAB 2: REGISTER ASSET (FIXED DYNAMIC FILTERING) ---
with tab2:
    st.header("Asset Registration Form")
    
    # STEP 1: Main Category (OUTSIDE the form for reactivity)
    category_list = list(ASSET_CATEGORIES.keys())
    selected_cat = st.selectbox("1. Select Main System Category", category_list)

    # STEP 2: Filter the subsystems based on the selection above
    available_subsystems = ASSET_CATEGORIES[selected_cat]
    
    # STEP 3: The Form (For all other data)
    with st.form("registry_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        
        # This dropdown now only contains subsystems for the chosen category
        subsystem = col_a.selectbox("2. Select Asset Subsystem", available_subsystems)
        
        asset_code = col_b.text_input("Asset Code (e.g., GEN-001)")
        unit = col_a.selectbox("Unit", ["Nos", "Set", "Units", "Meters"])
        qty = col_b.number_input("Total Quantity", min_value=1, step=1)
        
        u_cost = col_a.number_input("Unit Cost", min_value=0.0)
        exp_life = col_b.number_input("Expected Service Life (Years)", min_value=1)
        
        cur_life = col_a.number_input("Current Asset Life (Years)", min_value=0)
        status = col_b.radio("Status", ["Functional", "Non-Functional"], horizontal=True)
        
        # Submit Button
        if st.form_submit_button("Save to Google Sheets"):
            total_val = qty * u_cost
            inv_ws.append_row([
                selected_cat, subsystem, asset_code, unit, 
                qty, status, u_cost, total_val, exp_life, cur_life
            ])
            st.success(f"Asset {asset_code} saved under {selected_cat} > {subsystem}")
            st.rerun()

# --- TAB 3: MAINTENANCE LOG ---
with tab3:
    st.header("Maintenance Log")
    if not df_inv.empty:
        with st.form("m_form", clear_on_submit=True):
            m_code = st.selectbox("Asset Code", df_inv["Asset Code"].unique())
            m_date = st.date_input("Date")
            m_cause = st.selectbox("Root Cause", ["Wear and Tear", "Electrical", "Environmental", "Operational"])
            m_detail = st.text_area("Details")
            m_cost = st.number_input("Cost", min_value=0.0)
            
            if st.form_submit_button("Submit Log"):
                maint_ws.append_row([m_code, str(m_date), m_cause, m_detail, m_cost])
                st.success("Logged.")
                st.rerun()























