import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. YOUR OFFICIAL EQUIPMENT HIERARCHY ---
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
        all_sheets = [ws.title for ws in sh.worksheets()]
        target = next((s for s in all_sheets if "inventory" in s.lower()), all_sheets[0])
        return sh.worksheet(target)
    except Exception as e:
        st.error(f"Spreadsheet Connection Error: {e}")
        return None

inv_ws = init_connection()

# --- 3. DATA ENGINE (ROBUST HEADER MAPPING) ---
def get_clean_data(worksheet):
    if not worksheet: return pd.DataFrame()
    data = worksheet.get_all_values()
    if len(data) < 1: return pd.DataFrame()
    
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers).replace('', None).dropna(how='all')
    
    # Map raw headers to our required labels to avoid KeyErrors
    mapping = {
        'Category': ['category', 'cat', 'group'],
        'Subsystem': ['asset', 'subsystem', 'item', 'name'],
        'Quantity': ['qty', 'total', 'quantity'],
        'Functional Qty': ['func', 'working', 'operational'],
        'Non-Functional Qty': ['non', 'broken', 'failed', 'faulty']
    }
    
    renamed_cols = {}
    for standard_name, keywords in mapping.items():
        for actual_header in df.columns:
            if any(k in actual_header.lower() for k in keywords):
                renamed_cols[actual_header] = standard_name
                break
    
    df = df.rename(columns=renamed_cols)
    
    # Force Numeric
    for col in ['Quantity', 'Functional Qty', 'Non-Functional Qty']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

df_inv = get_clean_data(inv_ws)

# --- 4. UI SETTINGS ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
st.markdown("""
    <div style="background-color: #1E3A8A; padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 25px;">
        <h1>Addis Ababa-Adama Expressway</h1>
        <p>Asset Management & Conditional Assessment</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Conditional Assessment", "📝 Register New Equipment"])

# --- 5. DASHBOARD ---
if menu == "📊 Smart Dashboard":
    if not df_inv.empty and 'Quantity' in df_inv.columns:
        total = df_inv['Quantity'].sum()
        func = df_inv['Functional Qty'].sum() if 'Functional Qty' in df_inv.columns else 0
        health = (func / total * 100) if total > 0 else 0
        
        st.metric("Overall System Health", f"{health:.1f}%")
        
        if 'Category' in df_inv.columns:
            chart_data = df_inv.groupby('Category').agg({'Functional Qty':'sum', 'Quantity':'sum'}).reset_index()
            chart_data['Health %'] = (chart_data['Functional Qty'] / chart_data['Quantity'].replace(0,1) * 100).round(1)
            
            fig = px.bar(chart_data, x='Health %', y='Category', orientation='h', range_x=[0, 105],
                         color='Health %', color_continuous_scale='RdYlGn', text='Health %')
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available. Please register equipment first.")

# --- 6. CONDITIONAL ASSESSMENT (DYNAMIC DISPLAY) ---
elif menu == "🔎 Conditional Assessment":
    st.subheader("🔎 Inventory Operational Status")
    
    if df_inv.empty:
        st.info("No equipment found in the database.")
    else:
        # Only show columns that exist to prevent KeyErrors
        display_cols = [c for c in ['Category', 'Subsystem', 'Quantity', 'Functional Qty', 'Non-Functional Qty'] if c in df_inv.columns]
        
        search = st.text_input("Search Assets...", "")
        filtered_df = df_inv[df_inv.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)]

        edited_df = st.data_editor(
            filtered_df[display_cols],
            hide_index=True, 
            use_container_width=True,
            column_config={"Quantity": st.column_config.NumberColumn(disabled=True)}
        )

        if st.button("💾 Sync Updates to Google Sheets"):
            with st.spinner("Updating Cloud..."):
                raw_headers = inv_ws.row_values(1)
                f_idx = next(i for i, h in enumerate(raw_headers, 1) if "func" in h.lower())
                nf_idx = next(i for i, h in enumerate(raw_headers, 1) if "non" in h.lower())
                
                for i, row in edited_df.iterrows():
                    sheet_row = int(filtered_df.index[i]) + 2
                    f_val = int(row['Functional Qty'])
                    inv_ws.update_cell(sheet_row, f_idx, f_val)
                    inv_ws.update_cell(sheet_row, nf_idx, int(row['Quantity']) - f_val)
                
                st.success("✅ Assessment Saved!")
                st.rerun()

# --- 7. REGISTRATION (WITH YOUR CUSTOM CATEGORIES) ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 Register New Hardware Asset")
    
    # Dynamic Selection based on YOUR hierarchy
    cat = st.selectbox("Select Major Category", list(EQUIPMENT_STRUCTURE.keys()))
    sub = st.selectbox("Select Subsystem", EQUIPMENT_STRUCTURE[cat])
    
    with st.form("add_form", clear_on_submit=True):
        qty = st.number_input("Total Quantity", min_value=1, step=1)
        if st.form_submit_button("✅ Add to System"):
            # Row format: Category, Subsystem, Code, Unit, Total Qty, Status, U-Cost, T-Val, Life, Age, Func Qty, Non-Func Qty
            new_row = [cat, sub, "", "Nos", qty, "Operational", 0, 0, 10, 0, qty, 0]
            inv_ws.append_row(new_row)
            st.success(f"Added {qty} units of {sub} to {cat}.")
            st.rerun()













































































