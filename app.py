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

# --- 3. ENHANCED DATA ENGINE ---
def get_full_data(worksheet):
    if not worksheet: return pd.DataFrame()
    data = worksheet.get_all_values()
    if len(data) < 1: return pd.DataFrame()
    
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers).replace('', "0").dropna(how='all')
    
    # Internal keywords for critical logic (Search/Math)
    # We rename only for background logic, keeping original headers for display
    mapping = {
        'Category': ['category', 'cat'],
        'Subsystem': ['asset', 'subsystem', 'item'],
        'Quantity': ['qty', 'total', 'quantity'],
        'Functional Qty': ['func', 'working', 'operational'],
        'Non-Functional Qty': ['non', 'broken', 'failed']
    }
    
    # Helper to find column index by keyword
    def find_col(keywords):
        for i, h in enumerate(headers):
            if any(k in h.lower() for k in keywords):
                return h
        return None

    # Force math columns to numeric
    for k, v in mapping.items():
        actual_col = find_col(v)
        if actual_col:
            df[actual_col] = pd.to_numeric(df[actual_col], errors='coerce').fillna(0)
            
    return df, headers

df_inv, raw_headers = get_full_data(inv_ws)

# --- 4. UI SETTINGS ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
st.markdown("""
    <div style="background-color: #1E3A8A; padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 25px;">
        <h1 style="margin:0;">Addis Ababa-Adama Expressway</h1>
        <p style="margin:0;">Full Lifecycle Asset Inventory & Operational Status</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Inventory Operational Status", "📝 Register New Equipment"])

# --- 5. DASHBOARD ---
if menu == "📊 Smart Dashboard":
    if not df_inv.empty:
        # Dynamic Metric Search
        q_col = next((h for h in raw_headers if "qty" in h.lower() or "total" in h.lower()), None)
        f_col = next((h for h in raw_headers if "func" in h.lower() or "working" in h.lower()), None)
        
        if q_col and f_col:
            total = df_inv[q_col].sum()
            func = df_inv[f_col].sum()
            health = (func / total * 100) if total > 0 else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Overall System Health", f"{health:.1f}%")
            c2.metric("Total Assets", int(total))
            c3.metric("Down Assets", int(total - func))

        st.divider()
        st.subheader("📊 Operational Breakdown")
        cat_col = next((h for h in raw_headers if "cat" in h.lower()), raw_headers[0])
        chart_df = df_inv.groupby(cat_col).sum(numeric_only=True).reset_index()
        fig = px.bar(chart_df, x=cat_col, y=[f_col, q_col], barmode='group', title="Functional vs Total Units")
        st.plotly_chart(fig, use_container_width=True)

# --- 6. FULL INVENTORY OPERATIONAL STATUS ---
elif menu == "🔎 Inventory Operational Status":
    st.subheader("🔎 Full Asset Database & Conditional Status")
    
    if df_inv.empty:
        st.info("No equipment data found.")
    else:
        st.write("Below is the complete record of every asset. You can edit the operational status directly.")
        
        # Search bar
        search = st.text_input("Filter Entire Database (Category, Name, Code, etc.)...", "")
        filtered_df = df_inv[df_inv.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)]

        # Find critical columns for locking/auto-calc
        q_col = next((h for h in raw_headers if "qty" in h.lower() or "total" in h.lower()), "")
        f_col = next((h for h in raw_headers if "func" in h.lower() or "working" in h.lower()), "")
        nf_col = next((h for h in raw_headers if "non" in h.lower() or "broken" in h.lower()), "")

        # Display the FULL dataframe
        edited_df = st.data_editor(
            filtered_df,
            hide_index=True, 
            use_container_width=True,
            column_config={
                q_col: st.column_config.NumberColumn(disabled=True),
                nf_col: st.column_config.NumberColumn(disabled=True),
                # Protect metadata from accidental edits in this view
                raw_headers[0]: st.column_config.Column(disabled=True), # Category
                raw_headers[1]: st.column_config.Column(disabled=True)  # Subsystem
            }
        )

        if st.button("💾 Save All Changes to Cloud"):
            with st.spinner("Syncing to Google Sheets..."):
                f_idx = raw_headers.index(f_col) + 1
                nf_idx = raw_headers.index(nf_col) + 1
                
                for i, row in edited_df.iterrows():
                    sheet_row = int(filtered_df.index[i]) + 2
                    total_val = int(row[q_col])
                    f_val = min(int(row[f_col]), total_val)
                    
                    inv_ws.update_cell(sheet_row, f_idx, f_val)
                    inv_ws.update_cell(sheet_row, nf_idx, total_val - f_val)
                
                st.success("✅ Full Inventory Synced!")
                st.rerun()

# --- 7. REGISTRATION ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 New Asset Onboarding")
    
    cat = st.selectbox("Category", list(EQUIPMENT_STRUCTURE.keys()))
    sub = st.selectbox("Subsystem", EQUIPMENT_STRUCTURE[cat])
    
    with st.form("full_reg", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        code = c1.text_input("Asset Code (Tag)")
        unit = c2.selectbox("Unit", ["Nos", "Sets", "Meters", "Km"])
        qty = c3.number_input("Quantity", min_value=1, step=1)
        
        c4, c5, c6 = st.columns(3)
        cost = c4.number_input("Unit Cost ($)")
        life = c5.number_input("Useful Life (Years)", value=10)
        age = c6.number_input("Current Age (Years)", value=0)
        
        if st.form_submit_button("✅ Register Asset"):
            # Matches standard GSheet Format: Category, Subsystem, Code, Unit, Total Qty, Status, U-Cost, T-Val, Life, Age, Func Qty, Non-Func Qty
            new_row = [cat, sub, code, unit, qty, "Functional", cost, (qty*cost), life, age, qty, 0]
            inv_ws.append_row(new_row)
            st.success(f"Asset {code} ({sub}) added successfully!")
            st.rerun()














































































