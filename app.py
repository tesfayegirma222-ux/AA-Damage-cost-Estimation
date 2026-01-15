import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- 1. SMART CONNECTION & WORKSHEET FINDER ---
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        url = st.secrets["SHEET_URL"]
        sh = client.open_by_url(url)
        
        # Smart Finder: Finds 'Inventory' regardless of case or spaces
        all_sheets = [ws.title for ws in sh.worksheets()]
        target = next((s for s in all_sheets if "inventory" in s.lower().strip()), None)
        
        if not target:
            st.error(f"❌ Error: Could not find a tab named 'Inventory'. Found: {all_sheets}")
            st.stop()
            
        return sh, sh.worksheet(target)
    except Exception as e:
        st.error(f"Configuration Error: {e}")
        st.stop()

sh, inv_ws = init_connection()

# --- 2. THE FUZZY COLUMN FINDER ---
def get_col_index(headers, target_name):
    headers_clean = ["".join(str(h).split()).lower() for h in headers]
    target_clean = "".join(target_name.split()).lower()
    if target_clean in headers_clean:
        return headers_clean.index(target_clean) + 1
    for i, h in enumerate(headers_clean):
        if target_clean in h or h in target_clean:
            return i + 1
    return None

def get_safe_data(worksheet):
    data = worksheet.get_all_values()
    if not data or len(data) < 1: return pd.DataFrame()
    
    raw_headers = data[0]
    df = pd.DataFrame(data[1:])
    
    # Map key columns
    idx_cat = get_col_index(raw_headers, "Category")
    idx_name = get_col_index(raw_headers, "Asset Name")
    idx_qty = get_col_index(raw_headers, "Quantity")
    idx_func = get_col_index(raw_headers, "Functional Qty")
    idx_non = get_col_index(raw_headers, "Non-Functional Qty")

    clean_df = pd.DataFrame()
    clean_df['Category'] = df[idx_cat-1] if idx_cat else "General"
    clean_df['Asset Name'] = df[idx_name-1] if idx_name else "Unknown Asset"
    clean_df['Quantity'] = pd.to_numeric(df[idx_qty-1], errors='coerce').fillna(0) if idx_qty else 0
    clean_df['Functional Qty'] = pd.to_numeric(df[idx_func-1], errors='coerce').fillna(0) if idx_func else 0
    clean_df['Non-Functional Qty'] = pd.to_numeric(df[idx_non-1], errors='coerce').fillna(0) if idx_non else 0
    
    return clean_df

df_inv = get_safe_data(inv_ws)

# --- 3. UI STYLE ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
st.markdown("""
    <style>
    .main-header { background-color: #1E3A8A; padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px;}
    </style>
    <div class="main-header">
        <h1>Addis Ababa-Adama Expressway</h1>
        <p>Electromechanical Inventory & System Health</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Inventory Assessment"])

# --- 4. MODULE: SMART DASHBOARD ---
if menu == "📊 Smart Dashboard":
    if not df_inv.empty:
        total = df_inv['Quantity'].sum()
        func = df_inv['Functional Qty'].sum()
        health = (func / total * 100) if total > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Operational Health", f"{health:.1f}%")
        c2.metric("Working Units", int(func))
        c3.metric("Broken Units", int(df_inv['Non-Functional Qty'].sum()))

        st.subheader("📊 Health by Equipment Category")
        chart_df = df_inv.groupby('Category').agg({'Functional Qty':'sum', 'Quantity':'sum'}).reset_index()
        chart_df['Health %'] = (chart_df['Functional Qty'] / chart_df['Quantity'].replace(0,1) * 100).round(1)
        
        # Logic: Red for <50%, Yellow for <80%, Green for >=80%
        chart_df['Status'] = pd.cut(chart_df['Health %'], bins=[-1, 50, 80, 101], labels=['Critical', 'Warning', 'Healthy'])
        
        fig = px.bar(chart_df.sort_values('Health %'), x='Health %', y='Category', orientation='h', 
                     range_x=[0,100], text='Health %', color='Status',
                     color_discrete_map={'Healthy': '#22C55E', 'Warning': '#FACC15', 'Critical': '#EF4444'})
        st.plotly_chart(fig, use_container_width=True)

# --- 5. MODULE: INVENTORY ASSESSMENT ---
elif menu == "🔎 Inventory Assessment":
    st.subheader("🔎 Update Inventory Status")
    st.info("Edit 'Functional Qty' and click Save. The Dashboard will update automatically.")
    
    if not df_inv.empty:
        edited_df = st.data_editor(df_inv, hide_index=True, use_container_width=True)

        if st.button("💾 Save Status & Update Dashboard"):
            with st.spinner("Syncing to Cloud..."):
                raw_headers = inv_ws.row_values(1)
                f_col = get_col_index(raw_headers, "Functional Qty")
                nf_col = get_col_index(raw_headers, "Non-Functional Qty")
                
                if f_col and nf_col:
                    for i, row in edited_df.iterrows():
                        sheet_row = i + 2
                        inv_ws.update_cell(sheet_row, f_col, int(row['Functional Qty']))
                        inv_ws.update_cell(sheet_row, nf_col, int(row['Non-Functional Qty']))
                    
                    st.success("✅ Inventory updated!")
                    st.rerun()
                else:
                    st.error("Could not find columns in Sheet.")







































































