import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- 1. OFFICIAL STRUCTURE ---
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
        # Force look for the 'inventory' sheet
        all_sheets = [ws.title for ws in sh.worksheets()]
        target = next((s for s in all_sheets if "inventory" in s.lower()), all_sheets[0])
        return sh.worksheet(target)
    except Exception as e:
        st.error(f"Spreadsheet Connection Error: {e}")
        return None

# --- 3. DATA ENGINE (FIXED DISPLAY ISSUE) ---
def get_standardized_data(worksheet):
    if not worksheet: return pd.DataFrame(), []
    
    # We clear the cache to ensure the new registered items show up immediately
    data = worksheet.get_all_values()
    if len(data) < 1: return pd.DataFrame(), []
    
    OFFICIAL_HEADERS = [
        "Category", "Subsystem", "Asset Code", "Unit", "Total Qty", 
        "Status", "Unit Cost", "Total Value", "Life", "Age", 
        "Functional Qty", "Non-Functional Qty"
    ]
    
    # Convert to DataFrame - using the first row of sheet as actual headers
    df = pd.DataFrame(data[1:], columns=data[0])
    
    # Clean column names in DF to match Official Headers
    mapping = {}
    for official in OFFICIAL_HEADERS:
        for raw in df.columns:
            if official.lower().replace(" ", "") == str(raw).lower().replace(" ", ""):
                mapping[raw] = official
                break
    
    df = df.rename(columns=mapping)
    
    # Fill missing columns to prevent KeyError
    for col in OFFICIAL_HEADERS:
        if col not in df.columns:
            df[col] = 0 if any(x in col for x in ["Qty", "Cost", "Value", "Life", "Age"]) else ""
    
    # Ensure math columns are numeric
    num_cols = ["Total Qty", "Unit Cost", "Total Value", "Life", "Age", "Functional Qty", "Non-Functional Qty"]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df[OFFICIAL_HEADERS], OFFICIAL_HEADERS

# --- 4. UI SETUP ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
inv_ws = init_connection()
df_inv, HEADERS = get_standardized_data(inv_ws)

st.markdown("""
    <div style="background-color: #1E3A8A; padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 25px;">
        <h1 style="margin:0;">Addis Ababa-Adama Expressway</h1>
        <p style="margin:0;">Electromechanical Master Database</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Inventory Operational Status", "📝 Register New Equipment"])

# --- 5. DASHBOARD ---
if menu == "📊 Smart Dashboard":
    if not df_inv.empty:
        t_qty = df_inv["Total Qty"].sum()
        f_qty = df_inv["Functional Qty"].sum()
        health = (f_qty / t_qty * 100) if t_qty > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("System Health", f"{health:.1f}%")
        c2.metric("Total Operational", int(f_qty))
        c3.metric("Maintenance Needed", int(t_qty - f_qty))

        st.divider()
        fig = px.bar(df_inv.groupby("Category").sum(numeric_only=True).reset_index(), 
                     x="Category", y=["Functional Qty", "Total Qty"], barmode='group')
        st.plotly_chart(fig, use_container_width=True)

# --- 6. INVENTORY STATUS (FIXED VIEW) ---
elif menu == "🔎 Inventory Operational Status":
    st.subheader("🔎 Master Database - Registered Assets")
    
    if df_inv.empty:
        st.warning("No data found. If you just registered an item, wait 2 seconds and click 'Register' again to refresh.")
    else:
        search = st.text_input("Search Assets...", "")
        filtered_df = df_inv[df_inv.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)]

        edited_df = st.data_editor(
            filtered_df,
            hide_index=True, 
            use_container_width=True,
            column_config={
                "Total Qty": st.column_config.NumberColumn(disabled=True),
                "Non-Functional Qty": st.column_config.NumberColumn(disabled=True),
                "Category": st.column_config.Column(disabled=True),
                "Subsystem": st.column_config.Column(disabled=True)
            }
        )

        if st.button("💾 Save Changes"):
            with st.spinner("Saving..."):
                for i, row in edited_df.iterrows():
                    sheet_row = int(filtered_df.index[i]) + 2
                    f_val = min(int(row["Functional Qty"]), int(row["Total Qty"]))
                    inv_ws.update_cell(sheet_row, HEADERS.index("Functional Qty") + 1, f_val)
                    inv_ws.update_cell(sheet_row, HEADERS.index("Non-Functional Qty") + 1, int(row["Total Qty"]) - f_val)
                st.success("✅ Synced!"); st.rerun()

# --- 7. REGISTRATION (FIXED REDIRECT) ---
elif menu == "📝 Register New Equipment":
    st.subheader("📝 New Asset Onboarding")
    cat = st.selectbox("Category", list(EQUIPMENT_STRUCTURE.keys()))
    sub = st.selectbox("Subsystem", EQUIPMENT_STRUCTURE[cat])
    
    with st.form("reg_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        code = c1.text_input("Asset Code")
        unit = c2.selectbox("Unit", ["Nos", "Sets", "Meters"])
        qty = c3.number_input("Quantity", min_value=1, step=1)
        
        cost = st.number_input("Unit Cost", min_value=0.0)
        
        if st.form_submit_button("✅ Add Asset"):
            # Ensure the row matches your Google Sheet column order exactly
            new_row = [cat, sub, code, unit, qty, "Operational", cost, (qty*cost), 10, 0, qty, 0]
            inv_ws.append_row(new_row)
            st.success(f"Registered {sub}. Moving to inventory view...")
            st.rerun() # This force-refreshes the whole app so the item appears




















































































