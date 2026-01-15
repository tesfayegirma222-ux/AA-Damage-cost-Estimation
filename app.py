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

# --- 3. DATA ENGINE (FIXES THE "COLUMN NOT FOUND" ERROR) ---
def load_data(worksheet):
    if not worksheet: return pd.DataFrame()
    data = worksheet.get_all_values()
    if len(data) < 1: return pd.DataFrame()
    
    # FIND THE HEADER ROW (Skips empty rows at the top)
    header_idx = 0
    for i, row in enumerate(data):
        if any(cell.strip() for cell in row):
            header_idx = i
            break
            
    raw_headers = data[header_idx]
    clean_headers = []
    seen = {}
    for i, h in enumerate(raw_headers):
        h = str(h).strip() if h else f"Col_{i+1}"
        if h in seen:
            seen[h] += 1
            clean_headers.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            clean_headers.append(h)
            
    df = pd.DataFrame(data[header_idx+1:], columns=clean_headers)
    
    # Convert numeric columns
    for col in df.columns:
        if any(k in col.lower() for k in ['qty', 'total', 'cost', 'value', 'life', 'age', 'func', 'non']):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

# --- 4. UI SETUP ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
df = load_data(inv_ws)

st.markdown("""
    <div style="background: #1E3A8A; color: white; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
        <h2 style="margin:0;">Addis Ababa-Adama Expressway</h2>
        <p style="margin:0;">Electromechanical Master Database (Live Sync)</p>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["🔎 Inventory Operational Status", "📝 Register New Equipment", "📊 Dashboard"])

# --- 5. MODULE: INVENTORY OPERATIONAL STATUS ---
if menu == "🔎 Inventory Operational Status":
    st.subheader("🔎 Master Registry & Operational Health")
    if df.empty:
        st.warning("No data found. Please ensure your Google Sheet has headers in the first row.")
    else:
        search = st.text_input("Search Assets...", "")
        mask = df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        display_df = df[mask]

        edited_df = st.data_editor(display_df, hide_index=True, use_container_width=True, num_rows="dynamic")

        if st.button("💾 Sync Updates to Google Sheet"):
            with st.spinner("Syncing..."):
                for i, row in edited_df.iterrows():
                    sheet_row = int(display_df.index[i]) + 2
                    inv_ws.update(range_name=f"A{sheet_row}", values=[row.tolist()])
                st.success("✅ Database Updated!"); st.rerun()

# --- 6. MODULE: REGISTRATION ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 New Asset Onboarding")
    with st.form("aae_reg", clear_on_submit=True):
        col1, col2 = st.columns(2)
        category = col1.selectbox("Major Category", list(AAE_STRUCTURE.keys()))
        subsystem = col2.selectbox("Subsystem", AAE_STRUCTURE[category])
        
        col3, col4, col5 = st.columns(3)
        code = col3.text_input("Asset Code")
        unit = col4.selectbox("Unit", ["Nos", "Sets", "Meters", "Km"])
        qty = col5.number_input("Total Quantity", min_value=1)
        
        col6, col7 = st.columns(2)
        cost = col6.number_input("Unit Cost", min_value=0.0)
        life = col7.number_input("Useful Life (Years)", value=10)
        
        if st.form_submit_button("✅ Add Asset"):
            new_row = [category, subsystem, code, unit, qty, "Functional", cost, (qty*cost), life, 0, qty, 0]
            inv_ws.append_row(new_row)
            st.success("Asset added!"); st.rerun()

# --- 7. DASHBOARD (ENHANCED RESOLVER) ---
elif menu == "📊 Dashboard":
    st.subheader("📊 System Health Analytics")
    if not df.empty:
        # SEARCH FOR COLUMNS BY KEYWORD
        c_col = next((c for c in df.columns if 'cat' in c.lower()), None)
        s_col = next((c for c in df.columns if 'sub' in c.lower()), None)
        q_col = next((c for c in df.columns if 'qty' in c.lower() or 'total' in c.lower()), None)
        f_col = next((c for c in df.columns if 'func' in c.lower()), None)
        n_col = next((c for c in df.columns if 'non' in c.lower()), None)

        if c_col and s_col and q_col:
            m1, m2, m3 = st.columns(3)
            total_v = df[q_col].sum()
            broken_v = df[n_col].sum() if n_col else 0
            
            m1.metric("Total Assets", int(total_v))
            m2.metric("Operational", int(total_v - broken_v))
            m3.metric("Down Units (Maintenance)", int(broken_v), delta_color="inverse")

            st.divider()
            col_l, col_r = st.columns(2)
            with col_l:
                fig_sun = px.sunburst(df, path=[c_col, s_col], values=q_col, title="Asset Hierarchy Distribution")
                st.plotly_chart(fig_sun, use_container_width=True)
            with col_r:
                if f_col:
                    fig_bar = px.bar(df.groupby(c_col)[[f_col, q_col]].sum().reset_index(), 
                                     x=c_col, y=[f_col, q_col], barmode='group', title="Functional vs Total")
                    st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.error("🚨 Dashboard Column Error")
            st.write("Current headers detected in your Google Sheet:")
            st.code(list(df.columns))
            st.warning("Please ensure your Google Sheet headers contain words like 'Category', 'Subsystem', and 'Qty'.")

























































































