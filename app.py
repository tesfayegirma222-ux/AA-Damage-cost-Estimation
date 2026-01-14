import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- 1. CONFIGURATION ---
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

# --- 3. UI THEME ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
st.markdown("""
    <style>
    .main-header { background-color: #1E3A8A; padding: 25px; border-radius: 12px; color: white; text-align: center; margin-bottom: 25px; }
    .stMetric { background-color: #ffffff; border-left: 5px solid #1E3A8A; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    <div class="main-header">
        <h1>Addis Ababa-Adama Expressway</h1>
        <p style='font-size: 1.2rem;'>Electromechanical Asset Management System</p>
    </div>
    """, unsafe_allow_html=True)

with st.sidebar:
    logo_url = "https://img.icons8.com/fluency/96/highway.png" 
    st.image(logo_url, width=120)
    st.title("Main Menu")
    menu = st.radio("Select Module", ["📊 Dashboard", "📝 Register New Asset", "🔎 Conditional Assessment", "🛠️ Maintenance Log"])
    st.divider()
    st.info("System: AAE-EMS v12.0")

# --- 4. DATA HANDLING ---
sh = init_connection()
inv_ws = sh.worksheet("Inventory")

def get_safe_data():
    data = inv_ws.get_all_values()
    if not data: return pd.DataFrame()
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    
    # Numeric Safety
    num_cols = ['Quantity', 'Unit Cost', 'Total Value', 'Expected Life', 'Current Age', 'Functional Qty', 'Non-Functional Qty']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

df_inv = get_safe_data()

# --- 5. MODULE LOGIC ---

# DASHBOARD
if menu == "📊 Dashboard":
    if not df_inv.empty:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Enterprise Value", f"${df_inv['Total Value'].sum():,.2f}")
        
        total_q = df_inv['Quantity'].sum()
        func_q = df_inv['Functional Qty'].sum()
        health_pct = (func_q / total_q * 100) if total_q > 0 else 0
        m2.metric("Operational Health", f"{health_pct:.1f}%")
        
        m3.metric("Broken Assets", int(df_inv['Non-Functional Qty'].sum()))
        m4.metric("Aging Alerts", len(df_inv[df_inv['Current Age'] >= df_inv['Expected Life']]))

        st.divider()
        st.subheader("📊 System Health (Operational Status)")
        cat_sum = df_inv.groupby('Category').agg({'Functional Qty': 'sum', 'Quantity': 'sum'}).reset_index()
        cat_sum['Health %'] = (cat_sum['Functional Qty'] / (cat_sum['Quantity'].replace(0,1)) * 100).round(1)
        
        fig = px.bar(cat_sum.sort_values('Health %'), x='Health %', y='Category', orientation='h', 
                     range_x=[0, 100], text='Health %', color_discrete_sequence=['#22C55E'])
        fig.update_traces(texttemplate='%{text}%', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data found.")

# CONDITIONAL ASSESSMENT (FIXED SAVE)
elif menu == "🔎 Conditional Assessment":
    st.subheader("🔎 Edit Operational Quantities")
    
    if not df_inv.empty:
        # Create a copy for editing
        edit_cols = ["Category", "Asset Name", "Quantity", "Functional Qty", "Non-Functional Qty"]
        
        # DISPLAY DATA EDITOR
        edited_df = st.data_editor(
            df_inv[edit_cols],
            column_config={
                "Category": st.column_config.Column(disabled=True),
                "Asset Name": st.column_config.Column(disabled=True),
                "Quantity": st.column_config.NumberColumn("Total Registered"),
                "Functional Qty": st.column_config.NumberColumn("Functional ✅"),
                "Non-Functional Qty": st.column_config.NumberColumn("Broken ❌"),
            },
            hide_index=True,
            use_container_width=True,
            key="inventory_editor" # Key is essential for state
        )

        if st.button("💾 Save All Quantities"):
            with st.spinner("Writing to Database..."):
                try:
                    for index, row in edited_df.iterrows():
                        sheet_row = index + 2  # +1 for header, +1 for 0-indexing
                        
                        # Update columns: 5=Total Qty, 11=Functional, 12=Non-Functional
                        inv_ws.update_cell(sheet_row, 5, int(row['Quantity']))
                        inv_ws.update_cell(sheet_row, 11, int(row['Functional Qty']))
                        inv_ws.update_cell(sheet_row, 12, int(row['Non-Functional Qty']))
                        
                        # Auto-update status text (Column 6)
                        new_status = "Functional" if row['Functional Qty'] > 0 else "Non-Functional"
                        inv_ws.update_cell(sheet_row, 6, new_status)

                    st.success("✅ Success: Quantities saved to Google Sheets!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")
    else:
        st.warning("Inventory is empty.")





















































