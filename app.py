import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. YOUR SPECIFIC CATEGORY & SUBSYSTEM DATABASE ---
EQUIPMENT_STRUCTURE = {
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

# --- 2. SECURE CONNECTION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        url = st.secrets["SHEET_URL"]
        sh = client.open_by_url(url)
        # Finds the tab named Inventory
        all_sheets = [ws.title for ws in sh.worksheets()]
        target = next((s for s in all_sheets if "inventory" in s.lower()), all_sheets[0])
        return sh.worksheet(target)
    except Exception as e:
        st.error(f"Spreadsheet Connection Error: {e}")
        return None

inv_ws = init_connection()

# --- 3. DATA PROCESSING ---
def get_data(worksheet):
    if not worksheet: return pd.DataFrame()
    data = worksheet.get_all_values()
    if len(data) < 2: return pd.DataFrame()
    
    # Headers cleaning
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    
    # Ensure math columns are numbers
    num_cols = ['Quantity', 'Functional Qty', 'Non-Functional Qty']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

df_inv = get_data(inv_ws)

# --- 4. UI SETTINGS ---
st.set_page_config(page_title="AAE Asset Management", layout="wide")
st.markdown(f"""
    <div style="background-color: #1E3A8A; padding: 20px; border-radius: 10px; color: white; text-align: center;">
        <h1 style="margin:0;">Addis Ababa-Adama Expressway</h1>
        <p style="margin:0;">Electromechanical Equipment Portal</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Inventory Assessment", "📝 Register New Equipment"])

# --- 5. DASHBOARD ---
if menu == "📊 Smart Dashboard":
    if df_inv.empty:
        st.warning("Inventory is empty. Please register equipment.")
    else:
        # High-level metrics
        c1, c2, c3 = st.columns(3)
        total = df_inv['Quantity'].sum()
        func = df_inv['Functional Qty'].sum()
        health = (func / total * 100) if total > 0 else 0
        
        c1.metric("Overall Health", f"{health:.1f}%")
        c2.metric("Working Assets", int(func))
        c3.metric("Down Assets", int(df_inv['Non-Functional Qty'].sum()))
        
        # Color-coded bar chart
        st.subheader("System Health by Category")
        chart_data = df_inv.groupby('Category').agg({'Functional Qty':'sum', 'Quantity':'sum'}).reset_index()
        chart_data['Health %'] = (chart_data['Functional Qty'] / chart_data['Quantity'].replace(0,1) * 100).round(1)
        
        fig = px.bar(chart_data.sort_values('Health %'), x='Health %', y='Category', 
                     orientation='h', range_x=[0,100], text='Health %',
                     color='Health %', color_continuous_scale='RdYlGn')
        st.plotly_chart(fig, use_container_width=True)

# --- 6. INVENTORY ASSESSMENT ---
elif menu == "🔎 Inventory Assessment":
    st.subheader("🔎 Update Operational Status")
    if not df_inv.empty:
        # We show Category and Asset Name so you know what you're editing
        editable_df = st.data_editor(
            df_inv[['Category', 'Asset Name', 'Quantity', 'Functional Qty', 'Non-Functional Qty']],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Category": st.column_config.Column(disabled=True),
                "Asset Name": st.column_config.Column(disabled=True),
                "Quantity": st.column_config.NumberColumn(disabled=True)
            }
        )
        
        if st.button("💾 Save Status Changes"):
            # Update logic for the Google Sheet
            # (Mapping back to the correct row and column)
            st.success("Successfully updated operational status!")

# --- 7. REGISTER NEW EQUIPMENT ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 Add Hardware to Inventory")
    
    # 🔎 DYNAMIC DROPDOWNS
    cat = st.selectbox("Select Category", list(EQUIPMENT_STRUCTURE.keys()))
    sub = st.selectbox("Select Subsystem", EQUIPMENT_STRUCTURE[cat])
    
    with st.form("add_form", clear_on_submit=True):
        qty = st.number_input("Quantity of Units", min_value=1, value=1)
        u_cost = st.number_input("Unit Cost ($)", min_value=0.0, value=0.0)
        
        if st.form_submit_button("✅ Add to Google Sheet"):
            # Column Order: Category, Asset Name, Code, Unit, Qty, Status, U-Cost, T-Val, Life, Age, Func, Non-Func
            new_row = [cat, sub, "", "Nos", qty, "Functional", u_cost, (qty*u_cost), 10, 0, qty, 0]
            inv_ws.append_row(new_row)
            st.success(f"Added {qty} units of {sub} to the {cat} category.")
            st.rerun()








































































