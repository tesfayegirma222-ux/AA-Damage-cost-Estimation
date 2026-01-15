import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIG & HIERARCHY ---
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

OFFICIAL_HEADERS = [
    "Category", "Subsystem", "Asset Code", "Unit", "Total Qty", 
    "Status", "Unit Cost", "Total Value", "Life", "Age", 
    "Functional Qty", "Non-Functional Qty"
]

# --- 2. CONNECTION (FORCE REFRESH) ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(st.secrets["SHEET_URL"])
        all_sheets = [ws.title for ws in sh.worksheets()]
        target = next((s for s in all_sheets if "inventory" in s.lower()), all_sheets[0])
        return sh.worksheet(target)
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

# --- 3. DATA ENGINE ---
def load_live_data(worksheet):
    if not worksheet: return pd.DataFrame()
    # Fetch all data without caching to ensure new items show up
    data = worksheet.get_all_values()
    if len(data) < 2: return pd.DataFrame()
    
    # Clean and Standardize
    df = pd.DataFrame(data[1:], columns=data[0]).dropna(how='all')
    
    # Standardize column names to prevent mapping errors
    mapping = {raw: off for off in OFFICIAL_HEADERS for raw in df.columns 
               if off.lower().replace(" ","") == str(raw).lower().replace(" ","")}
    df = df.rename(columns=mapping)
    
    # Fill missing columns
    for col in OFFICIAL_HEADERS:
        if col not in df.columns:
            df[col] = 0 if any(x in col for x in ["Qty", "Cost", "Value", "Life", "Age"]) else ""
            
    # Convert Numbers
    num_cols = ["Total Qty", "Unit Cost", "Total Value", "Functional Qty", "Non-Functional Qty"]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df[OFFICIAL_HEADERS]

# --- 4. UI SETUP ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
inv_ws = init_connection()

st.markdown("""
    <style>
        .reportview-container { background: #F5F7F9; }
        .main-header { background: #1E3A8A; color: white; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px; }
    </style>
    <div class="main-header">
        <h1>Addis Ababa-Adama Expressway</h1>
        <p>Real-Time Asset Inventory System</p>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Inventory Operational Status", "📝 Register New Equipment"])

# --- 5. DASHBOARD ---
if menu == "📊 Smart Dashboard":
    df = load_live_data(inv_ws)
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        total = df["Total Qty"].sum()
        func = df["Functional Qty"].sum()
        health = (func/total*100) if total > 0 else 0
        c1.metric("System Health", f"{health:.1f}%")
        c2.metric("Total Items", int(total))
        c3.metric("Maintenance List", int(total - func))
        
        fig = px.bar(df.groupby("Category").sum(numeric_only=True).reset_index(), 
                     x="Category", y="Total Qty", title="Asset Count by Category")
        st.plotly_chart(fig, use_container_width=True)

# --- 6. INVENTORY STATUS (FORCE REFRESH) ---
elif menu == "🔎 Inventory Operational Status":
    st.subheader("🔎 Master Database")
    # Force a re-load every time this tab is clicked
    df = load_live_data(inv_ws)
    
    if df.empty:
        st.info("No items registered. Use the 'Register New Equipment' tab to add assets.")
    else:
        search = st.text_input("Search Assets...", "")
        filtered_df = df[df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)]

        edited_df = st.data_editor(
            filtered_df,
            hide_index=True, 
            use_container_width=True,
            column_config={
                "Total Qty": st.column_config.NumberColumn(disabled=True),
                "Category": st.column_config.Column(disabled=True),
                "Subsystem": st.column_config.Column(disabled=True)
            }
        )

        if st.button("💾 Save Changes"):
            with st.spinner("Updating Google Sheets..."):
                for i, row in edited_df.iterrows():
                    sheet_row = int(filtered_df.index[i]) + 2
                    f_val = min(int(row["Functional Qty"]), int(row["Total Qty"]))
                    inv_ws.update_cell(sheet_row, OFFICIAL_HEADERS.index("Functional Qty") + 1, f_val)
                    inv_ws.update_cell(sheet_row, OFFICIAL_HEADERS.index("Non-Functional Qty") + 1, int(row["Total Qty"]) - f_val)
                st.success("✅ Database Synced!")
                st.rerun()

# --- 7. REGISTRATION ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 Register New Asset")
    cat = st.selectbox("Category", list(EQUIPMENT_STRUCTURE.keys()))
    sub = st.selectbox("Subsystem", EQUIPMENT_STRUCTURE[cat])
    
    with st.form("reg_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        code = c1.text_input("Asset Code (e.g. CAM-01)")
        qty = c2.number_input("Quantity", min_value=1, step=1)
        cost = st.number_input("Unit Cost", min_value=0.0)
        
        if st.form_submit_button("✅ Add Asset"):
            # Row data: Category, Subsystem, Asset Code, Unit, Total Qty, Status, Unit Cost, Total Value, Life, Age, Func Qty, Non-Func Qty
            new_row = [cat, sub, code, "Nos", qty, "Operational", cost, (qty*cost), 10, 0, qty, 0]
            inv_ws.append_row(new_row)
            st.success(f"Registered {sub} successfully! Redirecting to Inventory...")
            st.rerun()





















































































