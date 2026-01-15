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

# --- 2. DATA LOADING & CLEANING ---
sh = init_connection()
inv_ws = sh.worksheet("Inventory")
maint_ws = sh.worksheet("Maintenance")

def get_safe_data(worksheet):
    data = worksheet.get_all_values()
    if not data: return pd.DataFrame()
    # Clean headers to remove any hidden spaces
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    
    # Ensure critical columns are numeric for the chart
    num_cols = ['Quantity', 'Functional Qty', 'Non-Functional Qty', 'Total Value']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

df_inv = get_safe_data(inv_ws)

# --- 3. UI SETUP ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
menu = st.sidebar.radio("Navigation", ["📊 Dashboard", "📝 Register Asset", "🔎 Assessment", "🛠️ Maintenance"])

# --- 4. MODULE: DASHBOARD (GREEN HORIZONTAL CHART) ---
if menu == "📊 Dashboard":
    st.header("Expressway System Health")
    if not df_inv.empty:
        # Group by Category to calculate health percentage
        cat_data = df_inv.groupby('Category').agg({'Functional Qty':'sum', 'Quantity':'sum'}).reset_index()
        cat_data['Health %'] = (cat_data['Functional Qty'] / cat_data['Quantity'].replace(0,1) * 100).round(1)
        
        # Horizontal Bar Chart - Green
        fig = px.bar(cat_data.sort_values('Health %'), x='Health %', y='Category', 
                     orientation='h', range_x=[0,100], text='Health %',
                     title="Live Operational Status per System")
        fig.update_traces(marker_color='#22C55E', texttemplate='%{text}%', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Financial Detail")
        st.dataframe(df_inv[['Category', 'Asset Name', 'Unit Cost', 'Total Value']], use_container_width=True)

# --- 5. MODULE: ASSESSMENT (THE FIX FOR SAVING) ---
elif menu == "🔎 Assessment":
    st.subheader("Update Operational Quantities")
    if not df_inv.empty:
        # We use a data editor to let you change numbers
        edit_df = df_inv[['Category', 'Asset Name', 'Quantity', 'Functional Qty', 'Non-Functional Qty']].copy()
        
        updated_df = st.data_editor(edit_df, hide_index=True, use_container_width=True, key="editor")

        if st.button("💾 Save to Google Sheets"):
            with st.spinner("Finding columns and saving..."):
                # 1. Identify Column Indices dynamically
                headers = inv_ws.row_values(1)
                headers_clean = [h.strip() for h in headers]
                
                try:
                    idx_q = headers_clean.index("Quantity") + 1
                    idx_f = headers_clean.index("Functional Qty") + 1
                    idx_nf = headers_clean.index("Non-Functional Qty") + 1
                    idx_s = headers_clean.index("Status") + 1
                    
                    # 2. Batch update (Update each row)
                    for i, row in updated_df.iterrows():
                        sheet_row = i + 2
                        status = "Functional" if float(row['Functional Qty']) > 0 else "Non-Functional"
                        
                        inv_ws.update_cell(sheet_row, idx_q, int(row['Quantity']))
                        inv_ws.update_cell(sheet_row, idx_f, int(row['Functional Qty']))
                        inv_ws.update_cell(sheet_row, idx_nf, int(row['Non-Functional Qty']))
                        inv_ws.update_cell(sheet_row, idx_s, status)
                    
                    st.success("✅ Saved! Please check the Dashboard for the updated Green Chart.")
                    st.rerun()
                except ValueError as e:
                    st.error(f"Error: Could not find one of the required columns in your Google Sheet headers. Please check spelling.")

# --- 6. OTHER MODULES (Simplified for completion) ---
elif menu == "📝 Register Asset":
    st.subheader("New Asset Registration")
    with st.form("reg"):
        cat = st.text_input("Category")
        name = st.text_input("Asset Name")
        q = st.number_input("Quantity", min_value=1)
        if st.form_submit_button("Register"):
            inv_ws.append_row([cat, name, "", "Nos", q, "Functional", 0, 0, 0, 0, q, 0])
            st.success("Registered!")

elif menu == "🛠️ Maintenance":
    st.subheader("Maintenance Log")
    df_m = get_safe_data(maint_ws)
    st.dataframe(df_m, use_container_width=True)



























































