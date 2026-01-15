import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIG ---
OFFICIAL_HEADERS = [
    "Category", "Subsystem", "Asset Code", "Unit", "Total Qty", 
    "Status", "Unit Cost", "Total Value", "Life", "Age", 
    "Functional Qty", "Non-Functional Qty"
]

# --- 2. CONNECTION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(st.secrets["SHEET_URL"])
        # Find sheet containing 'inventory'
        target = next((s for s in sh.worksheets() if "inventory" in s.title.lower()), sh.get_worksheet(0))
        return target
    except Exception as e:
        st.error(f"Link Error: {e}")
        return None

inv_ws = init_connection()

# --- 3. THE "FORCE DISPLAY" ENGINE ---
def load_live_data(worksheet):
    if not worksheet: return pd.DataFrame()
    
    # 1. Get raw data
    raw_data = worksheet.get_all_values()
    if len(raw_data) < 2: return pd.DataFrame()
    
    # 2. Create DataFrame with existing headers
    df = pd.DataFrame(raw_data[1:], columns=raw_data[0])
    
    # 3. Handle Missing Columns (Prevents registered items from disappearing)
    for col in OFFICIAL_HEADERS:
        if col not in df.columns:
            df[col] = "0"
            
    # 4. Final Cleanup: Convert empty strings to 0 for math columns
    num_cols = ["Total Qty", "Unit Cost", "Total Value", "Functional Qty", "Non-Functional Qty"]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

# --- 4. UI ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")

# This forces the app to reload the sheet whenever the user switches tabs
df = load_live_data(inv_ws)

st.markdown("""
    <div style="background: #1E3A8A; color: white; padding: 15px; border-radius: 10px; text-align: center;">
        <h2>Addis Ababa-Adama Expressway</h2>
        <p>Master Asset Database (Live Sync)</p>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["🔎 Inventory Operational Status", "📝 Register New Equipment", "📊 Dashboard"])

# --- 5. INVENTORY STATUS (PRIMARY FIX) ---
if menu == "🔎 Inventory Operational Status":
    st.subheader("🔎 All Registered Assets")
    
    if df.empty:
        st.warning("Database is empty or could not be read.")
    else:
        # Show a summary count to prove the app sees the data
        st.info(f"Total Records Found: {len(df)}")
        
        search = st.text_input("Search Assets...", "")
        filtered_df = df[df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)]

        # Display EVERYTHING to ensure nothing is hidden
        edited_df = st.data_editor(
            filtered_df,
            hide_index=True, 
            use_container_width=True,
            num_rows="dynamic" # Allows you to see if extra rows are there
        )

        if st.button("💾 Save Changes"):
            with st.spinner("Updating Cloud..."):
                # Save logic maps back to original Sheet Row
                for i, row in edited_df.iterrows():
                    sheet_row = int(filtered_df.index[i]) + 2
                    # Update only Functional/Non-Functional for speed
                    f_idx = list(df.columns).index("Functional Qty") + 1
                    nf_idx = list(df.columns).index("Non-Functional Qty") + 1
                    inv_ws.update_cell(sheet_row, f_idx, row["Functional Qty"])
                    inv_ws.update_cell(sheet_row, nf_idx, row["Non-Functional Qty"])
                st.success("✅ Database Updated!"); st.rerun()

# --- 6. REGISTRATION (WITH AUTO-REFRESH) ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 Add New Asset")
    with st.form("reg_form", clear_on_submit=True):
        cat = st.text_input("Category")
        sub = st.text_input("Subsystem")
        code = st.text_input("Asset Code")
        qty = st.number_input("Quantity", min_value=1)
        cost = st.number_input("Unit Cost")
        
        if st.form_submit_button("✅ Register & Sync"):
            # Ensure the row exactly matches your sheet columns
            # Column Order: Category, Subsystem, Asset Code, Unit, Total Qty, Status, Unit Cost, Total Value, Life, Age, Functional Qty, Non-Functional Qty
            new_row = [cat, sub, code, "Nos", qty, "New", cost, (qty*cost), 10, 0, qty, 0]
            inv_ws.append_row(new_row)
            st.success("Asset added to Google Sheet!")
            st.rerun() # This kills the current session and pulls the new data





















































































