import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. AAE OFFICIAL HIERARCHY ---
AAE_STRUCTURE = {
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
        sh = client.open_by_url(st.secrets["SHEET_URL"])
        target = next((s for s in sh.worksheets() if "inventory" in s.title.lower()), sh.get_worksheet(0))
        return target
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

inv_ws = init_connection()

# --- 3. DATA ENGINE (ROBUST COLUMN MAPPING) ---
def load_data(worksheet):
    if not worksheet: return pd.DataFrame()
    data = worksheet.get_all_values()
    if len(data) < 2: return pd.DataFrame()
    
    raw_headers = data[0]
    clean_headers = []
    seen = {}
    for i, h in enumerate(raw_headers):
        h = str(h).strip() if h else f"Col_{i}"
        if h in seen:
            seen[h] += 1
            clean_headers.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            clean_headers.append(h)
            
    df = pd.DataFrame(data[1:], columns=clean_headers)
    
    # Force Numeric for calculation columns
    for col in df.columns:
        if any(k in col.lower() for k in ['qty', 'total', 'cost', 'value', 'func', 'non']):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

# --- 4. UI SETUP ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
df = load_data(inv_ws)

st.markdown("""
    <div style="background: #1E3A8A; color: white; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
        <h2 style="margin:0;">Addis Ababa-Adama Expressway</h2>
        <p style="margin:0;">Electromechanical Master Database</p>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["🔎 Inventory Operational Status", "📝 Register New Equipment", "📊 Dashboard"])

# --- 5. MODULE: INVENTORY OPERATIONAL STATUS ---
if menu == "🔎 Inventory Operational Status":
    st.subheader("🔎 Master Registry & Status")
    
    if df.empty:
        st.warning("No data found.")
    else:
        search = st.text_input("Search (Category, Subsystem, Code, etc.)", "")
        mask = df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        display_df = df[mask]

        edited_df = st.data_editor(
            display_df,
            hide_index=True, 
            use_container_width=True,
            num_rows="dynamic"
        )

        if st.button("💾 Sync Updates to Google Sheet"):
            with st.spinner("Updating..."):
                for i, row in edited_df.iterrows():
                    sheet_row = int(display_df.index[i]) + 2
                    inv_ws.update(range_name=f"A{sheet_row}", values=[row.tolist()])
                st.success("✅ Database Synced!"); st.rerun()

# --- 6. MODULE: REGISTRATION (AAE CATEGORIES) ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 New Asset Onboarding")
    
    with st.form("aae_reg", clear_on_submit=True):
        col1, col2 = st.columns(2)
        category = col1.selectbox("Major Category", list(AAE_STRUCTURE.keys()))
        subsystem = col2.selectbox("Subsystem", AAE_STRUCTURE[category])
        
        col3, col4, col5 = st.columns(3)
        code = col3.text_input("Asset Code (Tag)")
        unit = col4.selectbox("Unit", ["Nos", "Sets", "Meters", "Km"])
        qty = col5.number_input("Total Quantity", min_value=1)
        
        col6, col7 = st.columns(2)
        cost = col6.number_input("Unit Cost", min_value=0.0)
        life = col7.number_input("Useful Life (Years)", value=10)
        
        if st.form_submit_button("✅ Add to Master Database"):
            # Ensure this list matches your sheet's column order exactly
            # Cat, Sub, Code, Unit, Total Qty, Status, Cost, Total Val, Life, Age, Func Qty, Non-Func Qty
            new_row = [category, subsystem, code, unit, qty, "Functional", cost, (qty*cost), life, 0, qty, 0]
            inv_ws.append_row(new_row)
            st.success("Registered Successfully!"); st.rerun()

# --- 7. DASHBOARD (FIXED ERROR) ---
elif menu == "📊 Dashboard":
    st.subheader("📊 System Health Analytics")
    if not df.empty:
        # DYNAMIC COLUMN FINDER to prevent Plotly errors
        cat_col = next((c for c in df.columns if 'category' in c.lower()), None)
        sub_col = next((c for c in df.columns if 'subsystem' in c.lower()), None)
        qty_col = next((c for c in df.columns if 'qty' in c.lower() or 'total' in c.lower()), None)

        if cat_col and sub_col and qty_col:
            fig = px.sunburst(df, path=[cat_col, sub_col], values=qty_col, 
                              title="Asset Distribution Hierarchy")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("Dashboard Error: Could not find Category, Subsystem, or Quantity columns in the data.")























































































