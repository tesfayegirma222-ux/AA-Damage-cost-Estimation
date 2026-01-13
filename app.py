import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. SECURE CONNECTION ---
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    except:
        creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
    return gspread.authorize(creds)

# --- 2. INITIALIZE SHEETS (THE FIX) ---
def get_or_create_worksheets(sh):
    # Check for Inventory Sheet
    try:
        inv_ws = sh.worksheet("Inventory")
    except gspread.exceptions.WorksheetNotFound:
        inv_ws = sh.add_worksheet(title="Inventory", rows="100", cols="10")
        inv_ws.append_row(["Category", "Asset Name", "Asset Code", "Unit", "Quantity", 
                           "Status", "Unit Cost", "Total Asset Value", "Expected Service Life", "Current Asset Life"])
    
    # Check for Maintenance Sheet
    try:
        maint_ws = sh.worksheet("Maintenance")
    except gspread.exceptions.WorksheetNotFound:
        maint_ws = sh.add_worksheet(title="Maintenance", rows="100", cols="5")
        maint_ws.append_row(["Asset Code", "Root Cause", "Details", "Cost"])
        
    return inv_ws, maint_ws

# --- 3. UI LAYOUT ---
st.set_page_config(page_title="Asset Manager", layout="wide")
st.title("🚜 Electro-Mechanical Asset Management")

sheet_url = st.sidebar.text_input("Google Sheet URL", placeholder="Paste your URL here")

if not sheet_url:
    st.info("👋 Please paste your Google Sheet URL in the sidebar to begin.")
    st.stop()

# Load and Sync
client = get_gspread_client()
sh = client.open_by_url(sheet_url)
inventory_sheet, maint_sheet = get_or_create_worksheets(sh)

# Convert to DataFrames
df_inv = pd.DataFrame(inventory_sheet.get_all_records())
df_maint = pd.DataFrame(maint_sheet.get_all_records())

# --- DASHBOARD & FORMS ---
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📦 Inventory", "🛠️ Maintenance"])

with tab1:
    if not df_inv.empty:
        total_val = df_inv['Total Asset Value'].sum()
        st.metric("Total Enterprise Asset Value", f"${total_val:,.2f}")
        
        c1, c2 = st.columns(2)
        with c1:
            # Horizontal Bar: Category Health
            fig1 = px.bar(df_inv, y="Category", color="Status", orientation='h', 
                          title="Asset Condition by Category")
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            # Vertical Bar: Subsystem Life
            fig2 = px.bar(df_inv, x="Asset Name", y="Current Asset Life", 
                          title="Current Asset Age (Years)")
            st.plotly_chart(fig2, use_container_width=True)
            
        if not df_maint.empty:
            st.subheader("Root Cause Analysis")
            fig3 = px.pie(df_maint, names='Root Cause', title="Maintenance Drivers")
            st.plotly_chart(fig3)
    else:
        st.warning("Inventory is currently empty.")

# (Entry forms for Tab 2 and Tab 3 remain the same as previous code)
            


















