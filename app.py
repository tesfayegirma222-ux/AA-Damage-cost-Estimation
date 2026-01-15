import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. EQUIPMENT STRUCTURE ---
EQUIPMENT_MAP = {
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

# --- 2. SMART CONNECTION ---
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

# --- 3. DATA ENGINE (FIXES KEYERROR) ---
def get_clean_data(worksheet):
    if not worksheet: return pd.DataFrame()
    data = worksheet.get_all_values()
    if len(data) < 1: return pd.DataFrame()
    
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers).replace('', None).dropna(how='all')
    
    # --- AUTO-FIX HEADERS ---
    rename_logic = {
        'Category': ['cat', 'type'],
        'Asset Name': ['asset', 'item', 'subsystem', 'name'],
        'Quantity': ['qty', 'total', 'quantity'],
        'Functional Qty': ['func', 'working', 'ok'],
        'Non-Functional Qty': ['non', 'broken', 'down', 'fail']
    }
    
    new_cols = {}
    for standard_name, keywords in rename_logic.items():
        for actual_header in df.columns:
            if any(k in actual_header.lower() for k in keywords):
                new_cols[actual_header] = standard_name
                break
    
    df = df.rename(columns=new_cols)
    
    # Ensure math columns are numeric
    for col in ['Quantity', 'Functional Qty', 'Non-Functional Qty']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0 # Create it if it literally doesn't exist
            
    return df

df_inv = get_clean_data(inv_ws)

# --- 4. UI SETTINGS ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
st.markdown("""
    <div style="background-color: #1E3A8A; padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 25px;">
        <h1>Addis Ababa-Adama Expressway</h1>
        <p>Asset Inventory & Conditional Assessment</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Inventory Assessment", "📝 Register New Equipment"])

# --- 5. DASHBOARD ---
if menu == "📊 Smart Dashboard":
    if not df_inv.empty:
        t_qty = df_inv['Quantity'].sum()
        f_qty = df_inv['Functional Qty'].sum()
        health = (f_qty / t_qty * 100) if t_qty > 0 else 0
        
        st.metric("Total Operational Health", f"{health:.1f}%")
        
        chart_data = df_inv.groupby('Category').agg({'Functional Qty':'sum', 'Quantity':'sum'}).reset_index()
        chart_data['Health %'] = (chart_data['Functional Qty'] / chart_data['Quantity'].replace(0,1) * 100).round(1)
        
        fig = px.bar(chart_data, x='Health %', y='Category', orientation='h', range_x=[0, 105],
                     color='Health %', color_continuous_scale='RdYlGn', text='Health %')
        st.plotly_chart(fig, use_container_width=True)

# --- 6. ASSESSMENT (UNBREAKABLE VERSION) ---
elif menu == "🔎 Inventory Assessment":
    st.subheader("🔎 Operational Status Update")
    
    if df_inv.empty:
        st.info("No data found in the spreadsheet.")
    else:
        # Search bar logic using standard name
        search = st.text_input("Filter by Category or Asset", "")
        
        # We check if 'Asset Name' exists (it should now thanks to our rename logic)
        name_col = 'Asset Name' if 'Asset Name' in df_inv.columns else df_inv.columns[1]
        cat_col = 'Category' if 'Category' in df_inv.columns else df_inv.columns[0]
        
        filtered_df = df_inv[
            df_inv[name_col].astype(str).str.contains(search, case=False) |
            df_inv[cat_col].astype(str).str.contains(search, case=False)
        ]

        edited_df = st.data_editor(
            filtered_df[['Category', 'Asset Name', 'Quantity', 'Functional Qty', 'Non-Functional Qty']],
            hide_index=True, use_container_width=True,
            column_config={"Quantity": st.column_config.NumberColumn(disabled=True)}
        )

        if st.button("💾 Save Changes"):
            with st.spinner("Syncing..."):
                headers = inv_ws.row_values(1)
                # Find the actual indexes in the REAL sheet
                f_idx = next(i for i, h in enumerate(headers, 1) if "func" in h.lower())
                nf_idx = next(i for i, h in enumerate(headers, 1) if "non" in h.lower())
                
                for i, row in edited_df.iterrows():
                    sheet_row = int(filtered_df.index[i]) + 2
                    f_val = min(int(row['Functional Qty']), int(row['Quantity']))
                    inv_ws.update_cell(sheet_row, f_idx, f_val)
                    inv_ws.update_cell(sheet_row, nf_idx, int(row['Quantity']) - f_val)
                
                st.success("✅ Database Updated!")
                st.rerun()

# --- 7. REGISTRATION ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 Register New Asset")
    c = st.selectbox("Category", list(EQUIPMENT_MAP.keys()))
    s = st.selectbox("Subsystem", EQUIPMENT_MAP[c])
    with st.form("add_form"):
        q = st.number_input("Total Quantity", min_value=1)
        if st.form_submit_button("✅ Add to Inventory"):
            inv_ws.append_row([c, s, "", "Nos", q, "Functional", 0, 0, 10, 0, q, 0])
            st.success(f"Added {s}")
            st.rerun()












































































