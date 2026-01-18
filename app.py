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
        if user == "admin" and pwd == "aae123":
            st.session_state["password_correct"] = True
            if "password" in st.session_state: del st.session_state["password"]
            if "username" in st.session_state: del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("<div style='text-align: center; padding: 20px;'><h2 style='color: #1e3a8a;'>AAE Executive Portal</h2><p>Electromechanical Master Database Login</p></div>", unsafe_allow_html=True)
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
    # --- 1. HIERARCHY & RCA ---
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

    # --- 2. CONNECTION ---
    def init_connection():
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        try:
            creds_dict = st.secrets["gcp_service_account"]
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            client = gspread.authorize(creds)
            sh = client.open_by_url(st.secrets["SHEET_URL"])
            inv = sh.worksheet("Sheet1")
            try:
                maint = sh.worksheet("Maintenance_Log")
            except:
                maint = sh.add_worksheet(title="Maintenance_Log", rows="1000", cols="6")
                maint.append_row(["Date", "Category", "Subsystem", "Asset Code", "Failure Cause", "Technician"])
            return inv, maint
        except Exception as e:
            st.error(f"Connection Error: {e}")
            return None, None

    inv_ws, maint_ws = init_connection()

    # --- 3. DATA ENGINE ---
    def load_data(worksheet):
        if not worksheet: return pd.DataFrame()
        data = worksheet.get_all_values()
        if len(data) < 2: return pd.DataFrame()
        headers = [str(h).strip() for h in data[0]]
        df = pd.DataFrame(data[1:], columns=headers)
        # Dynamic conversion of all numeric columns (Qty, Health, Cost, Life, Age)
        for col in df.columns:
            if any(x in col.lower() for x in ['qty', 'total', 'cost', 'value', 'func', 'life', 'age']):
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df

    # --- 4. UI STYLING ---
    st.set_page_config(page_title="AAE Executive Portal", layout="wide")
    logo_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Logo_of_the_Addis_Ababa%E2%80%93Adama_Expressway.png/300px-Logo_of_the_Addis_Ababa%E2%80%93Adama_Expressway.png"
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
            <p style="margin:0; opacity: 0.9;">Asset Life-Age & Sustainability Analytics</p>
        </div>
    """, unsafe_allow_html=True)

    df_inv = load_data(inv_ws)
    df_maint = load_data(maint_ws)

    if st.sidebar.button("🔓 Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    menu = st.sidebar.radio("Navigation", ["📊 Smart Dashboard", "🔎 Asset Registry", "📝 Add New Asset", "🛠️ Failure Logs"])

    # --- 5. SMART DASHBOARD ---
    if menu == "📊 Smart Dashboard":
        if df_inv.empty:
            st.info("No data found. Please register assets.")
        else:
            v_col, q_col, f_col, c_col = df_inv.columns[7], df_inv.columns[4], df_inv.columns[5], df_inv.columns[0]
            s_col = df_inv.columns[1] # Subsystem
            life_col, age_col = df_inv.columns[8], df_inv.columns[9]

            # Top Row Metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💰 Total Asset Value", f"{df_inv[v_col].sum():,.0f} Br")
            m2.metric("📦 Units Tracked", int(df_inv[q_col].sum()))
            health = (df_inv[f_col].sum() / df_inv[q_col].sum() * 100) if df_inv[q_col].sum() > 0 else 0
            m3.metric("🏥 System Health", f"{health:.1f}%")
            m4.metric("🚨 Maintenance Events", len(df_maint) if not df_maint.empty else 0)

            st.divider()

            # --- NEW PROFESSIONAL LIFE-AGE ANALYSIS BY SUBSYSTEM ---
            st.markdown("#### ⏳ Sustainability Analysis by Subsystem")
            df_inv['Remaining %'] = ((df_inv[life_col] - df_inv[age_col]) / df_inv[life_col] * 100).clip(0, 100).fillna(0)
            
            # Grouping by Subsystem for clearer view
            sub_age = df_inv.groupby(s_col).agg({age_col: 'mean', 'Remaining %': 'mean', v_col: 'sum'}).reset_index()
            
            col_viz1, col_viz2 = st.columns([7, 3])
            with col_viz1:
                # Professional Bubble Chart: Age vs Remaining Life by Subsystem
                fig_sub = px.scatter(sub_age, x=age_col, y='Remaining %', size=v_col, color=s_col,
                                     text=s_col, labels={age_col: "Avg. Service Age (Years)", 'Remaining %': "Avg. Remaining Life (%)"},
                                     title="Subsystem Replacement Priority Matrix")
                fig_sub.add_hrect(y0=0, y1=25, fillcolor="red", opacity=0.1, annotation_text="Critical Replacement Zone")
                fig_sub.update_traces(textposition='top center')
                fig_sub.update_layout(height=450, showlegend=False, plot_bgcolor='white')
                st.plotly_chart(fig_sub, use_container_width=True)
                

            with col_viz2:
                # Gauge for Sustainability Score
                overall_rem = df_inv['Remaining %'].mean()
                fig_sust = px.pie(values=[overall_rem, 100-overall_rem], hole=0.75,
                                  color_discrete_sequence=['#059669', '#f3f4f6'])
                fig_sust.update_layout(showlegend=False, height=350, margin=dict(t=0,b=0),
                                       annotations=[dict(text=f"{overall_rem:.0f}%<br>Useful Life<br>Remaining", x=0.5, y=0.5, font_size=20, showarrow=False)])
                st.plotly_chart(fig_sust, use_container_width=True)

            st.divider()

            # Row 2: Operational Health
            l_col, r_col = st.columns([1, 1])
            with l_col:
                st.markdown("#### ⚡ Operational Health Index (Subsystem)")
                # Health Bar Chart - Emerald Green
                h_df = df_inv.groupby(s_col).agg({q_col: 'sum', f_col: 'sum'}).reset_index()
                h_df['Health %'] = (h_df[f_col] / h_df[q_col] * 100).round(1).fillna(0)
                fig_bar = px.bar(h_df.sort_values('Health %'), x='Health %', y=s_col, orientation='h', 
                                 text='Health %', color_discrete_sequence=['#10b981'])
                fig_bar.update_traces(texttemplate='%{text}%', textposition='outside', marker_line_color='#064e3b', marker_line_width=1.5)
                fig_bar.update_layout(yaxis_title=None, xaxis_visible=False, height=400)
                st.plotly_chart(fig_bar, use_container_width=True)
                

            with r_col:
                st.markdown("#### 🎯 RCA Failure Distribution")
                if not df_maint.empty:
                    fig_sun = px.sunburst(df_maint, path=['Category', 'Subsystem', 'Failure Cause'], color_discrete_sequence=px.colors.qualitative.Prism)
                    fig_sun.update_layout(height=400, margin=dict(t=0,b=0,l=0,r=0))
                    st.plotly_chart(fig_sun, use_container_width=True)
                else:
                    st.info("No failures logged yet.")

    # --- RETAINED MODULES: REGISTRY, ADD ASSET, FAILURE LOGS ---
    elif menu == "🔎 Asset Registry":
        st.subheader("🔎 Master Registry (Sheet1)")
        edited_df = st.data_editor(df_inv, use_container_width=True, hide_index=True)
        if st.button("💾 Sync Data"):
            inv_ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
            st.success("Database Updated!"); st.rerun()

    elif menu == "📝 Add New Asset":
        st.subheader("📝 New Equipment Registration")
        c1, c2 = st.columns(2)
        sel_cat = c1.selectbox("Major Category", list(AAE_STRUCTURE.keys()))
        sel_sub = c2.selectbox("Subsystem", AAE_STRUCTURE.get(sel_cat, []))
        with st.form("reg_form", clear_on_submit=True):
            a_code = st.text_input("Asset Code")
            a_qty = st.number_input("Quantity", min_value=1)
            a_cost = st.number_input("Unit Cost", min_value=0.0)
            life = st.number_input("Design Life (Years)", min_value=1, value=10)
            if st.form_submit_button("🚀 Commit to Database"):
                inv_ws.append_row([sel_cat, sel_sub, a_code, "Nos", a_qty, a_qty, a_cost, a_qty*a_cost, life, 0, 0])
                st.success("Asset Registered!"); st.rerun()

    elif menu == "🛠️ Failure Logs":
        st.subheader("🛠️ Technical Incident Logging")
        l1, l2 = st.columns(2)
        m_cat = l1.selectbox("Major Category", list(AAE_STRUCTURE.keys()))
        m_sub = l2.selectbox("Subsystem", AAE_STRUCTURE.get(m_cat, []))
        with st.form("maint_form", clear_on_submit=True):
            m_cause = st.text_input("Root Cause / Problem")
            m_code = st.text_input("Asset Code")
            m_tech = st.text_input("Technician Name")
            if st.form_submit_button("⚠️ Log Incident"):
                maint_ws.append_row([datetime.now().strftime("%Y-%m-%d"), m_cat, m_sub, m_code, m_cause, m_tech])
                st.success("Incident Recorded!"); st.rerun()
        st.dataframe(df_maint, use_container_width=True)


























































































































