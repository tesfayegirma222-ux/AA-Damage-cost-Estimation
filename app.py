import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- 1. AUTH & CONNECTION ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        url = st.secrets["SHEET_URL"]
        return client.open_by_url(url)
    except Exception as e:
        st.error(f"Configuration Error: {e}")
        st.stop()

# --- 2. DATA LOADING (ROBUST) ---
sh = init_connection()
inv_ws = sh.worksheet("Inventory")
maint_ws = sh.worksheet("Maintenance")

def get_safe_data(worksheet):
    data = worksheet.get_all_values()
    if not data or len(data) < 1: return pd.DataFrame()
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    
    # Ensure columns exist and convert to numbers
    num_cols = ['Quantity', 'Functional Qty', 'Non-Functional Qty', 'Total Value']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0
    return df

# Load initial data
df_inv = get_safe_data(inv_ws)

# --- 3. UI SETUP ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
st.markdown("""<style>.main-header { background-color: #1E3A8A; padding: 20px; border-radius: 12px; color: white; text-align: center; }</style>
    <div class="main-header"><h1>Addis Ababa-Adama Expressway</h1><p>Electromechanical Asset Management</p></div>""", unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Dashboard", "📝 Register New Asset", "🔎 Conditional Assessment", "🛠️ Maintenance Log"])

# --- 4. MODULE: DASHBOARD (LIVE CONNECTION) ---
if menu == "📊 Dashboard":
    if not df_inv.empty:
        # Metrics
        total_units = df_inv['Quantity'].sum()
        func_units = df_inv['Functional Qty'].sum()
        health_pct = (func_units / total_units * 100) if total_units > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Overall Health", f"{health_pct:.1f}%")
        c2.metric("Functional ✅", int(func_units))
        c3.metric("Broken ❌", int(df_inv['Non-Functional Qty'].sum()))

        st.divider()
        st.subheader("📊 System Health (Operational Status)")
        
        # Aggregate Health per Category
        cat_health = df_inv.groupby('Category').agg({'Functional Qty':'sum', 'Quantity':'sum'}).reset_index()
        cat_health['Health %'] = (cat_health['Functional Qty'] / cat_health['Quantity'].replace(0,1) * 100).round(1)
        
        # Green Horizontal Bar Chart
        fig = px.bar(cat_health.sort_values('Health %'), x='Health %', y='Category', orientation='h', 
                     range_x=[0,100], text='Health %', color_discrete_sequence=['#22C55E'])
        fig.update_traces(texttemplate='%{text}%', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

# --- 5. MODULE: CONDITIONAL ASSESSMENT (THE FIX) ---
elif menu == "🔎 Conditional Assessment":
    st.subheader("🔎 Update Asset Functionality")
    st.info("Change the numbers below and click 'Save' to update the Health Chart.")
    
    if not df_inv.empty:
        # Use a subset for editing
        edit_df = df_inv[['Category', 'Asset Name', 'Quantity', 'Functional Qty', 'Non-Functional Qty']].copy()
        
        # Display Data Editor
        updated_data = st.data_editor(
            edit_df, 
            hide_index=True, 
            use_container_width=True,
            key="qty_editor_final"
        )

        if st.button("💾 Save & Update System Health"):
            with st.spinner("Syncing with Google Sheets..."):
                # 1. Dynamically find column positions
                headers = [h.strip() for h in inv_ws.row_values(1)]
                try:
                    idx_func = headers.index("Functional Qty") + 1
                    idx_nonfunc = headers.index("Non-Functional Qty") + 1
                    idx_stat = headers.index("Status") + 1
                    
                    # 2. Iterate and update each row
                    for i, row in updated_data.iterrows():
                        sheet_row = i + 2
                        f_val = int(row['Functional Qty'])
                        nf_val = int(row['Non-Functional Qty'])
                        status_text = "Functional" if f_val > 0 else "Non-Functional"
                        
                        # Update the three relevant columns
                        inv_ws.update_cell(sheet_row, idx_func, f_val)
                        inv_ws.update_cell(sheet_row, idx_nonfunc, nf_val)
                        inv_ws.update_cell(sheet_row, idx_stat, status_text)
                    
                    st.success("✅ Database Updated! Refreshing Chart...")
                    st.rerun()
                except ValueError:
                    st.error("Missing headers in Google Sheet: Ensure 'Functional Qty' and 'Non-Functional Qty' exist.")

# --- 6. REMAINING MODULES (UNTOUCHED) ---
elif menu == "📝 Register New Asset":
    st.subheader("Register New Hardware")
    # ... (Keep your existing registration form logic here)
    st.write("Use your existing form to add rows to 'Inventory' worksheet.")

elif menu == "🛠️ Maintenance Log":
    st.subheader("Maintenance Log")
    # ... (Keep your existing maintenance log logic here)
    st.write("Current logs are saved to 'Maintenance' worksheet.")





























































