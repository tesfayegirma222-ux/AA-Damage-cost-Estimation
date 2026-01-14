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

# --- 2. UI THEME ---
st.set_page_config(page_title="AAE Asset Portal", layout="wide")
st.markdown("""
    <style>
    .main-header { background-color: #1E3A8A; padding: 20px; border-radius: 10px; color: white; text-align: center; }
    </style>
    <div class="main-header">
        <h1>Addis Ababa-Adama Expressway</h1>
        <p>Asset Operational Status Management</p>
    </div>
    """, unsafe_allow_html=True)

sh = init_connection()
inv_ws = sh.worksheet("Inventory")

# --- 3. DATA CLEANING & LOADING ---
def get_cleaned_data():
    data = inv_ws.get_all_values()
    if not data: return pd.DataFrame()
    
    # Clean headers to prevent KeyErrors (removes hidden spaces)
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    
    # Ensure columns exist and are numeric
    cols = ['Quantity', 'Functional Qty', 'Non-Functional Qty', 'Total Value', 'Current Age', 'Expected Life']
    for col in cols:
        if col not in df.columns: df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

df_inv = get_cleaned_data()

# --- 4. NAVIGATION ---
menu = st.sidebar.radio("Module", ["📊 Dashboard", "🔎 Conditional Assessment"])

# --- 5. DASHBOARD (CONNECTED TO UPDATES) ---
if menu == "📊 Dashboard":
    if not df_inv.empty:
        m1, m2, m3 = st.columns(3)
        total = df_inv['Quantity'].sum()
        func = df_inv['Functional Qty'].sum()
        health = (func / total * 100) if total > 0 else 0
        
        m1.metric("Operational Health", f"{health:.1f}%")
        m2.metric("Total Functional", int(func))
        m3.metric("Total Broken", int(df_inv['Non-Functional Qty'].sum()))

        st.subheader("📊 System Health Status")
        # Horizontal Bar Chart (Green)
        cat_sum = df_inv.groupby('Category').agg({'Functional Qty': 'sum', 'Quantity': 'sum'}).reset_index()
        cat_sum['Health %'] = (cat_sum['Functional Qty'] / cat_sum['Quantity'].replace(0, 1) * 100).round(1)
        
        fig = px.bar(cat_sum.sort_values('Health %'), x='Health %', y='Category', orientation='h', 
                     range_x=[0, 100], text='Health %', color_discrete_sequence=['#22C55E'])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available.")

# --- 6. CONDITIONAL ASSESSMENT (FIXED SAVE LOGIC) ---
elif menu == "🔎 Conditional Assessment":
    st.subheader("🔎 Update Asset Quantities")
    st.info("Edit the 'Functional ✅' and 'Broken ❌' columns, then click Save.")

    if not df_inv.empty:
        # We only show the columns necessary for editing
        display_df = df_inv[['Category', 'Asset Name', 'Quantity', 'Functional Qty', 'Non-Functional Qty']].copy()
        
        edited_df = st.data_editor(
            display_df,
            column_config={
                "Category": st.column_config.Column(disabled=True),
                "Asset Name": st.column_config.Column(disabled=True),
                "Quantity": st.column_config.NumberColumn("Total Registered", min_value=0),
                "Functional Qty": st.column_config.NumberColumn("Functional ✅", min_value=0),
                "Non-Functional Qty": st.column_config.NumberColumn("Broken ❌", min_value=0),
            },
            hide_index=True,
            use_container_width=True,
            key="qty_editor"
        )

        if st.button("💾 Save Changes to Google Sheets"):
            with st.spinner("Updating records..."):
                try:
                    for index, row in edited_df.iterrows():
                        sheet_row = index + 2 # +1 for header, +1 for index
                        
                        # --- IMPORTANT: UPDATE THESE INDICES TO MATCH YOUR SHEET ---
                        # Column 5: Total Quantity
                        inv_ws.update_cell(sheet_row, 5, int(row['Quantity']))
                        # Column 11: Functional Qty
                        inv_ws.update_cell(sheet_row, 11, int(row['Functional Qty']))
                        # Column 12: Non-Functional Qty
                        inv_ws.update_cell(sheet_row, 12, int(row['Non-Functional Qty']))
                        
                        # Column 6: Status (Auto-logic)
                        status = "Functional" if row['Functional Qty'] > 0 else "Non-Functional"
                        inv_ws.update_cell(sheet_row, 6, status)

                    st.success("✅ Saved successfully! Go to Dashboard to see the updated chart.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving: {e}")
























































