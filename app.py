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

# --- 3. DATA ENGINE ---
def load_data(worksheet):
    if not worksheet: return pd.DataFrame()
    data = worksheet.get_all_values()
    if len(data) < 1: return pd.DataFrame()
    
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
        <p style="margin:0;">Master Asset Database (Real-Time Sync)</p>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["🔎 Inventory Operational Status", "📝 Register New Equipment", "📊 Dashboard"])

# --- 5. MODULE: INVENTORY OPERATIONAL STATUS ---
if menu == "🔎 Inventory Operational Status":
    st.subheader("🔎 Master Registry Management")
    if df.empty:
        st.warning("Database is empty.")
    else:
        df_edit = df.copy()
        df_edit.insert(0, "🗑️", False)
        search = st.text_input("Search Assets...", "")
        mask = df_edit.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        display_df = df_edit[mask]

        edited_df = st.data_editor(display_df, hide_index=True, use_container_width=True, column_config={"🗑️": st.column_config.CheckboxColumn("Delete?")})

        c1, c2 = st.columns(2)
        if c1.button("💾 Save All Changes"):
            with st.spinner("Syncing..."):
                q_c = next((c for c in df.columns if 'total' in c.lower() or 'qty' in c.lower()), None)
                f_c = next((c for c in df.columns if 'func' in c.lower()), None)
                n_c = next((c for c in df.columns if 'non' in c.lower()), None)
                for i, row in edited_df.iterrows():
                    sheet_row = int(display_df.index[i]) + 2
                    if q_c and f_c and n_c:
                        row[n_c] = row[q_c] - row[f_c]
                    row_to_save = row.drop("🗑️").tolist()
                    inv_ws.update(range_name=f"A{sheet_row}", values=[row_to_save])
                st.success("Changes synced!"); st.rerun()

        if c2.button("🗑️ Delete Selected Assets", type="primary"):
            to_del = edited_df[edited_df["🗑️"] == True].index.tolist()
            if to_del:
                for idx in sorted(to_del, reverse=True):
                    inv_ws.delete_rows(idx + 2)
                st.success("Records deleted!"); st.rerun()

# --- 6. MODULE: REGISTRATION (FIXED DYNAMIC DROPDOWNS) ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 New Asset Onboarding")
    
    # These must be OUTSIDE the form to trigger the subsystem update
    col_cat, col_sub = st.columns(2)
    sel_cat = col_cat.selectbox("Major Category", list(AAE_STRUCTURE.keys()))
    sel_sub = col_sub.selectbox("Subsystem", AAE_STRUCTURE[sel_cat])
    
    with st.form("aae_reg", clear_on_submit=True):
        col3, col4, col5 = st.columns(3)
        code = col3.text_input("Asset Code")
        unit = col4.selectbox("Unit", ["Nos", "Sets", "Meters", "Km"])
        qty = col5.number_input("Total Quantity", min_value=1)
        
        col6, col7 = st.columns(2)
        cost = col6.number_input("Unit Cost", min_value=0.0)
        life = col7.number_input("Useful Life (Years)", value=10)
        
        if st.form_submit_button("✅ Add Asset"):
            # Columns 1-12 mapping
            new_row = [sel_cat, sel_sub, code, unit, qty, "Functional", cost, (qty*cost), life, 0, qty, 0]
            inv_ws.append_row(new_row)
            st.success("Asset added!"); st.rerun()

# --- 7. DASHBOARD ---
elif menu == "📊 Dashboard":
    st.subheader("📊 System Health Analytics")
    if not df.empty:
        c_c = next((c for c in df.columns if 'cat' in c.lower()), None)
        s_c = next((c for c in df.columns if 'sub' in c.lower()), None)
        q_c = next((c for c in df.columns if 'qty' in c.lower() or 'total' in c.lower()), None)
        n_c = next((c for c in df.columns if 'non' in c.lower()), None)
        if c_c and s_c and q_c:
            m1, m2, m3 = st.columns(3)
            tot = df[q_c].sum()
            bad = df[n_c].sum() if n_c else 0
            m1.metric("Total Assets", int(tot))
            m2.metric("Operational", int(tot - bad))
            m3.metric("Faulty (Col 12)", int(bad), delta_color="inverse")
            st.divider()
            l, r = st.columns(2)
            with l: st.plotly_chart(px.sunburst(df, path=[c_c, s_c], values=q_c, title="Asset Distribution"), use_container_width=True)
            with r: st.plotly_chart(px.bar(df.groupby(c_c)[q_c].sum().reset_index(), x=c_c, y=q_c, title="Category Counts"), use_container_width=True)






























































































