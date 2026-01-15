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

# --- 2. THE "FUZZY" HEADER FINDER (FIXES THE ERROR) ---
def get_col_index(headers, target_name):
    """Finds a column index even if the name isn't a perfect match."""
    headers_clean = ["".join(str(h).split()).lower() for h in headers]
    target_clean = "".join(target_name.split()).lower()
    
    # 1. Try exact match
    if target_clean in headers_clean:
        return headers_clean.index(target_clean) + 1
    
    # 2. Try partial match (e.g., if sheet says 'Functional Quantity' it finds 'Functional')
    for i, h in enumerate(headers_clean):
        if target_clean in h or h in target_clean:
            return i + 1
    return None

def get_safe_data(worksheet):
    data = worksheet.get_all_values()
    if not data or len(data) < 1: return pd.DataFrame()
    
    raw_headers = data[0]
    df = pd.DataFrame(data[1:])
    
    # Map columns dynamically
    idx_cat = get_col_index(raw_headers, "Category")
    idx_name = get_col_index(raw_headers, "Asset Name")
    idx_qty = get_col_index(raw_headers, "Quantity")
    idx_func = get_col_index(raw_headers, "Functional Qty")
    idx_non = get_col_index(raw_headers, "Non-Functional Qty")

    # Build the dataframe with what we found
    clean_df = pd.DataFrame()
    clean_df['Category'] = df[idx_cat-1] if idx_cat else "Unknown"
    clean_df['Asset Name'] = df[idx_name-1] if idx_name else "Unknown"
    clean_df['Quantity'] = pd.to_numeric(df[idx_qty-1], errors='coerce').fillna(0) if idx_qty else 0
    clean_df['Functional Qty'] = pd.to_numeric(df[idx_func-1], errors='coerce').fillna(0) if idx_func else 0
    clean_df['Non-Functional Qty'] = pd.to_numeric(df[idx_non-1], errors='coerce').fillna(0) if idx_non else 0
    
    return clean_df

df_inv = get_safe_data(inv_ws)

# --- 3. UI SETUP ---
st.set_page_config(page_title="AAE Asset Management", layout="wide")
st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>Addis Ababa-Adama Expressway</h1>", unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Dashboard", "🔎 Inventory Assessment"])

# --- 4. DASHBOARD ---
if menu == "📊 Dashboard":
    if not df_inv.empty:
        total = df_inv['Quantity'].sum()
        func = df_inv['Functional Qty'].sum()
        health = (func / total * 100) if total > 0 else 0
        
        st.metric("System Operational Health", f"{health:.1f}%")
        
        # Health Chart
        chart_data = df_inv.groupby('Category').agg({'Functional Qty':'sum', 'Quantity':'sum'}).reset_index()
        chart_data['Health %'] = (chart_data['Functional Qty'] / chart_data['Quantity'].replace(0,1) * 100).round(1)
        
        fig = px.bar(chart_data, x='Health %', y='Category', orientation='h', range_x=[0,100],
                     color_discrete_sequence=['#22C55E'], text='Health %')
        st.plotly_chart(fig, use_container_width=True)

# --- 5. INVENTORY ASSESSMENT (STABLE SAVE) ---
elif menu == "🔎 Inventory Assessment":
    st.subheader("🔎 Inventory Status Input")
    
    if not df_inv.empty:
        edited_df = st.data_editor(df_inv, hide_index=True, use_container_width=True)

        if st.button("💾 Save to Google Sheets"):
            with st.spinner("Syncing..."):
                raw_headers = inv_ws.row_values(1)
                
                # Find column positions again for the save
                f_col = get_col_index(raw_headers, "Functional Qty")
                nf_col = get_col_index(raw_headers, "Non-Functional Qty")
                
                if not f_col or not nf_col:
                    st.error(f"Could not find columns in Sheet. Headers seen: {raw_headers}")
                else:
                    for i, row in edited_df.iterrows():
                        sheet_row = i + 2
                        inv_ws.update_cell(sheet_row, f_col, int(row['Functional Qty']))
                        inv_ws.update_cell(sheet_row, nf_col, int(row['Non-Functional Qty']))
                    
                    st.success("✅ Saved successfully!")
                    st.rerun()






































































