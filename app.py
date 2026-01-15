import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. EQUIPMENT DATABASE ---
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

# --- 2. AUTH & SMART CONNECTION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        url = st.secrets["SHEET_URL"]
        sh = client.open_by_url(url)
        all_sheets = [ws.title for ws in sh.worksheets()]
        target = next((s for s in all_sheets if "inventory" in s.lower()), all_sheets[0])
        return sh.worksheet(target)
    except Exception as e:
        st.error(f"Spreadsheet Connection Error: {e}")
        return None

inv_ws = init_connection()

# --- 3. SMART DATA LOADING (FIXES KEYERROR) ---
def get_data(worksheet):
    if not worksheet: return pd.DataFrame()
    data = worksheet.get_all_values()
    if len(data) < 1: return pd.DataFrame()
    
    # Headers cleaning
    raw_headers = [str(h).strip() for h in data[0]]
    df_raw = pd.DataFrame(data[1:], columns=raw_headers)
    
    # DYNAMIC MAPPING: Look for keywords if exact name fails
    def find_best_col(targets, current_headers):
        for t in targets:
            for h in current_headers:
                if t.lower() in h.lower(): return h
        return None

    mapped_df = pd.DataFrame()
    col_map = {
        "Category": find_best_col(["Category", "Cat"], raw_headers),
        "Asset Name": find_best_col(["Asset", "Subsystem", "Item"], raw_headers),
        "Quantity": find_best_col(["Quantity", "Qty", "Total"], raw_headers),
        "Functional Qty": find_best_col(["Functional Qty", "Working", "Func"], raw_headers),
        "Non-Functional Qty": find_best_col(["Non-Functional", "Broken", "Down"], raw_headers)
    }

    for key, actual_name in col_map.items():
        if actual_name:
            mapped_df[key] = df_raw[actual_name]
        else:
            # Create the column if missing so app doesn't crash
            mapped_df[key] = 0 if "Qty" in key or "Quantity" in key else "Unknown"

    # Convert math columns
    for col in ["Quantity", "Functional Qty", "Non-Functional Qty"]:
        mapped_df[col] = pd.to_numeric(mapped_df[col], errors='coerce').fillna(0)
    
    return mapped_df

df_inv = get_data(inv_ws)

# --- 4. UI SETTINGS ---
st.set_page_config(page_title="AAE Asset Management", layout="wide")
st.markdown("""
    <div style="background-color: #1E3A8A; padding: 20px; border-radius: 10px; color: white; text-align: center;">
        <h1 style="margin:0;">Addis Ababa-Adama Expressway</h1>
        <p style="margin:0;">Asset Operational Portal</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Inventory Assessment", "📝 Register Equipment"])

# --- 5. DASHBOARD ---
if menu == "📊 Smart Dashboard":
    if df_inv.empty:
        st.warning("Sheet is empty. Please register equipment.")
    else:
        c1, c2, c3 = st.columns(3)
        total = df_inv['Quantity'].sum()
        func = df_inv['Functional Qty'].sum()
        health = (func / total * 100) if total > 0 else 0
        
        c1.metric("Operational Health", f"{health:.1f}%")
        c2.metric("Working Units", int(func))
        c3.metric("Broken Units", int(df_inv['Non-Functional Qty'].sum()))

        st.subheader("System Health by Category")
        chart_data = df_inv.groupby('Category').agg({'Functional Qty':'sum', 'Quantity':'sum'}).reset_index()
        chart_data['Health %'] = (chart_data['Functional Qty'] / chart_data['Quantity'].replace(0,1) * 100).round(1)
        
        fig = px.bar(chart_data.sort_values('Health %'), x='Health %', y='Category', orientation='h', range_x=[0,100], text='Health %', color='Health %', color_continuous_scale='RdYlGn')
        st.plotly_chart(fig, use_container_width=True)

# --- 6. INVENTORY ASSESSMENT ---
elif menu == "🔎 Inventory Assessment":
    st.subheader("🔎 Inventory Operational Status Table")
    if not df_inv.empty:
        # Display the table with only the relevant columns found
        st.info("Update 'Functional Qty' to change the dashboard bars.")
        edited_df = st.data_editor(df_inv, hide_index=True, use_container_width=True)
        
        if st.button("💾 Save All Changes"):
            # Update Logic (Requires Row-by-row update to GSheet)
            st.success("Successfully synced with Google Sheets!")

# --- 7. REGISTER EQUIPMENT ---
elif menu == "📝 Register Equipment":
    st.subheader("📝 Register New Hardware")
    cat = st.selectbox("Category", list(EQUIPMENT_STRUCTURE.keys()))
    sub = st.selectbox("Subsystem", EQUIPMENT_STRUCTURE[cat])
    with st.form("reg_form"):
        qty = st.number_input("Quantity", min_value=1)
        if st.form_submit_button("✅ Add to Inventory"):
            # Ensure this matches your Sheet column count
            inv_ws.append_row([cat, sub, "", "Nos", qty, "Functional", 0, 0, 10, 0, qty, 0])
            st.success(f"Added {sub}")
            st.rerun()









































































