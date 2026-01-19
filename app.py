import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 0. AUTHENTICATION SYSTEM ---
def check_password():
    def password_entered():
        user = st.session_state.get("username")
        pwd = st.session_state.get("password")
        if user == "admin" and pwd == "aae123":
            st.session_state["password_correct"] = True
            if "password" in st.session_state: del st.session_state["password"]
            if "username" in st.session_state: del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("<div style='text-align: center; padding: 20px;'><h2 style='color: #1e3a8a;'>AAE Executive Portal</h2><p>AA Electromechanical Asset Master Database Login</p></div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Login", on_click=password_entered)
        return False
    elif not st.session_state["password_correct"]:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Login", on_click=password_entered)
            st.error("😕 Username or password incorrect")
        return False
    return True

if check_password():
    AAE_STRUCTURE = {
        "Electric Power Source": ["Electric Utility", "Generator", "Solar Power System"],
        "Electric Power Distribution": ["ATS", "Main Breaker", "Distribution Panel", "Power Cable", "Transformer"],
        "UPS System": ["UPS Unit", "UPS Battery Bank", "Inverter"],
        "CCTV System": ["Lane Camera", "Booth Camera", "Road Camera", "PTZ Camera", "NVR/Server"],
        "Auto-Railing System": ["Barrier Gate Motor", "Barrier Controller", "Loop Detector", "Remote Control"],
        "HVAC System": ["Air Conditioning Unit", "Ventilation Fan", "Chiller"],
        "Illumination System": ["High Mast Light", "Road Light", "Booth Light", "Plaza Light", "Photocell Controller"],
        "Electronic Display System": ["VMS", "LED Notice Board", "Money Fee Display", "Passage Signal Lamp", "Fog Light"],
        "Pump System": ["Surface Water Pump", "Submersible Pump", "Fire Pump", "Pump Controller"],
        "Overload System (WIM)": ["Weight-In-Motion Sensor", "WIM Controller", "Inductive Loop", "Charging Controller"]
    }

    RCA_STANDARDS = {
        "Electric Power Source": ["Fuel Contamination", "AVR Failure", "Battery Dead", "Utility Outage"],
        "Electric Power Distribution": ["MCB Tripped", "Contact Burnout", "Insulation Failure", "Loose Connection"],
        "CCTV System": ["Connector Corrosion", "Power Supply Fault", "IP Conflict", "Lens Fogging"],
        "General": ["Vandalism", "Physical Accident", "Extreme Weather", "Wear & Tear"]
    }

    def init_connection():
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        try:
            creds_dict = st.secrets["gcp_service_account"]
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            client = gspread.authorize(creds)
            sh = client.open_by_url(st.secrets["SHEET_URL"])
            inv = sh.worksheet("Sheet1")
            
            # Failure Logs
            try: maint = sh.worksheet("Maintenance_Log")
            except: 
                maint = sh.add_worksheet(title="Maintenance_Log", rows="1000", cols="6")
                maint.append_row(["Date", "Category", "Subsystem", "Asset Code", "Failure Cause", "Technician"])
            
            # PM Activity
            try: pm_ws = sh.worksheet("PM_Activity")
            except:
                pm_ws = sh.add_worksheet(title="PM_Activity", rows="1000", cols="6")
                pm_ws.append_row(["Date", "Category", "Subsystem", "Asset Code", "Activity Type", "Next Due Date"])

            # NEW: Removed Assets Sheet
            try: rem_ws = sh.worksheet("Removed_Assets")
            except:
                rem_ws = sh.add_worksheet(title="Removed_Assets", rows="1000", cols="7")
                rem_ws.append_row(["Date", "Category", "Subsystem", "Asset Code", "Reason", "Value At Removal", "Technician"])
                
            return inv, maint, pm_ws, rem_ws
        except Exception as e:
            st.error(f"Connection Error: {e}")
            return None, None, None, None

    inv_ws, maint_ws, pm_ws, rem_ws = init_connection()

    def load_data(worksheet):
        if not worksheet: return pd.DataFrame()
        data = worksheet.get_all_values()
        if len(data) < 2: return pd.DataFrame()
        headers = [str(h).strip() for h in data[0]]
        df = pd.DataFrame(data[1:], columns=headers)
        for col in df.columns:
            if any(k in col.lower() for k in ['qty', 'total', 'cost', 'value', 'func', 'life', 'age']):
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df

    st.set_page_config(page_title="AAE EMA Portal", layout="wide")
    logo_url = "https://skilled-sapphire-ragpx5z8le.edgeone.app/images.jpg"
    st.sidebar.image(logo_url, use_container_width=True)

    st.markdown("""
        <style>
        .stApp { background-color: #f8fafc; }
        .main-header {
            background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
            color: white; padding: 1.5rem; border-radius: 12px;
            text-align: center; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        div[data-testid="metric-container"] {
            background: white; padding: 15px; border-radius: 10px;
            border-left: 5px solid #10b981; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        </style>
        <div class="main-header">
            <h1 style="margin:0; font-size: 24px;">AAE ELECTROMECHANICAL EXECUTIVE PORTAL</h1>
            <p style="margin:0; opacity: 0.9;">Strategic EM Asset Management & RCA Dashboard</p>
        </div>
    """, unsafe_allow_html=True)

    df_inv = load_data(inv_ws)
    df_maint = load_data(maint_ws)
    df_pm = load_data(pm_ws)
    df_rem = load_data(rem_ws)

    if st.sidebar.button("🔓 Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Asset Registry", "📝 Add New Asset", "🛠️ Logs & Maintenance"])

    if menu == "📊 Smart Dashboard":
        if df_inv.empty:
            st.info("Inventory is empty. Please register assets.")
        else:
            v_col, q_col, f_col, c_col = df_inv.columns[7], df_inv.columns[4], df_inv.columns[5], df_inv.columns[0]
            s_col, id_col = df_inv.columns[1], df_inv.columns[2]
            life_col, used_col = df_inv.columns[8], df_inv.columns[9]
            
            # --- KPI METRICS ---
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("💰 Portfolio Value", f"{df_inv[v_col].sum():,.0f} Br")
            k2.metric("📦 Active Assets", int(df_inv[q_col].sum()))
            health = (df_inv[f_col].sum() / df_inv[q_col].sum() * 100) if df_inv[q_col].sum() > 0 else 0
            k3.metric("🏥 Health Index", f"{health:.1f}%")
            
            # NEW Removed Feature Metric
            removed_val = df_rem['Value At Removal'].sum() if not df_rem.empty else 0
            k4.metric("🗑️ Retired Assets", f"{len(df_rem)} Items", delta=f"{removed_val:,.0f} Br")

            st.divider()

            # --- LIFE-AGE & REMOVAL ANALYSIS ---
            st.markdown("#### ⏳ Asset Life-Age & Retirement Analysis")
            col_age1, col_age2 = st.columns([6, 4])
            df_inv['Remaining %'] = ((df_inv[life_col] - df_inv[used_col]) / df_inv[life_col] * 100).clip(0, 100).fillna(0)
            
            with col_age1:
                fig_age = px.scatter(df_inv, x=used_col, y='Remaining %', size=v_col, color=s_col,
                                     hover_name=id_col, title="Asset Replacement Matrix")
                fig_age.add_hline(y=20, line_dash="dot", line_color="red")
                st.plotly_chart(fig_age, use_container_width=True)

            with col_age2:
                st.markdown("##### 📉 Disposal Reasons")
                if not df_rem.empty:
                    fig_rem = px.pie(df_rem, names='Reason', hole=0.4, title="Asset Retirement Drivers")
                    st.plotly_chart(fig_rem, use_container_width=True)
                else:
                    st.info("No retired assets recorded to show distribution.")

            st.divider()

            # --- PREVENTIVE MAINTENANCE DASHBOARD ---
            st.markdown("#### 🛡️ Maintenance & PM Status")
            p_col1, p_col2 = st.columns([1, 1])
            with p_col1:
                if not df_pm.empty:
                    pm_counts = df_pm.groupby('Category').size().reset_index(name='Count')
                    fig_pm = px.bar(pm_counts, x='Count', y='Category', orientation='h', title="PM Compliance", color='Count')
                    st.plotly_chart(fig_pm, use_container_width=True)
            with p_col2:
                st.markdown("##### 📅 Upcoming PM Due")
                if not df_pm.empty:
                    df_pm['Next Due Date'] = pd.to_datetime(df_pm['Next Due Date'])
                    upcoming = df_pm[df_pm['Next Due Date'] >= datetime.now()].sort_values('Next Due Date').head(5)
                    st.dataframe(upcoming[[id_col, 'Activity Type', 'Next Due Date']], hide_index=True, use_container_width=True)

    elif menu == "📝 Add New Asset":
        st.subheader("📝 New Equipment Registration")
        c1, c2 = st.columns(2)
        sel_cat = c1.selectbox("Major Category", list(AAE_STRUCTURE.keys()))
        sel_sub = c2.selectbox("Subsystem", AAE_STRUCTURE.get(sel_cat, []))
        with st.form("reg_form", clear_on_submit=True):
            a_code = st.text_input("Asset Code")
            a_qty = st.number_input("Quantity", min_value=1)
            a_cost = st.number_input("Unit Cost (Br)", min_value=0.0)
            if st.form_submit_button("🚀 Commit to Sheet1"):
                inv_ws.append_row([sel_cat, sel_sub, a_code, "Nos", a_qty, a_qty, a_cost, a_qty*a_cost, 10, 0, 0])
                st.success("Registered!"); st.rerun()

    elif menu == "🛠️ Logs & Maintenance":
        tab_fail, tab_pm, tab_rem = st.tabs(["⚠️ Failures", "🛡️ PM Activities", "🗑️ Disposal/Removal"])
        
        with tab_fail:
            st.subheader("Failure Logging")
            l1, l2 = st.columns(2)
            m_cat = l1.selectbox("Category", list(AAE_STRUCTURE.keys()), key="f_cat")
            m_sub = l2.selectbox("Subsystem", AAE_STRUCTURE.get(m_cat, []), key="f_sub")
            with st.form("maint_form", clear_on_submit=True):
                m_cause = st.selectbox("Root Cause", RCA_STANDARDS.get(m_cat, ["General Issue"]) + ["Wear & Tear", "Vandalism"])
                m_code = st.text_input("Asset Code")
                m_tech = st.text_input("Technician")
                if st.form_submit_button("⚠️ Log Failure"):
                    maint_ws.append_row([datetime.now().strftime("%Y-%m-%d"), m_cat, m_sub, m_code, m_cause, m_tech])
                    st.success("Failure Logged!"); st.rerun()

        with tab_pm:
            st.subheader("PM Activity")
            p1, p2 = st.columns(2)
            pm_cat = p1.selectbox("Category", list(AAE_STRUCTURE.keys()), key="pm_cat")
            pm_sub = p2.selectbox("Subsystem", AAE_STRUCTURE.get(pm_cat, []), key="pm_sub")
            with st.form("pm_form", clear_on_submit=True):
                pm_code = st.text_input("Asset Code")
                pm_type = st.selectbox("Type", ["Monthly", "Quarterly", "Annual", "Calibration"])
                pm_int = st.select_slider("Months", options=[1, 3, 6, 12])
                if st.form_submit_button("🛡️ Log PM"):
                    next_date = (datetime.now() + timedelta(days=pm_int*30)).strftime("%Y-%m-%d")
                    pm_ws.append_row([datetime.now().strftime("%Y-%m-%d"), pm_cat, pm_sub, pm_code, pm_type, next_date])
                    st.success(f"PM Logged! Next due: {next_date}"); st.rerun()

        with tab_rem:
            st.subheader("Asset Removal/Disposal")
            r1, r2 = st.columns(2)
            rm_cat = r1.selectbox("Category", list(AAE_STRUCTURE.keys()), key="rm_cat")
            rm_sub = r2.selectbox("Subsystem", AAE_STRUCTURE.get(rm_cat, []), key="rm_sub")
            with st.form("remove_form", clear_on_submit=True):
                rm_code = st.text_input("Asset Code to Remove")
                rm_reason = st.selectbox("Reason for Removal", ["Beyond Economic Repair", "Technological Obsolescence", "Accidental Damage", "Upgraded/Replaced", "Vandalized"])
                rm_val = st.number_input("Est. Value at Removal (Br)", min_value=0.0)
                rm_tech = st.text_input("Authorized By")
                st.warning("Note: This will log the asset as removed. Ensure you manually remove it from the 'Asset Registry' tab to update active inventory.")
                if st.form_submit_button("🗑️ Confirm Removal"):
                    rem_ws.append_row([datetime.now().strftime("%Y-%m-%d"), rm_cat, rm_sub, rm_code, rm_reason, rm_val, rm_tech])
                    st.success("Asset removal logged!"); st.rerun()

    elif menu == "🔎 Asset Registry":
        st.subheader("🔎 Master Registry")
        edited_df = st.data_editor(df_inv, use_container_width=True, hide_index=True)
        if st.button("💾 Sync Database"):
            inv_ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
            st.success("Database synced!"); st.rerun()








































































































































