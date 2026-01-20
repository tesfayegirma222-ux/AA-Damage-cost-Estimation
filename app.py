import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 0. AUTHENTICATION SYSTEM ---
def check_password():
    def password_entered():
        user = st.session_state.get("username")
        pwd = st.session_state.get("password")
        if user == "admin" and pwd == "password":
            st.session_state["password_correct"] = True
            if "password" in st.session_state: del st.session_state["password"]
            if "username" in st.session_state: del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("<div style='text-align: center; padding: 20px;'><h2 style='color: #1e3a8a;'>AAE Electro Mechanical Asset Portal</h2><p>AAE Electromechanical Asset Master Database</p></div>", unsafe_allow_html=True)
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
        "Electric Power Source(Generator)": ["Electric Utility", "Generator", "Solar Power System"],
        "Electric Power Distribution": ["ATS", "Main Breaker", "Distribution Panel", "Power Cable", "Transformer"],
        "UPS System": ["UPS Unit", "UPS Battery Bank", "Inverter"],
        "CCTV System": ["Lane Camera", "Booth Camera", "Road Camera", "PTZ Camera", "NVR/Server"],
        "Auto-Railing System": ["Electrical Motor", "Barrier Controller/MRC board", "Loop Detector", "Arm"],
        "HVAC System": ["Air Conditioning Unit", "Ventilation Fan", "Chiller"],
        "Illumination System": ["High Mast Light", "Road Light", "Booth Light", "Plaza Light", "Photocell Controller"],
        "Electronic Display System": ["VMS", "LED Notice Board", "Money Fee Display", "Passage Signal Lamp", "Fog Light"],
        "Pump System": ["Surface Water Pump", "Submersible Pump", "Fire Pump", "Pump Controller"],
        "Overload System (WIM)": ["Weight-In-Motion Sensor", "WIM Controller", "Inductive Loop", "Charging Controller"]
    }

    RCA_STANDARDS = {
        "Electric Power Source(Generator)": ["Fuel Contamination", "AVR Failure", "Battery Dead", "Utility Outage", "Aging"],
        "Electric Power Distribution": ["MCB Tripped", "Contact Burnout", "Insulation Failure", "Loose Connection", "Aging"],
        "CCTV System": ["Connector Corrosion", "Power Supply Fault", "IP Conflict", "Lens Fogging", "Aging"],
        "Auto-Railing System": ["Lack of Lubrication", "Dirty or Obstructed Tracks", "Worn-Out component", "Mis alignment", "Rust or Corrosion", "Aging"],
        "HVAC System": ["Clogged or Dirty Air Filters ", "Refrigerant Leaks ", "Faulty Capacitors and Relays", "Dirty Condenser/Evaporator Coils", "Clogged Condensate Drain Lines", "Lack of Motor Lubrication/Bearing Failure"],
        "Illumination System": ["Burnt-out Lamps", "Overheating", "Wiring Issues:", "Overloaded Circuits", "Aging"],
        "Electronic Display System": ["Overheating", "Capacitor Failure", "Improper Cleaning", "environmental condition", "Aging"],
        "Pump System": ["Lack of lubrication", "Cavitation", "Mis alignment", "Dry running", "Loose wiring", "Corrosion", "Aging"],
        "UPS System": ["Battery aging", "Loose connection", "High temprature", "Load exceeds ups capacity", "Invertor failure", "Human error", "Aging"],
        "General": ["Vandalism", "Physical Accident", "Extreme Weather", "Wear & Tear", "Aging"]
    }

    PM_TASKS = {
        "Electric Power Source(Generator)": ["Fuel Level Check", "Battery Voltage Test", "Air Filter Change", "Coolant Level Check", "Oil Change", "Generator Load Test","Cooling system inspection",  "Exhaust system Inspection", "Oil Change" ],
        "Electric Power Distribution": ["Infrared Thermography", "Tightening Terminals", "Breaker Exercise", "Cleaning Busbars", "Transformer Oil Test"],
        "UPS System": ["Battery Discharge Test", "Capacitor Inspection", "Fan Dusting", "Tightening Terminals", "Firmware Check"],
        "CCTV System": ["Lens Cleaning", "Housing Inspection", "Connector Waterproofing", "Storage Integrity Check", "Focus Adjustment"],
        "Auto-Railing System": ["Motor Lubrication", "Controller Syncing", "Loop Sensitivity Test", "Spring Tension Adjustment", "Limit Switch Test"],
        "HVAC System": ["Filter Replacement", "Condenser Cleaning", "Refrigerant Leak Test", "Thermostat Calibration", "Drain Line Flush"],
        "Illumination System": ["Lamp Replacement", "Photocell Test", "Timer Calibration", "Wiring Insulation Test", "Fixture Cleaning"],
        "Electronic Display System": ["Pixel Test", "Cooling Fan Check", "Brightness Calibration", "Data Cable Inspection", "Enclosure Sealing"],
        "Pump System": ["Mechanical Seal Check", "Bearing Lubrication", "Impeller Inspection", "Pressure Gauge Calibration", "Valve Exercise"],
        "Overload System (WIM)": ["Sensor Calibration", "Loop Resistance Test", "Drainage Cleaning", "Junction Box Sealing"],
        "General": ["Visual Inspection", "Cleaning", "Tightening Connections", "Lubrication", "Functionality Test"]
    }

    LOCATIONS = ["KM2", "KM16", "KM33", "KM52", "KM60A", "KM60B", "KM64", "KM78", "Along roadside", "others"]

    def init_connection():
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        try:
            creds_dict = st.secrets["gcp_service_account"]
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            client = gspread.authorize(creds)
            sh = client.open_by_url(st.secrets["SHEET_URL"])
            inv = sh.worksheet("Sheet1")
            
            try: maint = sh.worksheet("Maintenance_Log")
            except:
                maint = sh.add_worksheet(title="Maintenance_Log", rows="1000", cols="7")
                maint.append_row(["Date", "Category", "Subsystem", "Asset Code", "Failure Cause", "Technician", "Location"])
            
            try: prev = sh.worksheet("Preventive_Log")
            except:
                prev = sh.add_worksheet(title="Preventive_Log", rows="1000", cols="7")
                prev.append_row(["Date", "Category", "Subsystem", "Asset Code", "Task Performed", "Status", "Location"])
            
            return inv, maint, prev
        except Exception as e:
            st.error(f"Connection Error: {e}")
            return None, None, None

    inv_ws, maint_ws, prev_ws = init_connection()

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
    
    # --- SIDEBAR LOGOS ---
    logo_url = "https://inquisitive-azure-n8rlqionj0.edgeone.app/asset.jpg"
    st.sidebar.image(logo_url, use_container_width=True)
      # --- SIDEBAR LOGO ---
    logo_url = "https://physical-magenta-dzvxdrxnhh.edgeone.app/electrical.jpg"
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
            <h1 style="margin:0; font-size: 24px;">AAE ELECTRO-MECHANICAL ASSET PORTAL</h1>
            <p style="margin:0; opacity: 0.9;">Strategic EM Asset Management & PM/RCA Dashboard</p>
        </div>
    """, unsafe_allow_html=True)

    df_inv = load_data(inv_ws)
    df_maint = load_data(maint_ws)
    df_prev = load_data(prev_ws)

    if st.sidebar.button("🔓 Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Asset Registry", "📝 Add New Asset", "🛠️ Failure Logs", "📅 Preventive Maintenance"])

    if menu == "📊 Smart Dashboard":
        if df_inv.empty:
            st.info("Inventory is empty.")
        else:
            v_col, q_col, f_col, c_col = df_inv.columns[7], df_inv.columns[4], df_inv.columns[5], df_inv.columns[0]
            s_col, id_col = df_inv.columns[1], df_inv.columns[2]
            life_col, used_col = df_inv.columns[8], df_inv.columns[9]
            
            total_val = df_inv[v_col].sum()
            if total_val >= 1_000_000: display_val = f"{total_val/1_000_000:.2f}M Br"
            elif total_val >= 1_000: display_val = f"{total_val/1_000:.1f}K Br"
            else: display_val = f"{total_val:,.0f} Br"

            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("💰 Portfolio Value", display_val, help=f"Exact Value: {total_val:,.2f} Br")
            k2.metric("📦 Active Assets", int(df_inv[q_col].sum()))
            health_idx = (df_inv[f_col].sum() / df_inv[q_col].sum() * 100) if df_inv[q_col].sum() > 0 else 0
            k3.metric("🏥 Health Index", f"{health_idx:.1f}%")
            k4.metric("🛠️ Failures Logged", len(df_maint) if not df_maint.empty else 0)
            k5.metric("📅 PM Activities", len(df_prev) if not df_prev.empty else 0)

            st.divider()

            st.markdown("#### ⏳ Asset Life-Age & Sustainability Analysis")
            col_age1, col_age2 = st.columns([6, 4])
            df_inv['Remaining %'] = ((df_inv[life_col] - df_inv[used_col]) / df_inv[life_col] * 100).clip(0, 100).fillna(0).round(1)
            with col_age1:
                fig_age = px.scatter(df_inv, x=used_col, y='Remaining %', size=v_col, color=s_col, hover_name=id_col, title="Asset Replacement Matrix")
                fig_age.add_hline(y=20, line_dash="dot", line_color="red")
                st.plotly_chart(fig_age, use_container_width=True)
            with col_age2:
                st.markdown("##### ⚠️ Replacement Watchlist")
                critical_df = df_inv[df_inv['Remaining %'] <= 20][[id_col, s_col, 'Remaining %']]
                warning_df = df_inv[(df_inv['Remaining %'] > 20) & (df_inv['Remaining %'] <= 40)][[id_col, s_col, 'Remaining %']]
                tab1, tab2 = st.tabs(["🔴 Critical (<20%)", "🟡 Warning (20-40%)"])
                with tab1:
                    if not critical_df.empty: st.dataframe(critical_df.sort_values('Remaining %'), hide_index=True, use_container_width=True)
                    else: st.success("No assets in critical zone.")
                with tab2:
                    if not warning_df.empty: st.dataframe(warning_df.sort_values('Remaining %'), hide_index=True, use_container_width=True)
                    else: st.info("No assets in warning zone.")

            st.divider()

            col_h1, col_h2 = st.columns(2)
            with col_h1:
                st.markdown("#### ⚡ System Health")
                h_df = df_inv.groupby(c_col).agg({q_col: 'sum', f_col: 'sum'}).reset_index()
                h_df['Health %'] = (h_df[f_col] / h_df[q_col] * 100).round(1).fillna(0)
                fig_bar = px.bar(h_df.sort_values('Health %'), x='Health %', y=c_col, orientation='h', text='Health %', color='Health %', color_continuous_scale='Greens')
                fig_bar.update_traces(texttemplate='%{text}%', textposition='outside')
                st.plotly_chart(fig_bar, use_container_width=True)
            with col_h2:
                st.markdown("#### 💎 Valuation by Subsystem")
                fig_pie = px.pie(df_inv, values=v_col, names=s_col, hole=0.5)
                st.plotly_chart(fig_pie, use_container_width=True)

            st.divider()

            st.markdown("#### 🎯 Root Cause Analysis (RCA) & Maintenance Breakdown")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                if not df_maint.empty:
                    rca_data = df_maint.groupby(['Category', 'Failure Cause']).size().reset_index(name='Incidents')
                    cat_totals = df_maint.groupby('Category').size().reset_index(name='Total_Cat')
                    rca_final = rca_data.merge(cat_totals, on='Category')
                    rca_final['%'] = (rca_final['Incidents'] / rca_final['Total_Cat'] * 100).round(1)
                    fig_rca = px.bar(rca_final, x='Incidents', y='Category', color='Failure Cause', orientation='h',
                                     text=rca_final.apply(lambda x: f"{x['Failure Cause']} ({x['%']}%)", axis=1), title="Incident Root Causes")
                    fig_rca.update_traces(textposition='inside')
                    fig_rca.update_layout(barmode='stack', showlegend=False)
                    st.plotly_chart(fig_rca, use_container_width=True)
                else: st.info("No failure logs.")

            with col_r2:
                # --- UPDATED PM CHART: Grouped by Category with Activity Labels ---
                if not df_prev.empty:
                    pm_data = df_prev.groupby(['Category', 'Task Performed']).size().reset_index(name='Count')
                    pm_cat_totals = df_prev.groupby('Category').size().reset_index(name='Total_PM')
                    pm_final = pm_data.merge(pm_cat_totals, on='Category')
                    
                    fig_pm = px.bar(pm_final, 
                                   x='Count', 
                                   y='Category', 
                                   color='Task Performed', 
                                   orientation='h',
                                   text=pm_final.apply(lambda x: f"{x['Task Performed']} ({x['Count']})", axis=1),
                                   title="PM Frequency by Category & Activity")
                    
                    fig_pm.update_traces(textposition='inside')
                    fig_pm.update_layout(barmode='stack', showlegend=False, xaxis_title="Total Activities", yaxis_title="Category")
                    st.plotly_chart(fig_pm, use_container_width=True)
                else: st.info("No PM logs.")

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

    elif menu == "🛠️ Failure Logs":
        st.subheader("🛠️ Technical Failure Logging")
        l1, l2 = st.columns(2)
        m_cat = l1.selectbox("Major Category", list(AAE_STRUCTURE.keys()))
        m_sub = l2.selectbox("Subsystem", AAE_STRUCTURE.get(m_cat, []))
        with st.form("maint_form", clear_on_submit=True):
            m_cause = st.selectbox("Root Cause", RCA_STANDARDS.get(m_cat, ["General Issue"]) + ["Wear & Tear", "Vandalism"])
            m_code = st.text_input("Asset Code")
            m_tech = st.text_input("Technician Name")
            m_loc = st.selectbox("Location", LOCATIONS)
            if st.form_submit_button("⚠️ Log Incident"):
                maint_ws.append_row([datetime.now().strftime("%Y-%m-%d"), m_cat, m_sub, m_code, m_cause, m_tech, m_loc])
                st.success("Log recorded!"); st.rerun()
        st.dataframe(df_maint, use_container_width=True, hide_index=True)

    elif menu == "📅 Preventive Maintenance":
        st.subheader("📅 Preventive Activity Logging")
        p1, p2 = st.columns(2)
        p_cat = p1.selectbox("Category", list(AAE_STRUCTURE.keys()))
        p_sub = p2.selectbox("Subsystem", AAE_STRUCTURE.get(p_cat, []))
        with st.form("preventive_form", clear_on_submit=True):
            p_code = st.text_input("Asset Code")
            p_task = st.selectbox("Maintenance Task", PM_TASKS.get(p_cat, PM_TASKS["General"]))
            p_stat = st.selectbox("Condition", ["Excellent", "Good", "Needs Repair"])
            p_loc = st.selectbox("Location", LOCATIONS)
            if st.form_submit_button("✅ Log PM"):
                prev_ws.append_row([datetime.now().strftime("%Y-%m-%d"), p_cat, p_sub, p_code, p_task, p_stat, p_loc])
                st.success("PM Logged!"); st.rerun()
        st.dataframe(df_prev, use_container_width=True, hide_index=True)

    elif menu == "🔎 Asset Registry":
        st.subheader("🔎 Master Registry")
        edited_df = st.data_editor(df_inv, use_container_width=True, hide_index=True)
        if st.button("💾 Sync Database"):
            inv_ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
            st.success("Database synced!"); st.rerun()



































































































































































