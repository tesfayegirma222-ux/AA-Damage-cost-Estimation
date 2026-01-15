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
        st.error(f"Setup Error: {e}")
        st.stop()

sh = init_connection()
inv_ws = sh.worksheet("Inventory")
maint_ws = sh.worksheet("Maintenance")

# --- 2. DATA ENGINE (ROBUST CLEANING) ---
def get_safe_data(worksheet):
    data = worksheet.get_all_values()
    if not data or len(data) < 1: return pd.DataFrame()
    
    # Clean headers: Remove spaces, tabs, and newlines
    headers = [" ".join(str(h).split()) for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    
    # Define required columns for app stability
    required = ['Category', 'Asset Name', 'Quantity', 'Functional Qty', 'Non-Functional Qty', 'Current Age', 'Expected Life', 'Total Value']
    for col in required:
        if col not in df.columns:
            df[col] = 0
            
    # Numeric conversion
    num_cols = ['Quantity', 'Functional Qty', 'Non-Functional Qty', 'Current Age', 'Expected Life', 'Total Value']
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

df_inv = get_safe_data(inv_ws)

# --- 3. UI STYLE ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
st.markdown("""
    <style>
    .main-header { background-color: #1E3A8A; padding: 20px; border-radius: 12px; color: white; text-align: center; }
    </style>
    <div class="main-header">
        <h1>Addis Ababa-Adama Expressway</h1>
        <p>Asset Operational Portal</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Dashboard", "📝 Register New Asset", "🔎 Conditional Assessment", "🛠️ Maintenance Log"])

# --- 4. MODULE: DASHBOARD ---
if menu == "📊 Dashboard":
    if not df_inv.empty:
        m1, m2, m3 = st.columns(3)
        total_q = df_inv['Quantity'].sum()
        func_q = df_inv['Functional Qty'].sum()
        health = (func_q / total_q * 100) if total_q > 0 else 0
        
        m1.metric("Operational Health", f"{health:.1f}%")
        m2.metric("Total Functional", int(func_q))
        m3.metric("Aging Alerts", len(df_inv[df_inv['Current Age'] >= df_inv['Expected Life']]))

        st.subheader("📊 System Health (Operational Status)")
        cat_sum = df_inv.groupby('Category').agg({'Functional Qty': 'sum', 'Quantity': 'sum'}).reset_index()
        cat_sum['Health %'] = (cat_sum['Functional Qty'] / cat_sum['Quantity'].replace(0, 1) * 100).round(1)
        
        fig = px.bar(cat_sum.sort_values('Health %'), x='Health %', y='Category', orientation='h', 
                     range_x=[0, 100], text='Health %', color_discrete_sequence=['#22C55E'])
        fig.update_traces(texttemplate='%{text}%', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

# --- 5. MODULE: CONDITIONAL ASSESSMENT (FIXED SYNC LOGIC) ---
elif menu == "🔎 Conditional Assessment":
    st.subheader("🔎 Asset Status Table")
    if not df_inv.empty:
        edit_view = df_inv[['Category', 'Asset Name', 'Quantity', 'Functional Qty', 'Non-Functional Qty']]
        edited_df = st.data_editor(edit_view, hide_index=True, use_container_width=True, key="assess_editor")

        if st.button("💾 Save All Changes"):
            with st.spinner("Searching for columns and syncing..."):
                # Fetch raw headers and clean them thoroughly
                raw_headers = inv_ws.row_values(1)
                clean_headers = [" ".join(str(h).split()) for h in raw_headers]
                
                try:
                    # Find indices dynamically
                    idx_f = clean_headers.index("Functional Qty") + 1
                    idx_nf = clean_headers.index("Non-Functional Qty") + 1
                    
                    # Try to find Status column, default to 6 if not found
                    try:
                        idx_s = clean_headers.index("Status") + 1
                    except ValueError:
                        idx_s = 6 

                    for i, row in edited_df.iterrows():
                        sheet_row = i + 2
                        f_val = int(row['Functional Qty'])
                        nf_val = int(row['Non-Functional Qty'])
                        stat = "Functional" if f_val > 0 else "Non-Functional"
                        
                        inv_ws.update_cell(sheet_row, idx_f, f_val)
                        inv_ws.update_cell(sheet_row, idx_nf, nf_val)
                        inv_ws.update_cell(sheet_row, idx_s, stat)
                        
                    st.success("✅ Assessment saved and Dashboard updated!")
                    st.rerun()
                except ValueError:
                    st.error("Header Error: Please check that row 1 of your 'Inventory' sheet contains 'Functional Qty' and 'Non-Functional Qty' exactly.")

# --- 6. REMAINING MODULES ---
elif menu == "📝 Register New Asset":
    st.subheader("Register Asset")
    with st.form("reg"):
        cat = st.text_input("Category")
        name = st.text_input("Subsystem Name")
        q = st.number_input("Quantity", min_value=1)
        if st.form_submit_button("Add Row"):
            inv_ws.append_row([cat, name, "", "Nos", q, "Functional", 0, 0, 10, 0, q, 0])
            st.success("Recorded.")
            st.rerun()

elif menu == "🛠️ Maintenance Log":
    st.subheader("Maintenance History")
    df_m = get_safe_data(maint_ws)
    st.dataframe(df_m, use_container_width=True)


































































