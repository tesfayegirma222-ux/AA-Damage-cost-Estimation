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

# --- 3. DATA ENGINE (FIXES DUPLICATE/EMPTY HEADERS) ---
def get_full_data(worksheet):
    if not worksheet: return pd.DataFrame(), []
    data = worksheet.get_all_values()
    if len(data) < 1: return pd.DataFrame(), []
    
    # --- HEADER SANITIZATION ---
    raw_headers = data[0]
    clean_headers = []
    counts = {}
    
    for i, h in enumerate(raw_headers):
        h_str = str(h).strip()
        if h_str == "": h_str = f"Unnamed_{i}" # Fill empty headers
        
        # Handle duplicate names
        if h_str in counts:
            counts[h_str] += 1
            clean_headers.append(f"{h_str}_{counts[h_str]}")
        else:
            counts[h_str] = 0
            clean_headers.append(h_str)

    df = pd.DataFrame(data[1:], columns=clean_headers).dropna(how='all')
    
    # Identify critical columns for Dashboard logic using keywords
    def find_best_match(keywords):
        for h in clean_headers:
            if any(k in h.lower() for k in keywords): return h
        return None

    q_col = find_best_match(['qty', 'total', 'quantity'])
    f_col = find_best_match(['func', 'working', 'operational'])
    nf_col = find_best_match(['non', 'broken', 'failed'])

    # Ensure math columns are numeric
    for col in [q_col, f_col, nf_col]:
        if col:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df, clean_headers, q_col, f_col, nf_col

df_inv, headers, Q_COL, F_COL, NF_COL = get_full_data(inv_ws)

# --- 4. UI SETTINGS ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
st.markdown("""
    <div style="background-color: #1E3A8A; padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 25px;">
        <h1 style="margin:0;">Addis Ababa-Adama Expressway</h1>
        <p style="margin:0;">Electromechanical Asset Management System</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Inventory Operational Status", "📝 Register New Equipment"])

# --- 5. DASHBOARD ---
if menu == "📊 Smart Dashboard":
    if not df_inv.empty and Q_COL and F_COL:
        total = df_inv[Q_COL].sum()
        func = df_inv[F_COL].sum()
        health = (func / total * 100) if total > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Overall Health", f"{health:.1f}%")
        c2.metric("Operational", int(func))
        c3.metric("Maintenance Needed", int(total - func))

        st.divider()
        cat_col = headers[0] # Assuming first col is Category
        fig = px.bar(df_inv.groupby(cat_col).sum(numeric_only=True).reset_index(), 
                     x=cat_col, y=[F_COL, Q_COL], barmode='group', title="Status by Category")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Register items to view Dashboard analytics.")

# --- 6. INVENTORY OPERATIONAL STATUS (SAFE VERSION) ---
elif menu == "🔎 Inventory Operational Status":
    st.subheader("🔎 Asset Database")
    
    if df_inv.empty:
        st.info("No data found.")
    else:
        search = st.text_input("Search inventory...", "")
        mask = df_inv.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        filtered_df = df_inv[mask]

        # data_editor will now work because headers are unique strings
        edited_df = st.data_editor(
            filtered_df,
            hide_index=True, 
            use_container_width=True,
            column_config={
                Q_COL: st.column_config.NumberColumn(disabled=True) if Q_COL else None,
                NF_COL: st.column_config.NumberColumn(disabled=True) if NF_COL else None
            }
        )

        if st.button("💾 Save Changes"):
            if F_COL and NF_COL:
                with st.spinner("Syncing to Sheet..."):
                    # Match clean headers back to sheet indices
                    f_idx = headers.index(F_COL) + 1
                    nf_idx = headers.index(NF_COL) + 1
                    
                    for i, row in edited_df.iterrows():
                        sheet_row = int(filtered_df.index[i]) + 2
                        tot = int(row[Q_COL])
                        f_val = min(int(row[F_COL]), tot)
                        inv_ws.update_cell(sheet_row, f_idx, f_val)
                        inv_ws.update_cell(sheet_row, nf_idx, tot - f_val)
                    st.success("✅ Database Updated!")
                    st.rerun()
            else:
                st.error("Cannot save: 'Functional' or 'Non-Functional' columns not identified.")

# --- 7. REGISTRATION ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 Register Asset")
    cat = st.selectbox("Category", list(EQUIPMENT_STRUCTURE.keys()))
    sub = st.selectbox("Subsystem", EQUIPMENT_STRUCTURE[cat])
    
    with st.form("reg_form", clear_on_submit=True):
        code = st.text_input("Asset Code")
        qty = st.number_input("Quantity", min_value=1, step=1)
        if st.form_submit_button("✅ Register"):
            # Ensure this matches your Google Sheet's actual column count
            new_row = [cat, sub, code, "Nos", qty, "Functional", 0, 0, 10, 0, qty, 0]
            inv_ws.append_row(new_row)
            st.success("Added!"); st.rerun()















































































