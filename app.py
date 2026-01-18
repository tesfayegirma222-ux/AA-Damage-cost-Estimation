import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 0. AUTHENTICATION SYSTEM (STABLE & SECURE) ---
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
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

# --- PROCEED ONLY IF AUTHENTICATED ---
if check_password():
    # --- 1. AAE OFFICIAL HIERARCHY ---
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

    # --- 2. SECURE CONNECTION ---
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
        for i, col in enumerate(df.columns):
            if any(k in col.lower() for k in ['qty', 'total', 'cost', 'value', 'func', 'life', 'age']):
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df

    # --- 4. UI STYLING & SIDEBAR ---
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
            <p style="margin:0; opacity: 0.9;">Strategic Asset Management & RCA Dashboard</p>
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
            st.info("Inventory is empty. Please register assets.")
        else:
            # Mapping columns based on typical sheet structure
            v_col, q_col, f_col, c_col = df_inv.columns[7], df_inv.columns[4], df_inv.columns[5], df_inv.columns[0]
            life_col, used_col = df_inv.columns[8], df_inv.columns[9]
            
            # Metrics
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("💰 Portfolio Value", f"{df_inv[v_col].sum():,.0f} Br")
            k2.metric("📦 Active Assets", int(df_inv[q_col].sum()))
            health = (df_inv[f_col].sum() / df_inv[q_col].sum() * 100) if df_inv[q_col].sum() > 0 else 0
            k3.metric("🏥 Health Index", f"{health:.1f}%")
            k4.metric("🚨 Total Failures", len(df_maint) if not df_maint.empty else 0)

            st.divider()

            # --- LIFE-AGE ANALYSIS SECTION ---
            st.markdown("#### ⏳ Asset Life-Age & Sustainability Analysis")
            col_age1, col_age2 = st.columns([6, 4])
            
            with col_age1:
                # Calculate Remaining Life Percentage
                df_inv['Remaining %'] = ((df_inv[life_col] - df_inv[used_col]) / df_inv[life_col] * 100).clip(0, 100).fillna(0)
                fig_age = px.scatter(df_inv, x=used_col, y='Remaining %', size=v_col, color=c_col,
                                     hover_name=df_inv.columns[2], 
                                     labels={used_col: "Years in Service", 'Remaining %': "Remaining Useful Life (%)"},
                                     title="Asset Replacement Matrix (Size = Investment Value)")
                fig_age.add_hline(y=20, line_dash="dot", line_color="red", annotation_text="Critical Zone")
                fig_age.update_layout(height=400, plot_bgcolor='white')
                st.plotly_chart(fig_age, use_container_width=True)

            with col_age2:
                avg_rem = df_inv['Remaining %'].mean()
                fig_gauge = px.pie(values=[avg_rem, 100-avg_rem], names=['Remaining', 'Consumed'], hole=0.7,
                                   color_discrete_sequence=['#10b981', '#f1f5f9'])
                fig_gauge.update_layout(showlegend=False, height=350, 
                                        annotations=[dict(text=f"{avg_rem:.1f}%<br>Life<br>Remaining", x=0.5, y=0.5, font_size=18, showarrow=False)])
                st.plotly_chart(fig_gauge, use_container_width=True)

            st.divider()
            
            # Health and Distribution Row
            l_col, r_col = st.columns([1, 1])
            with l_col:
                st.markdown("#### ⚡ System Health (High Visibility)")
                h_df = df_inv.groupby(c_col).agg({q_col: 'sum', f_col: 'sum'}).reset_index()
                h_df['Health %'] = (h_df[f_col] / h_df[q_col] * 100).round(1).fillna(0)
                fig_bar = px.bar(h_df.sort_values('Health %'), x='Health %', y=c_col, orientation='h', 
                                 text='Health %', color='Health %', color_continuous_scale='Greens', range_x=[0, 125])
                fig_bar.update_traces(texttemplate='%{text}%', textposition='outside', 
                                      marker_line_color='#064e3b', marker_line_width=1.5, marker_color='#10b981')
                fig_bar.update_layout(yaxis_title=None, xaxis_visible=False, height=400, coloraxis_showscale=False)
                st.plotly_chart(fig_bar, use_container_width=True)

            with r_col:
                st.markdown("#### 💎 Asset Valuation")
                fig_pie = px.pie(df_inv, values=v_col, names=c_col, hole=0.5, color_discrete_sequence=px.colors.qualitative.Prism)
                st.plotly_chart(fig_pie, use_container_width=True)

            st.divider()
            st.markdown("#### 🎯 Root Cause Analysis (RCA) Hierarchy")
            if not df_maint.empty:
                fig_sun = px.sunburst(df_maint, path=['Category', 'Subsystem', 'Failure Cause'], color='Category', 
                                     color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_sun, use_container_width=True)

    # --- 6. REGISTRATION MODULE ---
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

    # --- 7. FAILURE LOGGING MODULE ---
    elif menu == "🛠️ Failure Logs":
        st.subheader("🛠️ Technical Incident Logging")
        l1, l2 = st.columns(2)
        m_cat = l1.selectbox("Major Category", list(AAE_STRUCTURE.keys()))
        m_sub = l2.selectbox("Subsystem", AAE_STRUCTURE.get(m_cat, []))
        with st.form("maint_form", clear_on_submit=True):
            m_cause = st.selectbox("Root Cause", RCA_STANDARDS.get(m_cat, ["General Issue"]) + ["Wear & Tear", "Vandalism"])
            m_code = st.text_input("Asset Code")
            m_tech = st.text_input("Technician Name")
            if st.form_submit_button("⚠️ Log Incident"):
                maint_ws.append_row([datetime.now().strftime("%Y-%m-%d"), m_cat, m_sub, m_code, m_cause, m_tech])
                st.success("Log recorded!"); st.rerun()
        st.dataframe(df_maint, use_container_width=True, hide_index=True)

    # --- 8. REGISTRY MANAGEMENT ---
    elif menu == "🔎 Asset Registry":
        st.subheader("🔎 Master Registry (Sheet1)")
        edited_df = st.data_editor(df_inv, use_container_width=True, hide_index=True)
        if st.button("💾 Sync Database"):
            inv_ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
            st.success("Database synced!"); st.rerun()

























































































































