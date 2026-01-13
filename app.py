import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os

# --- 1. SECURE CONNECTION LOGIC ---
def connect_gs():
    try:
        # This looks for the [gcp_service_account] block in your Streamlit Settings
        if "gcp_service_account" in st.secrets:
            creds_info = dict(st.secrets["gcp_service_account"])
            
            # This fixes the common private_key formatting error
            if "private_key" in creds_info:
                creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
                
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
            client = gspread.authorize(creds)
            return client.open("Asset_Damage_System")
        else:
            st.error("⚠️ Secrets not found! Please paste them in the Streamlit Cloud Settings panel.")
            return None
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

# Initialize global connection
gc = connect_gs()

# The rest of your program follows...




