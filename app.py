import streamlit as st
import pandas as pd
import plotly.express as px
from gspread_pandas import Spread, Conf

# --- CONFIGURATION & ASSET STRUCTURE ---
ASSET_CATEGORIES = {
    "Electric Power Source": ["Electric Utility", "Generator"],
    "Electric Power Distribution": ["ATS", "Breakers", "Power Cable", "Main Breakers", "DP"],
    "UPS System": ["UPS", "UPS Battery"],
    "CCTV System": ["Lane Camera", "Booth Camera", "Road Camera", "Plaza Camera"],
    "Auto-Railing System": ["Barrier Gate", "Controller"],
    "HVAC System": ["Air Conditioning System"],
    "Illumination System": ["High Mast Light", "Compound Light", "Road Light", "Booth Light", "Plaza Light"],
    "Electronic Display System": ["Canopy Light", "VMS", "LED Notice Board", "Fog Light", "Money Fee Display", "Passage Signal Lamp"],
    "Pump System": ["Surface Water Pump", "Submersible Pump"],
    "WIM System": ["Weight-In-Motion Sensor", "WIM Controller"]
}

# --- GOOGLE SHEETS CONNECTION ---
# Note: In a real app, use st.secrets for credentials
def load_data():
    # Replace with your actual Spreadsheet ID or Name
    # spread = Spread("Your_Spreadsheet_Name")
    # inventory_df = spread.sheet_to_df(index=0, sheet='Inventory')
    # maint_df = spread.sheet_to_df(index=0, sheet='Maintenance')
    
    # Mock data for demonstration purposes
    inventory_data = {
        'Category': ['UPS System', 'Electric Power Source'],
        'Asset Name': ['UPS-01', 'Gen-01'],
        'Asset Code': ['UPS-101', 'GEN-202'],
        'Unit': ['Nos', 'Nos'],
        'Quantity': [2, 1],
        'Status': ['Functional', 'Non-Functional'],
        'Unit Cost': [5000, 15000],
        'Total Value': [10000, 15000],
        'Expected Life': [10, 15],
        'Current Life': [4, 16]
    }
    return pd.DataFrame(inventory_data), pd.DataFrame()

# --- APP LAYOUT ---
st.set_page_config(page_title="Electro-Mech Asset Manager", layout="wide")
st.title("⚙️ Electro-Mechanical Asset Management System")

tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "➕ Asset Entry", "🛠️ Maintenance Log"])

# --- TAB 1: DASHBOARD ---
with tab1:
    inv_df, maint_df = load_data()
    
    col1, col2 = st.columns(2)
    with col1:
        total_value = inv_df['Total Value'].sum()
        st.metric("Total Enterprise Asset Value", f"${total_value:,}")
    
    st.divider()
    
    # Horizontal Bar Chart: Asset Condition by Category
    cond_df = inv_df.groupby(['Category', 'Status']).size().reset_index(name='Count')
    fig_cat = px.bar(cond_df, x='Count', y='Category', color='Status', 
                     orientation='h', title="Asset Condition by Category",
                     color_discrete_map={'Functional': '#2ecc71', 'Non-Functional': '#e74c3c'})
    st.plotly_chart(fig_cat, use_container_width=True)

    # Vertical Bar Chart: Subsystem Condition
    fig_sub = px.bar(inv_df, x='Asset Name', y='Current Life', color='Status',
                     title="Asset Lifecycle Status (Current Age)")
    st.plotly_chart(fig_sub, use_container_width=True)

# --- TAB 2: ASSET ENTRY ---
with tab2:
    st.header("Register New Asset")
    with st.form("asset_form"):
        col_a, col_b = st.columns(2)
        category = col_a.selectbox("Main System", list(ASSET_CATEGORIES.keys()))
        subsystem = col_a.selectbox("Subsystem", ASSET_CATEGORIES[category])
        asset_code = col_b.text_input("Asset Code (e.g., GEN-001)")
        
        status = col_a.radio("Functionality Status", ["Functional", "Non-Functional"])
        qty = col_b.number_input("Total Quantity", min_value=1)
        u_cost = col_b.number_input("Unit Cost", min_value=0.0)
        
        if st.form_submit_button("Save Asset to Google Sheets"):
            # Logic to append row to Google Sheet
            st.success(f"Asset {asset_code} recorded successfully!")

# --- TAB 3: MAINTENANCE LOG ---
with tab3:
    st.header("Maintenance History & Root Cause Analysis")
    with st.expander("Add Maintenance Record"):
        m_asset = st.selectbox("Select Asset for Maintenance", inv_df['Asset Code'].unique())
        m_date = st.date_input("Date of Maintenance")
        m_root_cause = st.selectbox("Root Cause", ["Wear and Tear", "Power Surge", "Lack of Service", "Environmental", "Accidental"])
        m_desc = st.text_area("Work Performed")
        
        if st.form_submit_button("Log Maintenance"):
            st.info("Record logged.")

    st.subheader("Root Cause Analysis (RCA)")
    # Sample RCA Visualization
    rca_data = pd.DataFrame({'Cause': ["Wear and Tear", "Power Surge"], 'Count': [10, 3]})
    fig_rca = px.pie(rca_data, values='Count', names='Cause', title="Maintenance Root Cause Distribution")
    st.plotly_chart(fig_rca)
            
















