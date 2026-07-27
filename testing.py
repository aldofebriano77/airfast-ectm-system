"""
========================================================================================
 ENTERPRISE ENGINE CONDITION & FLEET MAINTENANCE CONTROL SYSTEM (FINAL RELEASE v4.2)
 PT. AIRFAST INDONESIA | DHC-6 TWIN OTTER / P&WC PT6A-34 FLEET
========================================================================================
 Architecture : Standalone Enterprise SaaS (Streamlit / Plotly / Multi-Linear Regression)
 Compliance   : P&WC PT6A-34 Fault Isolation Manual (P/N 3021242, Rev 75.0)
 Enhancements : - [v4.0] Single Source of Truth (SSOT) via EngineHealth Enum
                - [v4.1] Zero-Gap Sticky Header & Standardized Aviation Terminology
                - [v4.2] Tier 1 UI/UX Upgrade: OCC Fleet Heatmap, Visual RUL Horizon,
                         and Structured Maintenance Directive Cards.
========================================================================================
"""

import io
import os
import re
import smtplib
import hashlib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import plotly.express as px

try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

# ======================================================================================
# 1. PAGE CONFIGURATION & SYSTEM INITIALIZATION
# ======================================================================================
_icon_path = "airfasticon.png"
_page_icon = _icon_path if os.path.exists(_icon_path) else "\u2708\ufe0f"

st.set_page_config(
    page_title="AIRFAST Indonesia ECTM Dashboard",
    page_icon=_page_icon,
    layout="wide",
)

# ======================================================================================
# EXECUTIVE DASHBOARD HEADER (STICKY TOP & COMPACT LOGO)
# ======================================================================================
sticky_header_html = """
<div class="sticky-header-box">
    <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
        <div>
            <h1 style="margin: 0; padding: 0; font-size: 1.6rem !important; color: #003B6F; font-weight: 800; letter-spacing: -0.02em;">Engine Condition Trend Monitoring Dashboard</h1>
            <p style="margin: 2px 0 0 0; padding: 0; font-size: 0.85rem; font-weight: 600; color: #475569;">PT. AIRFAST Indonesia | DHC-6 / P&WC PT6A-34 Engine Telemetry</p>
        </div>
        <div style="text-align: right;">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 45" width="180" height="40">
              <g transform="translate(0, 2)">
                <path d="M 20 2 L 40 42 L 30 42 L 20 20 L 10 42 L 0 42 Z" fill="#003B6F"/>
                <path d="M 20 15 L 28 32 L 20 24 L 12 32 Z" fill="#F0B73D"/>
              </g>
              <g transform="translate(52, 28)">
                <text x="0" y="0" font-family="'Plus Jakarta Sans', 'Segoe UI', sans-serif" font-size="22" font-weight="800" fill="#003B6F" letter-spacing="1">ALDO</text>
                <text x="65" y="0" font-family="'Plus Jakarta Sans', 'Segoe UI', sans-serif" font-size="22" font-weight="300" fill="#64748B" letter-spacing="1">AEROSPACE</text>
              </g>
            </svg>
        </div>
    </div>
</div>
"""
st.markdown(sticky_header_html, unsafe_allow_html=True)

# ======================================================================================
# 2. OEM CONSTANTS, FIM THRESHOLDS & ABSOLUTE HEALTH STATE
# Source: PT6A-34 Fault Isolation Manual, P/N 3021242, Rev 75.0
# ======================================================================================
class EngineHealth(Enum):
    NORMAL = 1
    ADVISORY = 2
    CRITICAL = 3

SHIFT_T5_C = 5.0        
SHIFT_NG_PCT = 0.5      
SHIFT_WF_PCT = 2.0      

T5_WASH_C = 10.0                
T5_BORESCOPE_C = 15.0           
NG_BORESCOPE_LOW_PCT = -1.0     
NG_BORESCOPE_HIGH_PCT = -1.5    

OIL_PRESS_DROP_PSI = 5.0
OIL_TEMP_RISE_C = 5.0

SUSTAIN_WINDOW = 3              
TREND_WINDOW = 10               
CONTROL_SIGMA = 2.5             

# [PATCH #7] Menambahkan 'AML No' sebagai relational key utama antar ketiga file
REQUIRED_COLUMNS = ["Date", "Engine", "T5", "Ng", "Wf"]
FLEET_REGISTRATIONS = ["PK-OAM", "PK-OCH", "PK-OCG", "PK-OCI", "PK-OCF"]
CORRECTION_CANDIDATES = ["IOAT", "Press_Alt", "TQ", "Np"]
OPTIONAL_COLUMNS = ["AML No"] + CORRECTION_CANDIDATES + ["IAS", "Oil_Temp", "Oil_Press"]

NAVY = "#003B6F"
GOLD = "#f0b73d"
SLATE_DARK = "#0F172A"
SLATE_MUTED = "#64748B"

# ======================================================================================
# 3. ULTRA-MODERN AVIATION SAAS STYLING (TIER 1 UI/UX OVERHAUL & ZERO-WASTE SPACE)
# ======================================================================================
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; -webkit-font-smoothing: antialiased; }

    /* [PEMANGKASAN RUANG KOSONG] Memaksimalkan lebar layar dan memangkas padding atas/bawah */
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 1.5rem !important;
        padding-left: 2.2rem !important;
        padding-right: 2.2rem !important;
        max-width: 98% !important;
    }
    
    [data-testid="stAppViewContainer"], [data-testid="stApp"], .main {
        background-color: #F8FAFC !important; color: #0F172A !important;
    }
    [data-testid="stHeader"] { background-color: transparent !important; }
    
    /* Tipografi yang Lebih Padat & Bersih */
    h1, h2, h3, h4 { color: #00284D !important; font-weight: 800 !important; letter-spacing: -0.03em !important; margin-top: 0rem !important; }
    h1 { font-size: 1.85rem !important; }
    h2 { font-size: 1.35rem !important; }
    h3 { font-size: 1.1rem !important; font-weight: 700 !important; }

    /* ==========================================================================
       1. MODERN SEGMENTED TABS (MENGGANTIKAN TAB KAKU STREAMLIT)
       ========================================================================== */
    div[data-testid="stTabs"] button[role="tab"] {
        background-color: transparent !important; border: none !important;
        border-radius: 8px 8px 0 0 !important; font-weight: 700 !important;
        padding: 8px 18px !important; color: #64748B !important;
        font-size: 0.9rem !important; transition: all 0.2s ease !important;
    }
    div[data-testid="stTabs"] button[role="tab"]:hover {
        color: #003B6F !important; background-color: rgba(0, 59, 111, 0.03) !important;
    }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        color: #003B6F !important; border-bottom: 3px solid #f0b73d !important;
        background-color: rgba(0, 59, 111, 0.05) !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: transparent !important; }

    /* ==========================================================================
       2. COMPACT METRIC CARDS WITH HOVER LIFT
       ========================================================================== */
    div[data-testid="stMetric"] {
        background: #FFFFFF !important; border: none !important;
        border-radius: 12px !important; padding: 14px 18px !important;
        box-shadow: 0 4px 15px -2px rgba(0, 40, 77, 0.04), 0 0 2px 1px rgba(0, 40, 77, 0.02) !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important; position: relative; overflow: hidden;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px); box-shadow: 0 8px 20px -4px rgba(0, 40, 77, 0.08) !important;
    }
    div[data-testid="stMetric"]::before {
        content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
        background: linear-gradient(90deg, #003B6F 0%, #f0b73d 100%);
    }
    div[data-testid="stMetricLabel"] > label > p {
        color: #64748B !important; font-weight: 700 !important; font-size: 0.74rem !important;
        text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0px !important;
    }
    div[data-testid="stMetricValue"] > div { 
        color: #0F172A !important; font-weight: 800 !important; font-size: 1.5rem !important; 
        letter-spacing: -0.02em; margin-top: 2px;
    }

    /* ==========================================================================
       3. INTERACTIVE EXPANDER & CONTAINER CARDS
       ========================================================================== */
    div[data-testid="stExpander"] {
        border: 1px solid #E2E8F0 !important; border-radius: 10px !important;
        background: #FFFFFF !important; box-shadow: 0 2px 6px rgba(0,0,0,0.02) !important;
        overflow: hidden !important; transition: all 0.2s ease !important;
    }
    div[data-testid="stExpander"]:hover { border-color: #CBD5E1 !important; }
    div[data-testid="stExpander"] summary { font-weight: 700 !important; color: #003B6F !important; padding: 10px 14px !important; }

    /* ==========================================================================
       4. SIDEBAR & BUTTONS (COMPACT PILL NAV)
       ========================================================================== */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #00284D 0%, #00172D 100%) !important; 
        border-right: none !important; box-shadow: 4px 0 20px rgba(0, 0, 0, 0.12);
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] div, [data-testid="stSidebar"] b { color: #F1F5F9 !important; }
    
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        padding: 10px 16px !important; margin-bottom: 4px !important;
        background: transparent !important; border: none !important;
        cursor: pointer; transition: all 0.2s ease; width: 100%; border-radius: 8px !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background-color: rgba(255, 255, 255, 0.06) !important; transform: translateX(3px);
    }
    [data-testid="stSidebar"] div[role="radiogroup"] p {
        font-size: 0.88rem !important; font-weight: 600 !important; color: #94A3B8 !important; margin: 0 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"] {
        background: linear-gradient(90deg, rgba(240, 183, 61, 0.15) 0%, rgba(255, 255, 255, 0.05) 100%) !important;
        box-shadow: inset 3px 0 0 #f0b73d !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"] p { color: #FFFFFF !important; font-weight: 800 !important; }
    [data-testid="stSidebar"] div[data-baseweb="radio"] div[role="radio"] { display: none !important; }

    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, #003B6F 0%, #00284D 100%) !important; 
        color: #FFFFFF !important; font-weight: 700 !important; font-size: 0.88rem !important;
        border-radius: 8px !important; padding: 10px 20px !important; border: none !important; 
        box-shadow: 0 4px 10px rgba(0, 59, 111, 0.2) !important; transition: all 0.2s ease !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        transform: translateY(-2px); box-shadow: 0 6px 14px rgba(0, 59, 111, 0.3) !important;
        background: linear-gradient(135deg, #00488A 0%, #00305C 100%) !important; color: #f0b73d !important;
    }

    div[data-testid="stDownloadButton"] > button, div[data-testid="stButton"] > button[kind="secondary"] {
        background: #FFFFFF !important; color: #003B6F !important; font-weight: 700 !important; 
        font-size: 0.85rem !important; border-radius: 8px !important; border: 1px solid #E2E8F0 !important; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important; transition: all 0.2s ease !important;
    }
    div[data-testid="stDownloadButton"] > button:hover, div[data-testid="stButton"] > button[kind="secondary"]:hover {
        background: #F8FAFC !important; border-color: #003B6F !important; transform: translateY(-1px);
    }

    div[data-testid="stButton"] > button.red-logout-btn {
        background: linear-gradient(135deg, #DC2626 0%, #991B1B 100%) !important; color: #FFFFFF !important; 
        border: none !important; font-weight: 700 !important; border-radius: 8px !important;
    }
    div[data-testid="stButton"] > button.red-logout-btn:hover {
        background: linear-gradient(135deg, #EF4444 0%, #B91C1C 100%) !important; transform: translateY(-1px);
    }

    /* ==========================================================================
       5. BADGES & HEATMAP CARDS (TIGHTER PROFILE)
       ========================================================================== */
    .badge-red { background: rgba(220, 38, 38, 0.08); color: #DC2626; border: 1px solid rgba(220, 38, 38, 0.2); border-radius: 20px; padding: 4px 12px; font-weight: 800; font-size: 0.72rem; letter-spacing: 0.05em; text-transform: uppercase; display: inline-block; }
    .badge-amber { background: rgba(217, 119, 6, 0.08); color: #D97706; border: 1px solid rgba(217, 119, 6, 0.2); border-radius: 20px; padding: 4px 12px; font-weight: 800; font-size: 0.72rem; letter-spacing: 0.05em; text-transform: uppercase; display: inline-block; }
    .badge-green { background: rgba(22, 163, 74, 0.08); color: #16A34A; border: 1px solid rgba(22, 163, 74, 0.2); border-radius: 20px; padding: 4px 12px; font-weight: 800; font-size: 0.72rem; letter-spacing: 0.05em; text-transform: uppercase; display: inline-block; }
    
    .heatmap-card {
        background: #FFFFFF; border: none; border-radius: 12px; padding: 14px; margin-bottom: 12px;
        box-shadow: 0 4px 15px -2px rgba(0, 40, 77, 0.05), 0 0 2px 1px rgba(0, 40, 77, 0.02);
        transition: all 0.2s ease;
    }
    .heatmap-card:hover { transform: translateY(-3px); box-shadow: 0 8px 22px -4px rgba(0, 40, 77, 0.1); }
    .heatmap-reg { font-size: 1.15rem; font-weight: 800; color: #00284D; letter-spacing: -0.02em; }
    .heatmap-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; border-radius: 6px; margin-top: 5px; font-size: 0.8rem; font-weight: 700; }
    
    .hm-green { background: rgba(22, 163, 74, 0.06); color: #16A34A; border: 1px solid rgba(22, 163, 74, 0.15); }
    .hm-amber { background: rgba(217, 119, 6, 0.06); color: #D97706; border: 1px solid rgba(217, 119, 6, 0.15); }
    .hm-red { background: rgba(220, 38, 38, 0.06); color: #DC2626; border: 1px solid rgba(220, 38, 38, 0.15); }
    
    .rec-card-box { background: #FFFFFF; border: none; border-radius: 12px; padding: 16px; margin-bottom: 14px; box-shadow: 0 4px 15px -2px rgba(0, 40, 77, 0.04); }
    .rec-card-red { border-left: 5px solid #DC2626; }
    .rec-card-amber { border-left: 5px solid #D97706; }
    .rec-card-green { border-left: 5px solid #16A34A; }
    .rec-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #F1F5F9; padding-bottom: 10px; margin-bottom: 12px; }
    .rec-title { font-size: 1.08rem; font-weight: 800; color: #00284D; }

    .rul-box { 
        background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%); border: none; border-left: 4px solid #f0b73d;
        padding: 14px 16px; border-radius: 10px; margin-top: 8px; margin-bottom: 8px; box-shadow: 0 4px 12px -2px rgba(0, 40, 77, 0.04);
    }
    .rul-title { font-size: 0.74rem; font-weight: 800; color: #64748B; text-transform: uppercase; letter-spacing: 0.06em; }
    .rul-val { font-size: 1.25rem; font-weight: 800; color: #00284D; margin-top: 2px; }
    .rul-sub { font-size: 0.78rem; font-weight: 600; color: #64748B; margin-top: 2px; }

    .fim-ref { display: inline-block; background: #F1F5F9; color: #334155; border-radius: 4px; padding: 2px 8px; font-size: 0.72rem; font-weight: 700; margin-left: 6px; }
    
    div[data-testid="stElementContainer"]:has(.sticky-header-box),
    div.element-container:has(.sticky-header-box) {
        position: sticky !important;
        top: 0 !important;
        z-index: 9999 !important;
        background: rgba(248, 250, 252, 0.88) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border-bottom: 1px solid rgba(226, 232, 240, 0.9) !important;
        padding-top: 15px !important;
        padding-bottom: 14px !important; /* Tetap aman agar teks 'y', 'g', 'p' tidak kepotong */
        margin-bottom: -18px !important; /* [KUNCI]: Menetralkan flex-gap Streamlit agar judul tertarik naik */
    }
    
    /* Memaksa kontainer judul tepat di bawah header untuk merapat ke atas */
    div[data-testid="stElementContainer"]:has(.sticky-header-box) + div[data-testid="stElementContainer"],
    div.element-container:has(.sticky-header-box) + div.element-container {
        margin-top: -8px !important;
        padding-top: 0px !important;
    }

    hr { border: none !important; height: 1px !important; background: #E2E8F0 !important; margin: 16px 0 !important; }
    .gold-bar { height: 3px; width: 40px; background: linear-gradient(90deg, #003B6F 0%, #f0b73d 100%); border-radius: 4px; margin-top: -4px; margin-bottom: 16px; }
</style>
""",
    unsafe_allow_html=True,
)

# ======================================================================================
# 4. SESSION STATE MANAGEMENT & CALLBACK HELPERS (AUTHENTICATION INTEGRATED)
# ======================================================================================
if "active_menu" not in st.session_state:
    st.session_state["active_menu"] = "Home (Fleet Matrix)"
if "target_use_correction" not in st.session_state:
    st.session_state["target_use_correction"] = True
if "target_baseline_n" not in st.session_state:
    st.session_state["target_baseline_n"] = 6
if "target_engine" not in st.session_state:
    st.session_state["target_engine"] = None
if "filter_reg_kw" not in st.session_state:
    st.session_state["filter_reg_kw"] = None

def _hash_pw(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

USER_DATABASE = {
    "admin@airfastindonesia.com": {
        "password_hash": _hash_pw("admin123"),
        "role": "Chief Engineer / Admin",
        "name": "Aldo Febriano Artha Chandra"
    },
    "engineer@airfastindonesia.com": {
        "password_hash": _hash_pw("eng123"),
        "role": "Powerplant Engineer",
        "name": "Rochadin Bakdha Aji"
    },
    "officer@airfastindonesia.com": {
        "password_hash": _hash_pw("entry123"),
        "role": "Data Entry Officer",
        "name": "Line Maintenance Staff"
    }
}

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_email" not in st.session_state:
    st.session_state["user_email"] = ""
if "user_name" not in st.session_state:
    st.session_state["user_name"] = "Guest Viewer"
if "user_role" not in st.session_state:
    st.session_state["user_role"] = "Guest / Viewer"

def navigate_to_menu(menu_name: str, reg_filter: str = None):
    st.session_state["active_menu"] = menu_name
    if reg_filter:
        st.session_state["filter_reg_kw"] = reg_filter

if not st.session_state.get("logged_in", False):
    st.markdown("""
        <style>
            [data-testid="stSidebar"] { display: none !important; }
            [data-testid="collapsedControl"] { display: none !important; }
            [data-testid="stHeader"] { display: none !important; }
            
            /* [UI/UX UPGRADE] Menghilangkan border default st.form agar tidak ada kotak ganda */
            div[data-testid="stForm"] {
                border: none !important;
                padding: 0px !important;
            }
            
            /* Memberikan bayangan halus, sudut 16px, dan aksen top-gradient navy/gold pada kartu login */
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.login-portal-marker) > div {
                border-radius: 16px !important;
                border: 1px solid #CBD5E1 !important;
                box-shadow: 0 10px 30px -5px rgba(0, 40, 77, 0.08), 0 0 5px 1px rgba(0, 40, 77, 0.03) !important;
                background: #FFFFFF !important;
                position: relative;
                overflow: hidden;
                padding: 28px 32px !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.login-portal-marker) > div::before {
                content: ""; position: absolute; top: 0; left: 0; right: 0; height: 5px;
                background: linear-gradient(90deg, #003B6F 0%, #f0b73d 100%);
            }
            
            /* Presisi jarak pembatas bawah logo agar pas dan tidak terlalu mepet atau longgar */
            .login-divider {
                height: 1px;
                background-color: #E2E8F0;
                margin: 12px 0px 18px 0px;
            }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 1.35, 1])
    
    with col_l2:
        with st.container(border=True):
            # Penanda gaib untuk target CSS styling kartu login di atas
            st.markdown("<div class='login-portal-marker'></div>", unsafe_allow_html=True)
            
            # Badge kapsul penanda keamanan sistem
            st.markdown("""
            <div style="text-align:center; margin-bottom: 12px;">
                <span style="background:rgba(0, 59, 111, 0.06); color:#003B6F; font-size:0.7rem; font-weight:800; padding:5px 14px; border-radius:20px; border:1px solid rgba(0, 59, 111, 0.15); letter-spacing:0.08em;">
                    SECURE AIRWORTHINESS PORTAL
                </span>
            </div>
            """, unsafe_allow_html=True)
            
            logo_path = "images.png"  
            if os.path.exists(logo_path):
                col_logo1, col_logo2, col_logo3 = st.columns([1, 1.6, 1])
                with col_logo2:
                    st.image(logo_path, use_container_width=True)
            else:
                st.markdown("<h2 style='text-align:center; color:#003B6F; margin-top:5px; margin-bottom:0px;'>AIRFAST INDONESIA</h2>", unsafe_allow_html=True)
            
            # Garis pembatas proporsional dan deskripsi sistem
            st.markdown("""
            <div class="login-divider"></div>
            <div style="text-align:center; margin-bottom:22px;">
                <h3 style="color:#00284D; font-size:1.15rem; font-weight:800; margin-bottom:4px;">Engine Condition Trend Monitoring</h3>
                <p style="color:#64748B; font-size:0.85rem; font-weight:500; margin:0; line-height:1.4;">
                    Please authenticate with authorized engineering credentials to access airworthiness telemetry and maintenance logbooks.
                </p>
            </div>
            """, unsafe_allow_html=True)

            # [border=False] Kunci utama menghilangkan kotak ganda di form login
            with st.form("fullscreen_login_form", clear_on_submit=False, border=False):
                input_email = st.text_input("Corporate Email Address", placeholder="user@airfastindonesia.com").strip()
                input_password = st.text_input("Password", type="password", placeholder="••••••••")

                st.write("")
                c_btn1, c_btn2 = st.columns(2)
                with c_btn1:
                    btn_login = st.form_submit_button("Login to Portal", type="primary", use_container_width=True)
                with c_btn2:
                    btn_guest = st.form_submit_button("Continue as Guest", use_container_width=True)
                    
                if btn_login:
                    if input_email in USER_DATABASE and USER_DATABASE[input_email]["password_hash"] == _hash_pw(input_password):
                        user_info = USER_DATABASE[input_email]
                        st.session_state["logged_in"] = True
                        st.session_state["user_email"] = input_email
                        st.session_state["user_name"] = user_info["name"]
                        st.session_state["user_role"] = user_info["role"]
                        st.success("Authorization successful! Redirecting to dashboard...")
                        st.rerun()
                    else:
                        st.error("Invalid corporate email or password.")
                        
                if btn_guest:
                    st.session_state["logged_in"] = True
                    st.session_state["user_email"] = "guest.auditor@airfast.com"
                    st.session_state["user_name"] = "External Auditor / Guest"
                    st.session_state["user_role"] = "Guest / Viewer"
                    st.rerun()
            
            # Access Notice diubah menjadi kotak callout terstruktur yang rapi
            st.markdown("""
            <div style="background:#F8FAFC; border-left:3px solid #64748B; padding:10px 14px; border-radius:6px; margin-top:14px; border: 1px solid #F1F5F9; border-left-width:3px;">
                <p style="color:#64748B; font-size:0.75rem; line-height:1.4; margin:0;">
                    <b style="color:#334155;">Access Notice:</b> This is an internal access gate for the ECTM prototype, not a substitute for a production authentication/audit system. Do not reuse real corporate credentials here.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
    st.stop()

# ======================================================================================
# 5. DATA NORMALIZATION & INGESTION MODULE
# ======================================================================================
def safe_parse_dates(series: pd.Series) -> pd.Series:
    iso_date_only = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    iso_with_time = pd.to_datetime(series, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    parsed = iso_date_only.fillna(iso_with_time)

    remaining_mask = parsed.isna()
    if remaining_mask.any():
        fallback = pd.to_datetime(series[remaining_mask], format="mixed", dayfirst=True, errors="coerce")
        parsed = parsed.mask(remaining_mask, fallback)
    return parsed

def process_maintenance_reports(df_rep: pd.DataFrame) -> pd.DataFrame:
    if df_rep.empty:
        return pd.DataFrame(columns=['AML No', 'Date', 'Registration', 'ATA', 'ATA_Desc', 'Note / Report', 'Corrective Action', 'Position', 'P/N Off', 'P/N On'])
    
    df_rep = df_rep.copy()
    if 'Date' in df_rep.columns:
        df_rep['Date'] = safe_parse_dates(df_rep['Date'])
    if 'Note / Report' in df_rep.columns and 'Date' in df_rep.columns:
        df_rep = df_rep.dropna(subset=['Note / Report', 'Date'])
        
    if 'Registration' not in df_rep.columns:
        if 'AML No' in df_rep.columns:
            def ext_reg(val):
                if not isinstance(val, str): return "UNKNOWN"
                match = re.search(r"(PK-[A-Z0-9]{3,4})", val.upper())
                if match: return match.group(1)
                p = val.split('-')[0].strip().upper()
                if re.fullmatch(r"[A-Z0-9]{3,4}", p):
                    return f"PK-{p}"
                return p if p else "UNKNOWN"
            df_rep['Registration'] = df_rep['AML No'].apply(ext_reg)
        else:
            df_rep['Registration'] = "PK-OAM"

    if 'ATA_Desc' not in df_rep.columns:
        ata_map = {
            21: "21 - Air Conditioning", 22: "22 - Auto Flight", 23: "23 - Communications",
            24: "24 - Electrical Power", 25: "25 - Equipment / Furnishings", 26: "26 - Fire Protection",
            27: "27 - Flight Controls", 28: "28 - Fuel System", 29: "29 - Hydraulic Power",
            30: "30 - Ice & Rain Protection", 31: "31 - Indicating / Recording Systems",
            32: "32 - Landing Gear", 33: "33 - Lights", 34: "34 - Navigation",
            45: "45 - Central Maintenance System (CAS)", 52: "52 - Doors", 53: "53 - Fuselage",
            55: "55 - Stabilizers", 56: "56 - Windows", 57: "57 - Wings",
            61: "61 - Propellers", 71: "71 - Powerplant General", 72: "72 - Engine",
            73: "73 - Engine Fuel & Control", 74: "74 - Ignition", 77: "77 - Engine Indicating",
            78: "78 - Exhaust", 79: "79 - Engine Oil", 80: "80 - Starting"
        }
        if 'ATA' in df_rep.columns:
            df_rep['ATA_Desc'] = df_rep['ATA'].map(lambda x: ata_map.get(int(x) if pd.notnull(x) and str(x).isdigit() else x, f"ATA {x} - General"))
        else:
            df_rep['ATA_Desc'] = "71 - Powerplant General"
            
    return df_rep.sort_values('Date', ascending=False) if 'Date' in df_rep.columns else df_rep

def init_all_datasets():
    rng = np.random.default_rng(101)
    rows_ectm = []
    
    fleet_scenarios = [
        ("PK-OAM | LH (SN: PC-E101)", 0.28, -0.010, 0.45, 624.0, 91.50, 288.0, "WASH_RECOVERY"),
        ("PK-OAM | RH (SN: PC-E102)", 0.02, -0.001, 0.05, 625.5, 91.60, 290.5, "ISOLATED_SPIKE"),
        ("PK-OCH | LH (SN: PC-E103)", 0.45, -0.035, 0.85, 623.0, 91.45, 289.0, "BORESCOPE_CRITICAL"),
        ("PK-OCH | RH (SN: PC-E104)", -0.15, -0.020, -0.60, 626.0, 91.55, 291.0, "PNEUMATIC_LEAK"),
        ("PK-OCG | LH (SN: PC-E105)", 0.12, -0.005, 0.25, 624.5, 91.50, 289.5, "ADVISORY_WATCH"),
        ("PK-OCG | RH (SN: PC-E106)", 0.01,  0.001, 0.02, 622.0, 91.70, 287.5, "NORMAL_OPTIMAL"),
    ]
    total_cycles = 60
    
    for eng_id, t5_d, ng_d, wf_d, b_t5, b_ng, b_wf, scenario in fleet_scenarios:
        for i in range(total_cycles):
            ioat = 14.0 + 4.5 * np.sin(i / 5.0) + rng.normal(0, 0.8)
            alt = 10500 + rng.normal(0, 350)
            tq = 42.5 + rng.normal(0, 0.4)
            
            t5_phys = b_t5 + 0.42 * (ioat - 14.0) + rng.normal(0, 0.4)
            ng_phys = b_ng - 0.015 * (ioat - 14.0) + rng.normal(0, 0.05)
            wf_phys = b_wf + 0.90 * (ioat - 14.0) + rng.normal(0, 0.6)
            
            if scenario == "WASH_RECOVERY":
                drift_factor = i if i < 40 else max(0, (i - 40) * 0.1)
                t5_phys += t5_d * drift_factor
                ng_phys += ng_d * drift_factor
                wf_phys += wf_d * drift_factor
            elif scenario == "ISOLATED_SPIKE":
                spike = 1.0 if i == 25 else 0.0
                t5_phys += (t5_d * i) + (14.5 * spike)
                ng_phys += (ng_d * i) - (0.8 * spike)
                wf_phys += (wf_d * i) + (6.0 * spike)
            elif scenario == "BORESCOPE_CRITICAL":
                t5_phys += t5_d * i + (0.05 * (i ** 1.3))
                ng_phys += ng_d * i - (0.001 * (i ** 1.4))
                wf_phys += wf_d * i + (0.08 * (i ** 1.2))
            elif scenario == "PNEUMATIC_LEAK":
                t5_phys += t5_d * i
                ng_phys += ng_d * i
                wf_phys += wf_d * i
            else:
                t5_phys += t5_d * i
                ng_phys += ng_d * i
                wf_phys += wf_d * i
                
            reg_prefix = eng_id.split("|")[0].strip()
            aml_str = f"{reg_prefix[3:]}-2026-{(i+1):03d}"
            
            rows_ectm.append(dict(
                **{"AML No": aml_str},
                Date=pd.Timestamp("2026-05-01") + pd.Timedelta(days=i),
                Engine=eng_id, Press_Alt=round(alt, 0), IOAT=round(ioat, 1),
                IAS=round(135.0 + rng.normal(0, 1.5), 1), TQ=round(tq, 1), Np=75,
                T5=round(t5_phys, 1), Ng=round(ng_phys, 2), Wf=round(wf_phys, 1),
                Oil_Temp=round(71.0 + 0.05 * i + rng.normal(0, 0.4), 1), 
                Oil_Press=round(92.0 - 0.02 * i + rng.normal(0, 0.3), 1),
            ))
    df_ectm = pd.DataFrame(rows_ectm)

    util_file_candidates = ["Flight Utilization DHC6-400.xlsx", "Flight Utilization DHC6-400.xlsx"]
    df_util = pd.DataFrame()
    util_is_real = False
    for util_file in util_file_candidates:
        if os.path.exists(util_file):
            try:
                df_util = pd.read_excel(util_file)
                df_util['Work (Date)'] = safe_parse_dates(df_util['Work (Date)'])
                df_util = df_util.dropna(subset=['Registration', 'Work (Date)']).sort_values('Work (Date)')
                util_is_real = not df_util.empty
            except Exception:
                df_util = pd.DataFrame()
            break

    if df_util.empty:
        util_rows = []
        for reg in FLEET_REGISTRATIONS:
            for d in range(60):
                fc = int(rng.choice([2, 4, 6, 8], p=[0.2, 0.4, 0.3, 0.1]))
                fh = round(fc * rng.uniform(0.6, 0.9), 1)
                aml_str = f"{reg[3:]}-2026-{(d+1):03d}"
                util_rows.append(dict(
                    **{"AML No": aml_str},
                    Registration=reg,
                    **{'Work (Date)': pd.Timestamp("2026-05-01") + pd.Timedelta(days=d)},
                    FH=fh, FC=fc, **{'Block Hours': round(fh * 1.1, 1)},
                    From="WAY", To="TIM"
                ))
        df_util = pd.DataFrame(util_rows)

    rep_file = "Pilot & Maintenance Report DHC6-400.xlsx"
    rep_is_real = False
    if os.path.exists(rep_file):
        try:
            df_rep = pd.read_excel(rep_file)
            rep_is_real = not df_rep.empty
        except Exception:
            df_rep = pd.DataFrame()
    else:
        df_rep = pd.DataFrame()

    if df_rep.empty:
        df_rep = pd.DataFrame([
            {"AML No": "OAM-2026-041", "Date": "2026-06-10", "Registration": "PK-OAM", "ATA": 71, "ATA_Desc": "71 - Powerplant General", "Note / Report": "Pilot reported engine T5 ITT running 8 deg C above normal during cruise at 10,000 ft.", "Corrective Action": "Performed Compressor Performance Recovery Wash per AMM 71-00-00. Ground run test SAT. ITT dropped by 7 deg C.", "Position": "LH", "P/N Off": np.nan, "P/N On": np.nan, "S/N Off": np.nan, "S/N On": np.nan},
            {"AML No": "OAM-2026-026", "Date": "2026-05-26", "Registration": "PK-OAM", "ATA": 77, "ATA_Desc": "77 - Engine Indicating", "Note / Report": "ITT cockpit gauge flickered and showed momentary high spike during climb.", "Corrective Action": "Checked ITT wiring harness and thermocouple terminal connections. Found loose ground wire. Re-torqued and tested SAT.", "Position": "RH", "P/N Off": "3021100", "P/N On": "3021100", "S/N Off": "TH-991", "S/N On": "TH-992"},
            {"AML No": "OCH-2026-051", "Date": "2026-06-20", "Registration": "PK-OCH", "ATA": 72, "ATA_Desc": "72 - Engine", "Note / Report": "High T5 trend paired with Ng drop. Suspected CT vane erosion or bleed valve leak.", "Corrective Action": "Scheduled engine for mandatory borescope inspection. Replaced faulty compressor bleed valve assembly.", "Position": "LH", "P/N Off": "3100250-01", "P/N On": "3100250-01", "S/N Off": "BV-102", "S/N On": "BV-884"},
            {"AML No": "OCH-2026-036", "Date": "2026-06-05", "Registration": "PK-OCH", "ATA": 73, "ATA_Desc": "73 - Engine Fuel & Control", "Note / Report": "All engine parameters (Ng, ITT, Wf) reading slightly lower than baseline at cruise power.", "Corrective Action": "Inspected P3 pneumatic sensing line. Found minor air leak at FCU Bellows B-nut fitting. Re-sealed and leak tested SAT.", "Position": "RH", "P/N Off": np.nan, "P/N On": np.nan, "S/N Off": np.nan, "S/N On": np.nan},
            {"AML No": "OCG-2026-046", "Date": "2026-06-15", "Registration": "PK-OCG", "ATA": 79, "ATA_Desc": "79 - Engine Oil", "Note / Report": "Oil temperature slightly elevated by 3 deg C over the last 10 sectors.", "Corrective Action": "Inspected oil cooler matrix and cleaned external dust accumulation. Re-verified oil pressure relief valve setting.", "Position": "LH", "P/N Off": np.nan, "P/N On": np.nan, "S/N Off": np.nan, "S/N On": np.nan},
        ])

    df_rep = process_maintenance_reports(df_rep)
    return df_ectm, df_util, df_rep, util_is_real, rep_is_real

if "df_data" not in st.session_state or "df_util" not in st.session_state or "df_rep" not in st.session_state:
    e_df, u_df, r_df, u_is_real, r_is_real = init_all_datasets()
    st.session_state["df_data"] = e_df
    st.session_state["df_util"] = u_df
    st.session_state["df_rep"] = r_df
    st.session_state["util_is_real"] = u_is_real
    st.session_state["rep_is_real"] = r_is_real

def csv_template() -> bytes:
    cols = ["AML No"] + REQUIRED_COLUMNS + [c for c in OPTIONAL_COLUMNS if c not in REQUIRED_COLUMNS and c != "AML No"]
    example = pd.DataFrame([{"AML No": "OAM-2026-032", "Date": "2026-06-01", "Engine": "PK-OAM | LH (SN: PC-E101)", "Press_Alt": 11000, "IOAT": 12.0, "IAS": 135.0, "TQ": 42.0, "Np": 75, "T5": 624.0, "Ng": 91.50, "Wf": 288.0, "Oil_Temp": 72.5, "Oil_Press": 91.0}])
    example = example[[c for c in cols if c in example.columns]]
    buf = io.StringIO()
    example.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def validate_columns(df: pd.DataFrame):
    missing_required = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    available_correction = [c for c in CORRECTION_CANDIDATES if c in df.columns]
    return missing_required, available_correction

# ======================================================================================
# 6. AUTOMATED DATA QUALITY AUDIT MODULE
# ======================================================================================
def run_data_quality_audit(df: pd.DataFrame) -> list:
    alerts = []
    if not df.empty:
        if "IOAT" in df.columns:
            if (df["IOAT"] > 55.0).any() or (df["IOAT"] < -40.0).any():
                alerts.append("[PHYSICAL OUTLIER] IOAT exceeds standard operational atmospheric envelope (-40°C to +55°C).")
        if "T5" in df.columns and (df["T5"] <= 0).any():
            alerts.append("[SENSOR ERROR] T5 recorded at or below 0°C during engine operation.")
        
        for col in ["T5", "Ng", "Wf"]:
            if col in df.columns and len(df) >= 3:
                stuck_mask = (df[col].diff() == 0) & (df[col].diff().shift(-1) == 0)
                if stuck_mask.any():
                    alerts.append(f"[SENSOR FREEZE SUSPECTED] Column '{col}' contains identical consecutive static values for 3+ cycles.")
    return alerts

# ======================================================================================
# 7. THERMODYNAMIC LEAST-SQUARES REGRESSION & ADAPTIVE NOISE BANDING
# ======================================================================================
def fit_correction_model(df_baseline: pd.DataFrame, predictors: list, target: str):
    usable = [p for p in predictors if df_baseline[p].std(ddof=0) > 1e-6]
    if len(usable) == 0 or len(df_baseline) < len(usable) + 2:
        mean_val = df_baseline[target].mean() if not df_baseline.empty else 0.0
        return {"mode": "mean", "predictors": [], "coef": np.array([mean_val]), "downgraded": True}
    X = df_baseline[usable].astype(float).values
    X = np.column_stack([np.ones(len(X)), X])
    y = df_baseline[target].astype(float).values
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {"mode": "regression", "predictors": usable, "coef": coef, "downgraded": False}

def apply_correction_model(model: dict, df: pd.DataFrame) -> np.ndarray:
    if model["mode"] == "mean":
        return np.full(len(df), model["coef"][0])
    X = df[model["predictors"]].astype(float).values
    X = np.column_stack([np.ones(len(X)), X])
    return X @ model["coef"]

@st.cache_data(show_spinner=False)
def compute_engine_trend(df_engine: pd.DataFrame, baseline_n: int, use_correction: bool):
    df_engine = df_engine.sort_values("Date").reset_index(drop=True)
    
    # [PATCH HOLE 1] Mencegah crash akibat sel kosong (NaN) pada sensor IOAT/Alt/TQ/Np
    corr_cols_present = [c for c in CORRECTION_CANDIDATES if c in df_engine.columns]
    if corr_cols_present:
        df_engine[corr_cols_present] = df_engine[corr_cols_present].ffill().bfill().fillna(0.0)
        
    n = max(2, min(baseline_n, len(df_engine)))
    # ... (sisa kode ke bawah tetap sama persis)
    df_baseline = df_engine.iloc[:n]
    predictors = [c for c in CORRECTION_CANDIDATES if c in df_engine.columns] if use_correction else []
    models = {}
    is_downgraded = False
    
    for target in ["T5", "Ng", "Wf"]:
        models[target] = fit_correction_model(df_baseline, predictors, target)
        if models[target].get("downgraded", False) and use_correction and len(predictors) > 0:
            is_downgraded = True
        df_engine[f"{target}_pred"] = apply_correction_model(models[target], df_engine)
        df_engine[f"Delta_{target}"] = df_engine[target] - df_engine[f"{target}_pred"]
        
    df_engine["Delta_Ng_pct"] = df_engine["Delta_Ng"]
    baseline_wf_mean = df_baseline["Wf"].mean()
    df_engine["Delta_Wf_pct"] = 100 * df_engine["Delta_Wf"] / (baseline_wf_mean if baseline_wf_mean != 0 else 1.0)
    
    noise = {t: max(df_engine.loc[: n - 1, f"Delta_{t}"].std(ddof=0), 1e-6) for t in ["T5", "Ng", "Wf"]}
    for t in ["T5", "Ng", "Wf"]:
        rolling_std = df_engine[f"Delta_{t}"].rolling(window=TREND_WINDOW, min_periods=n).std()
        df_engine[f"Adaptive_Sigma_{t}"] = rolling_std.fillna(noise[t]).clip(lower=noise[t], upper=noise[t] * 3)

    df_engine.attrs["models"] = models
    df_engine.attrs["noise"] = noise
    df_engine.attrs["baseline_n"] = n
    df_engine.attrs["regression_downgraded"] = is_downgraded
    return df_engine

def rolling_slope(series: pd.Series, window: int) -> float:
    y = series.iloc[-window:].values
    if len(y) < 2: return 0.0
    x = np.arange(len(y))
    slope, _ = np.polyfit(x, y, 1)
    return float(slope)

def sustained_flag(series: pd.Series, threshold: float, window: int) -> bool:
    if len(series) < window: return False
    tail = series.iloc[-window:]
    half = abs(threshold) / 2
    return bool((tail > half).all()) if threshold > 0 else bool((tail < -half).all())

def isolated_spike_flag(series: pd.Series, threshold: float) -> bool:
    if len(series) < 2: return False
    last, prev = series.iloc[-1], series.iloc[-2]
    half = abs(threshold) / 2
    return bool(last > threshold and prev < half) if threshold > 0 else bool(last < threshold and prev > -half)

def detect_trend_acceleration(series: pd.Series, window: int) -> bool:
    if len(series) < window or window < 4: return False
    tail = series.iloc[-window:].rolling(3, min_periods=1).mean().values
    half = len(tail) // 2
    if half < 2: return False
    x_old, x_new = np.arange(half), np.arange(len(tail) - half)
    slope_old, _ = np.polyfit(x_old, tail[:half], 1)
    slope_new, _ = np.polyfit(x_new, tail[half:], 1)
    same_sign = (slope_old > 0 and slope_new > 0) or (slope_old < 0 and slope_new < 0)
    if not same_sign: return False
    if abs(slope_old) < 1e-6: return abs(slope_new) > 0.05
    return bool(abs(slope_new / slope_old) > 1.4)

# ======================================================================================
# 8. PREDICTIVE EXTRAPOLATION & UTILIZATION CORRELATION (RUL ENGINE)
# ======================================================================================
def calculate_rul(current_val: float, slope: float, threshold: float, direction: str = "UP"):
    if direction == "UP":
        if current_val >= threshold: return 0
        if slope <= 0.005: return 999
        cycles_left = (threshold - current_val) / slope
    else:
        if current_val <= threshold: return 0
        if slope >= -0.001: return 999
        cycles_left = (threshold - current_val) / slope
    return int(max(0, round(cycles_left)))

def get_aircraft_utilization_rate(reg: str, df_util: pd.DataFrame):
    if df_util.empty or reg not in df_util['Registration'].values:
        return 2.5 
    df_reg = df_util[df_util['Registration'] == reg]
    if len(df_reg) < 5: return 2.5
    date_min, date_max = df_reg['Work (Date)'].min(), df_reg['Work (Date)'].max()
    days = max(1, (date_max - date_min).days)
    total_fc = df_reg['FC'].sum()
    return max(0.5, total_fc / days)

# ======================================================================================
# 9. DIAGNOSTIC CLASSIFICATION & FIM DIRECTIVE GENERATION (SSOT ENGINE)
# ======================================================================================
def classify_direction(value, shift_band):
    if value > shift_band: return "UP"
    if value < -shift_band: return "DOWN"
    return "NORMAL"

def build_status(df_engine: pd.DataFrame, df_util: pd.DataFrame):
    latest = df_engine.iloc[-1]
    d_t5, d_ng, d_wf = latest["Delta_T5"], latest["Delta_Ng"], latest["Delta_Wf"]
    
    shift_t5 = classify_direction(d_t5, SHIFT_T5_C)
    shift_ng = classify_direction(d_ng, SHIFT_NG_PCT)
    shift_wf = classify_direction(latest["Delta_Wf_pct"], SHIFT_WF_PCT)
    
    alarm_wash = d_t5 >= T5_WASH_C
    alarm_borescope_t5 = d_t5 >= T5_BORESCOPE_C
    alarm_borescope_ng = d_ng <= NG_BORESCOPE_LOW_PCT
    
    sustained_t5 = sustained_flag(df_engine["Delta_T5"], T5_WASH_C, SUSTAIN_WINDOW)
    isolated_t5 = isolated_spike_flag(df_engine["Delta_T5"], T5_WASH_C)
    sustained_ng = sustained_flag(df_engine["Delta_Ng"], NG_BORESCOPE_LOW_PCT, SUSTAIN_WINDOW)
    isolated_ng = isolated_spike_flag(df_engine["Delta_Ng"], NG_BORESCOPE_LOW_PCT)
    
    dyn_sig_t5 = latest.get("Adaptive_Sigma_T5", df_engine.attrs.get("noise", {}).get("T5", 1))
    dyn_sig_ng = latest.get("Adaptive_Sigma_Ng", df_engine.attrs.get("noise", {}).get("Ng", 1))
    dyn_sig_wf = latest.get("Adaptive_Sigma_Wf", df_engine.attrs.get("noise", {}).get("Wf", 1))
    
    stat_band_breach = (abs(d_t5) > CONTROL_SIGMA * dyn_sig_t5 or abs(d_ng) > CONTROL_SIGMA * dyn_sig_ng or abs(d_wf) > CONTROL_SIGMA * dyn_sig_wf)

    is_abnormal = alarm_borescope_t5 or alarm_borescope_ng
    control_breach = stat_band_breach or alarm_wash or sustained_t5 or sustained_ng
    
    if is_abnormal:
        health_level = EngineHealth.CRITICAL
    elif control_breach:
        health_level = EngineHealth.ADVISORY
    else:
        health_level = EngineHealth.NORMAL

    status_label = {
        EngineHealth.NORMAL: "NORMAL TREND",
        EngineHealth.ADVISORY: "ADVISORY / WATCH",
        EngineHealth.CRITICAL: "CRITICAL / ABNORMAL"
    }[health_level]

    slope_t5 = rolling_slope(df_engine["Delta_T5"], TREND_WINDOW)
    slope_ng = rolling_slope(df_engine["Delta_Ng"], TREND_WINDOW)
    
    rul_t5_borescope = calculate_rul(d_t5, slope_t5, T5_BORESCOPE_C, "UP")
    rul_ng_borescope = calculate_rul(d_ng, slope_ng, NG_BORESCOPE_LOW_PCT, "DOWN")
    rul_cycles = min(rul_t5_borescope, rul_ng_borescope)
    # [BUG FIX] The RUL Horizon line on the trend chart previously always
    # plotted against T5, even when Ng was actually the closer (limiting)
    # threshold - the visual would then not match why that RUL number was
    # computed. Track which parameter actually drives the number so the
    # chart/labels can attribute it correctly.
    rul_limiting_param = "Ng" if rul_ng_borescope < rul_t5_borescope else "T5"

    accel_window = min(TREND_WINDOW * 2, len(df_engine))
    accel_t5 = detect_trend_acceleration(df_engine["Delta_T5"], accel_window)
    accel_ng = detect_trend_acceleration(df_engine["Delta_Ng"], accel_window)
    rul_is_linear_caution = bool(accel_t5 or accel_ng)
    rul_confidence = (
        "Low - trend is accelerating; linear extrapolation likely overstates remaining life"
        if rul_is_linear_caution else
        "Indicative only - assumes a constant (linear) degradation rate"
    )
    
    match_reg = re.search(r"(PK-[A-Z0-9]{3,4})", str(latest["Engine"]).upper())
    reg_prefix = match_reg.group(1) if match_reg else str(latest["Engine"]).split("|")[0].strip()
    
    fc_per_day = get_aircraft_utilization_rate(reg_prefix, df_util)
    days_left = int(rul_cycles / fc_per_day) if fc_per_day > 0 else 999
    days_left = min(days_left, 3650)
    proj_date = (datetime.now() + timedelta(days=days_left)).strftime("%Y-%m-%d") if rul_cycles < 999 else "Stable"
    
    return dict(
        latest=latest, d_t5=d_t5, d_ng=d_ng, d_wf=d_wf,
        shift_t5=shift_t5, shift_ng=shift_ng, shift_wf=shift_wf,
        alarm_wash=alarm_wash, alarm_borescope_t5=alarm_borescope_t5,
        alarm_borescope_ng=alarm_borescope_ng,
        sustained_t5=sustained_t5, isolated_t5=isolated_t5,
        sustained_ng=sustained_ng, isolated_ng=isolated_ng,
        control_breach=control_breach, is_abnormal=is_abnormal,
        health_level=health_level, status_label=status_label,
        slope_t5=slope_t5, slope_ng=slope_ng,
        rul_cycles=rul_cycles, rul_limiting_param=rul_limiting_param, proj_date=proj_date, fc_per_day=fc_per_day,
        rul_confidence=rul_confidence, rul_is_linear_caution=rul_is_linear_caution,
        reg_prefix=reg_prefix
    )

# [TIER 1 UPGRADE] Enhanced Recommendation Output with Structured Fields
def generate_recommendations(df_engine: pd.DataFrame, status: dict) -> list:
    recs = []
    sig_str = f"ΔT5: {status['d_t5']:+.1f}°C | ΔNg: {status['d_ng']:+.2f}% | ΔWf: {status['d_wf']:+.1f} PPH"
    
    if status["isolated_t5"] or status["isolated_ng"]:
        recs.append(dict(
            level="amber", 
            title="Possible Indicating System Anomaly (Isolated Point Shift)", 
            fim_ref="FIM Table 101, Note 2",
            priority="ROUTINE OBSERVATION",
            downtime="0 Hours (Deferred Action)",
            signature="Rapid single-cycle parameter shift inconsistent with thermodynamic regression trends.",
            body=("The latest observation indicates an isolated single-point deviation. "
                  "Per OEM manual guidance, isolated spikes are predominantly caused by instrumentation calibration drift or electrical transmitter faults.\n\n"
                  "**Line Engineering Directives:**\n1. Verify source flight-log entries to rule out transcription errors.\n"
                  "2. Conduct instrumentation calibration check on T5 / Ng cockpit indicators and engine transmitter units per AMM Ref. 77-00-00.\n"
                  "3. Defer invasive hardware maintenance; confirm whether shift persists across subsequent operating cycles.")
        ))
    if status["alarm_borescope_t5"] or status["alarm_borescope_ng"]:
        recs.append(dict(
            level="red", 
            title="Mandatory Hot-Section Borescope Inspection Required", 
            fim_ref="FIM Fig. 103 Sheet 9, Note 3",
            priority="IMMEDIATE GROUNDING",
            downtime="Est. 8 - 12 Hours (Invasive Inspection)",
            signature=f"Critical FIM Breach -> {sig_str}",
            body=(f"Thermodynamic residuals breached critical OEM limits: Delta T5 = **{status['d_t5']:+.1f} °C** (Limit: +15.0 °C) / "
                  f"Delta Ng = **{status['d_ng']:+.2f} %** (Limit: -1.0% to -1.5%).\n\n**Line Engineering Directives:**\n"
                  "1. Ground powerplant and schedule immediate hot-section borescope inspection per AMM Ref. 72-00-00.\n"
                  "2. Inspect combustion chamber liner, small exit duct, CT stator vanes, and CT rotor blades for thermal distortion or severe erosion.\n"
                  "3. Execute compressor performance recovery wash protocols upon completion of mechanical inspections.\n"
                  "4. If structural distress exceeds repairable AMM limits, route powerplant to an approved P&WC overhaul facility.")
        ))
    elif status["alarm_wash"] or status["sustained_t5"]:
        recs.append(dict(
            level="amber", 
            title="Compressor Performance Recovery Wash Recommended", 
            fim_ref="FIM Fig. 103 Sheet 9, Note 3",
            priority="NEXT MAINTENANCE WINDOW",
            downtime="Est. 3 - 4 Hours (Ground Wash & Run)",
            signature=f"Sustained Upward T5 Degradation -> {sig_str}",
            body=(f"Delta T5 demonstrates a sustained upward degradation trend reaching **{status['d_t5']:+.1f} °C** above installation baseline.\n\n"
                  "**Line Engineering Directives:**\n1. Execute compressor performance recovery wash per AMM Ref. 71-00-00.\n"
                  "2. Perform engine ground test run post-wash to confirm ITT recovery and re-verify baseline calibration.\n"
                  "3. Inspect fuel nozzle assemblies for spray pattern distortion if fuel flow deviation (ΔWf) is concurrently elevated.")
        ))
    t5, ng, wf = status["shift_t5"], status["shift_ng"], status["shift_wf"]
    if t5 == "UP" and ng == "DOWN" and wf == "UP":
        recs.append(dict(
            level="amber", 
            title="Compressor Aerodynamic Efficiency Loss / Bleed Valve Anomaly", 
            fim_ref="FIM Table 101 / Fig. 103",
            priority="NEXT MAINTENANCE WINDOW",
            downtime="Est. 4 - 6 Hours (Valve Check & Wash)",
            signature="ITT Increase | Ng Decrease | Fuel Flow Increase",
            body=("Thermodynamic Signature: **ITT Increase | Ng Decrease | Fuel Flow Increase**. Consistent with aerodynamic efficiency degradation.\n\n"
                  "**Line Engineering Directives:**\n1. Perform compressor desalination or performance recovery wash.\n"
                  "2. Inspect compressor bleed valve operation and diaphragm integrity (Ref. 75-30-00) to confirm full acoustic closure.\n"
                  "3. Execute visual and borescope examination of first-stage compressor blades for FOD per AMM Ref. 72-30-05.")
        ))
    elif t5 == "UP" and ng == "UP" and wf == "UP":
        recs.append(dict(
            level="amber", 
            title="Compressor Turbine Nozzle Area Enlargement", 
            fim_ref="FIM Table 101 / Fig. 103 Sheet 1",
            priority="PLANNED HSI SCHEDULING",
            downtime="Est. 1 - 2 Days (Hot Section Access)",
            signature="ITT Increase | Ng Increase | Fuel Flow Increase",
            body=("Thermodynamic Signature: **ITT Increase | Ng Increase | Fuel Flow Increase**. Consistent with effective nozzle area enlargement.\n\n"
                  "**Line Engineering Directives:**\n1. Schedule Hot Section Inspection (HSI) at next available maintenance window.\n"
                  "2. Inspect Compressor Turbine (CT) stator vanes for trailing-edge erosion, cracking, or bowing.\n"
                  "3. Verify power turbine vane ring class average specification per AMM Ref. 72-50-03.")
        ))
    elif t5 == "DOWN" and ng == "DOWN" and wf == "DOWN":
        recs.append(dict(
            level="amber", 
            title="Pneumatic Sensing Reference Leak / FCU Calibration Drift", 
            fim_ref="FIM Table 101",
            priority="NEXT MAINTENANCE WINDOW",
            downtime="Est. 2 - 3 Hours (Line Inspection & Leak Test)",
            signature="Uniform Downward Shift Across All Parameters",
            body=("Thermodynamic Signature: **Uniform downward shift across all parameters**. Indicates pneumatic sensing line leakage or FCU drift.\n\n"
                  "**Line Engineering Directives:**\n1. Inspect P3 and Py pneumatic sensing lines, fittings, and FCU bellows for leakage.\n"
                  "2. Conduct instrumentation calibration check on cockpit indicators and engine transmitter units.")
        ))
    
    if not recs:
        if status["health_level"] == EngineHealth.ADVISORY:
            recs.append(dict(
                level="amber", 
                title="Advisory Watch | Statistical Baseline Trend Deviation", 
                fim_ref="FIM Table 101 (Statistical Control)",
                priority="ROUTINE OBSERVATION",
                downtime="0 Hours (Operational)",
                signature=f"2.5-Sigma Noise Band Breach -> {sig_str}",
                body=("Thermodynamic residuals have exceeded the 2.5-sigma statistical noise band of the installation baseline, "
                      "although absolute values remain within OEM operational safety limits.\n\n"
                      "**Line Engineering Directives:**\n"
                      "1. Increase parameter logging frequency on subsequent flight cycles to monitor trend progression.\n"
                      "2. Verify IOAT and Pressure Altitude transmitter calibration to rule out atmospheric normalization drift.\n"
                      "3. No mechanical maintenance action required at this time; maintain advisory observation.")
            ))
        else:
            recs.append(dict(
                level="green", 
                title="Optimal Powerplant Condition | No Maintenance Action Required", 
                fim_ref="Normal Operations",
                priority="ROUTINE MONITORING",
                downtime="0 Hours (Optimal)",
                signature=f"Within Statistical Limits -> {sig_str}",
                body=("All monitored thermodynamic parameters remain within acceptable OEM operating tolerances. Condition-corrected residuals are stable.\n\n"
                      "**Line Engineering Directives:** Continue routine Engine Performance Logbook recording and periodic trend evaluations.")
            ))
    return recs

# ======================================================================================
# 10. PLOTLY VISUALIZATION ENGINE (WITH TIER 1 VISUAL RUL HORIZON)
# ======================================================================================
def make_trend_figure(df_engine: pd.DataFrame, engine_name: str, status: dict = None) -> go.Figure:
    fig = go.Figure()
    
    # [PATCH #16] Palet warna super kontras: Tidak ada satu pun garis yang warnanya sama!
    # Format: (Kolom, Label, Warna Actual, Warna Moving Average)
    specs = [
        ("Delta_T5", "\u0394 T5 (ITT) [\u00b0C]", "#DC2626", "#9333EA"),  # Red & Purple
        ("Delta_Ng", "\u0394 Ng [%]", "#003B6F", "#0891B2"),            # Navy & Teal/Cyan
        ("Delta_Wf", "\u0394 Wf [PPH]", "#D97706", "#16A34A")           # Amber & Emerald Green
    ]
    for col, label, color_act, color_ma in specs:
        fig.add_trace(go.Scatter(
            x=df_engine["Date"], y=df_engine[col], mode="lines+markers", name=label, 
            line=dict(color=color_act, width=2), marker=dict(size=5, color=color_act),
            hovertemplate="<b>%{y:+.2f}</b><extra></extra>"
        ))
        ma = df_engine[col].rolling(3, min_periods=1).mean().round(2)
        fig.add_trace(go.Scatter(
            x=df_engine["Date"], y=ma, mode="lines", name=f"{label} (3-cyc MA)", 
            line=dict(color=color_ma, width=1.8, dash="dot"), opacity=0.8, showlegend=True, hoverinfo="skip"
        ))

    if "Adaptive_Sigma_T5" in df_engine.columns:
        upper_vals = (CONTROL_SIGMA * df_engine["Adaptive_Sigma_T5"]).tolist()
        lower_vals = (-CONTROL_SIGMA * df_engine["Adaptive_Sigma_T5"]).tolist()
        x_vals = df_engine["Date"].tolist()
        
        fig.add_trace(go.Scatter(
            x=x_vals + x_vals[::-1],
            y=upper_vals + lower_vals[::-1],
            fill='toself', fillcolor='rgba(0, 59, 111, 0.05)',
            line=dict(color='rgba(255,255,255,0)'), hoverinfo="skip", showlegend=True, name="2.5σ Adaptive Noise Band"
        ))

    if status and status.get("rul_cycles", 999) < 100:
        latest_date = df_engine["Date"].max()
        proj_date = pd.to_datetime(status["proj_date"], errors="coerce")
        limiting = status.get("rul_limiting_param", "T5")
        if limiting == "Ng":
            horizon_y = [status["d_ng"], NG_BORESCOPE_LOW_PCT]
            horizon_label = "Est. Ng Borescope Horizon"
        else:
            horizon_y = [status["d_t5"], T5_BORESCOPE_C]
            horizon_label = "Est. T5 Borescope Horizon"
            
        # [PATCH #16] Warna garis Horizon dibedakan spesifik (Deep Magenta) agar tidak lebur dengan limit
        horizon_color = "#C026D3"

        if pd.notnull(proj_date) and proj_date > latest_date:
            fig.add_trace(go.Scatter(
                x=[latest_date, proj_date], y=horizon_y,
                mode="lines", name=horizon_label,
                line=dict(color=horizon_color, width=2.2, dash="dashdot"), showlegend=True
            ))
            fig.add_vline(
                x=proj_date, line_dash="dash", line_color=horizon_color, line_width=1.5,
                annotation_text=f"<b>RUL BREACH HORIZON ({limiting})</b><br>{status['rul_cycles']} Cyc ({status['proj_date']})",
                annotation_font=dict(size=10, color=horizon_color), annotation_position="top left"
            )

    fig.add_hline(y=T5_WASH_C, line_dash="dash", line_color="#B54708", line_width=1.2, annotation_text="ITT +10°C (Wash Limit)", annotation_font=dict(size=10, color="#B54708"))
    fig.add_hline(y=T5_BORESCOPE_C, line_dash="dash", line_color="#991B1B", line_width=1.2, annotation_text="ITT +15°C (Borescope Limit)", annotation_font=dict(size=10, color="#991B1B"))

    # [KUNCI STATIS] dragmode=False & fixedrange=True mencegah ketidaksengajaan zoom/pan
    fig.update_layout(
        title=dict(text=f"<b>Condition-Corrected Parameter Shift | Powerplant {engine_name}</b> ({len(df_engine)} Cycles Recorded)", font=dict(color=NAVY, size=14)),
        xaxis_title="Flight Date / Cycle", yaxis_title="Residual Delta from Baseline", hovermode="x unified", template="plotly_white", height=480,
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5, font=dict(size=11)), 
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(248,250,252,1)", margin=dict(l=40, r=20, t=70, b=80),
        dragmode=False,
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=11, color="#475569"), fixedrange=True), 
        yaxis=dict(showgrid=True, gridcolor="#F1F5F9", zeroline=True, zerolinecolor="#94A3B8", zerolinewidth=1, tickfont=dict(size=11, color="#475569"), fixedrange=True)
    )
    return fig

def make_raw_vs_predicted(df_engine: pd.DataFrame, param: str, unit: str, color: str) -> go.Figure:
    # [PATCH #16] Membedakan warna Predicted Baseline untuk tiap parameter agar tidak abu-abu semua
    pred_color_map = {"T5": "#881337", "Ng": "#0891B2", "Wf": "#78350F"}
    pred_color = pred_color_map.get(param, "#64748B")
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_engine["Date"], y=df_engine[param], mode="lines+markers", name=f"Actual {param}", line=dict(color=color, width=1.8), marker=dict(size=4)))
    fig.add_trace(go.Scatter(x=df_engine["Date"], y=df_engine[f"{param}_pred"], mode="lines", name="Predicted Baseline", line=dict(color=pred_color, width=1.8, dash="dash")))
    
    # [KUNCI STATIS] dragmode=False & fixedrange=True
    fig.update_layout(
        title=dict(text=f"<b>{param} | Actual vs. Condition Baseline ({unit})</b>", font=dict(color=NAVY, size=12)), 
        template="plotly_white", height=320, hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="center", x=0.5, font=dict(size=10)), 
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(248,250,252,1)", margin=dict(l=40, r=20, t=60, b=80),
        dragmode=False,
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=10), fixedrange=True), 
        yaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=10), fixedrange=True)
    )
    return fig

# ======================================================================================
# 11. AUTOMATED EMAIL TRANSMITTAL PROTOCOL & NATIVE PDF EWO GENERATOR
# ======================================================================================
def send_engineering_notice(engine_id: str, status_dict: dict, report_body: str, recipients: list, is_automated: bool = False):
    try:
        sender_email = st.secrets["email"]["sender_address"]
        sender_password = st.secrets["email"]["app_password"]
        smtp_server = st.secrets["email"].get("smtp_server", "smtp.gmail.com")
        smtp_port = int(st.secrets["email"].get("smtp_port", 465))
        live_mode = True
    except Exception:
        live_mode = False

    health = status_dict["health_level"]
    status_label = status_dict["status_label"]
    trigger_type = "[AUTOMATED WATCHDOG]" if is_automated else "[MANUAL TRANSMITTAL]"

    if not live_mode:
        if is_automated:
            st.toast(f"AUTOMATED ALERT FIRED: Powerplant {engine_id} breached CRITICAL limit. Notice simulated to {', '.join(recipients)}.")
            st.sidebar.error(f"AUTOMATED NOTICE TRANSMITTED\nTarget: {recipients[0]}\nEngine: {engine_id} ({status_label})")
        else:
            st.info(f"[SYSTEM SIMULATION MODE - {trigger_type}] SMTP secrets not configured. In production, notice for {engine_id} ({status_label}) is transmitted to: {', '.join(recipients)}.")
        return True

    if health == EngineHealth.CRITICAL:
        intro_text = (f"URGENT AIRWORTHINESS ADVISORY: An abnormal thermodynamic parameter shift (CRITICAL BREACH) has been confirmed on Powerplant {engine_id}.\n"
                      f"Trigger Source: {trigger_type}\n"
                      "Please immediately review the powerplant condition and execute the OEM FIM directives below:")
        subject_prefix = "[URGENT - CRITICAL BREACH]"
    elif health == EngineHealth.ADVISORY:
        intro_text = (f"ADVISORY WATCH NOTICE: A statistical baseline deviation has been detected on Powerplant {engine_id}.\n"
                      f"Trigger Source: {trigger_type}\n"
                      "Please review the computed residuals and increase telemetry logging frequency:")
        subject_prefix = "[ADVISORY - WATCH]"
    else:
        intro_text = (f"ROUTINE EVALUATION: Powerplant {engine_id} is operating within normal OEM thermodynamic tolerances.\n"
                      f"Trigger Source: {trigger_type}\n"
                      "Please find the routine condition logging evaluation below:")
        subject_prefix = "[ROUTINE - NORMAL]"

    msg = MIMEMultipart()
    msg['From'] = f"AIRFAST ECTM Automated System <{sender_email}>"
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = f"{subject_prefix} ECTM Alert: Powerplant {engine_id} Status Report"
    
    email_content = (
        f"EXECUTIVE ENGINEERING NOTICE | PT. AIRFAST INDONESIA\n"
        f"====================================================================\n"
        f"Powerplant Serial / Position : {engine_id}\n"
        f"System Status Classification : {status_label}\n"
        f"Transmittal Trigger Type     : {trigger_type}\n"
        f"Timestamp Evaluated          : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"====================================================================\n\n"
        f"{intro_text}\n\n"
        f"{report_body}\n\n"
        f"--------------------------------------------------------------------\n"
        f"Automated transmission from AIRFAST ECTM Technical Services System.\n"
        f"Do not reply directly to this automated service address."
    )
    msg.attach(MIMEText(email_content, 'plain'))
    
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        if is_automated:
            st.toast(f"AUTOMATED NOTICE TRANSMITTED: Critical alert for {engine_id} delivered to {recipients[0]}.")
        return True
    except Exception as ssl_err:
        try:
            with smtplib.SMTP(smtp_server, 587, timeout=10) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            if is_automated:
                st.toast(f"AUTOMATED NOTICE TRANSMITTED: Critical alert for {engine_id} delivered to {recipients[0]}.")
            return True
        except Exception as tls_err:
            st.error(f"SMTP Transmission Failure (SSL Error: {ssl_err} | TLS Error: {tls_err})")
            return False
        
def generate_ewo_html(engine_id, status_label, status, recommendations):
    html = f"<html><head><title>EWO {engine_id}</title></head><body style='font-family:sans-serif; padding:20px;'>"
    html += f"<h2>ENGINEERING WORK ORDER | PT. AIRFAST INDONESIA</h2><hr>"
    html += f"<p><b>Powerplant:</b> {engine_id} | <b>Status:</b> {status_label}</p>"
    html += f"<p><b>Residuals:</b> ΔT5: {status['d_t5']:+.1f}°C | ΔNg: {status['d_ng']:+.2f}% | ΔWf: {status['d_wf']:+.1f} PPH</p><hr>"
    html += "<h3>MAINTENANCE DIRECTIVES:</h3><ul>"
    for r in recommendations: html += f"<li><b>[{r['fim_ref']}] {r['title']}</b><br>{r['body']}</li><br>"
    html += "</ul><hr><p>Authorized Signature: ______________________</p></body></html>"
    return html

def generate_ewo_pdf(engine_id, status_label, status, recommendations):
    if not HAS_FPDF: return b""
    
    # [UNIVERSAL UNICODE SANITIZER] Pengaman mutlak karakter non-ASCII
    def clean_text(txt):
        if not isinstance(txt, str): return str(txt)
        txt = txt.replace("Δ", "Delta ").replace("°C", "deg C").replace("°", "deg ").replace("**", "").replace("▪", "- ")
        return txt.encode("latin-1", errors="replace").decode("latin-1")

    pdf = FPDF()
    pdf.add_page()
    
    # Lebar cetak efektif (Effective Printable Width) universal untuk semua versi FPDF/FPDF2
    epw = pdf.w - pdf.l_margin - pdf.r_margin
    
    # Helper function agar posisi X selalu di-reset ke margin kiri dan lebar konsisten
    def write_line(h, text, style="", size=10, align="L"):
        pdf.set_font("Arial", style, size)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(epw, h, clean_text(str(text)), align=align)

    write_line(10, "ENGINEERING WORK ORDER | PT. AIRFAST INDONESIA", style="B", size=14, align="C")
    write_line(7, f"Powerplant: {engine_id} | Status: {status_label}", size=10)
    write_line(7, f"Residuals: Delta T5: {status['d_t5']:+.1f} C | Delta Ng: {status['d_ng']:+.2f} %", size=10)
    pdf.ln(4)
    
    write_line(8, "MAINTENANCE DIRECTIVES:", style="B", size=11)
    
    for r in recommendations:
        pdf.ln(2)
        write_line(6, f"[{r['fim_ref']}] {r['title']}", style="B", size=10)
        
        meta_text = (
            f"Priority: {r.get('priority', 'ROUTINE')} | Downtime: {r.get('downtime', 'N/A')}\n"
            f"Signature: {r.get('signature', 'N/A')}"
        )
        write_line(5, meta_text, style="I", size=9)
        
        body_text = f"{r.get('body', '')}\n"
        write_line(5, body_text, style="", size=9)
    
    try:
        out = pdf.output(dest="S")
    except TypeError:
        out = pdf.output()
        
    if isinstance(out, str):
        return out.encode("latin-1", errors="ignore")
    elif isinstance(out, (bytes, bytearray)):
        return bytes(out)
    return b""

# ======================================================================================
# 12. CLEAN EXECUTIVE SIDEBAR (AUTHORIZED USER & RBAC NAVIGATION)
# ======================================================================================
logo_path = "images.png"  
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, use_container_width=True)
else:
    st.sidebar.markdown("<h2 style='font-size:1.5rem; font-weight:800; margin-bottom:0px; color:#FFFFFF; letter-spacing:0.05em;'>AIRFAST</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("<p style='font-weight:700; font-size:0.75rem; letter-spacing:0.15em; margin-top:0px; color:#f0b73d;'>INDONESIA</p>", unsafe_allow_html=True)

st.sidebar.markdown("---")

st.sidebar.markdown(f"""
<div style="background-color: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); padding: 14px 16px; border-radius: 6px; margin-bottom: 12px;">
    <span style="color: #f0b73d !important; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; display: block; letter-spacing: 0.05em;">LOGGED IN AS</span>
    <span style="color: #FFFFFF !important; font-size: 1.05rem; font-weight: 700; display: block; margin-top: 4px;">{st.session_state['user_name']}</span>
    <span style="color: #94A3B8 !important; font-size: 0.78rem; display: block;">{st.session_state['user_email']}</span>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
    [data-testid="stSidebar"] [data-testid="stButton"] > button,
    [data-testid="stSidebar"] [data-testid="stButton"] > button[kind="secondary"],
    [data-testid="stSidebar"] [data-testid="stButton"] > button[kind="primary"] {
        background-color: #DC2626 !important;
        border: 1px solid #B91C1C !important;
        border-radius: 6px !important;
        padding: 10px 15px !important;
        width: 100% !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
    }
    [data-testid="stSidebar"] [data-testid="stButton"] > button *,
    [data-testid="stSidebar"] [data-testid="stButton"] > button p,
    [data-testid="stSidebar"] [data-testid="stButton"] > button span {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        letter-spacing: 0.03em !important;
    }
    [data-testid="stSidebar"] [data-testid="stButton"] > button:hover,
    [data-testid="stSidebar"] [data-testid="stButton"] > button[kind="secondary"]:hover {
        background-color: #991B1B !important;
        border-color: #7F1D1D !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.3) !important;
    }
</style>
""", unsafe_allow_html=True)

if st.sidebar.button("Logout", key="btn_logout_sidebar", use_container_width=True):
    st.session_state["logged_in"] = False
    st.session_state["user_email"] = ""
    st.session_state["user_name"] = "Guest Viewer"
    st.session_state["user_role"] = "Guest / Viewer"
    st.session_state["active_menu"] = "Home (Fleet Matrix)"
    st.rerun()

st.sidebar.markdown("---")

all_menus = [
    "Home (Fleet Matrix)", 
    "Data Collection & Setup", 
    "Trend Analysis & RUL", 
    "Logbook & Defect Correlator", 
    "Recommendations & Notice Transmittal"
]

allowed_menus = all_menus 

if st.session_state["active_menu"] not in allowed_menus:
    st.session_state["active_menu"] = allowed_menus[0]

menu_selection = st.sidebar.radio(
    "Navigation Menu",
    allowed_menus,
    key="active_menu",
    label_visibility="collapsed",
)

st.sidebar.markdown("<br>" * 2, unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.markdown("<p style='font-weight:700; color:#f0b73d; font-size:0.85rem; margin-bottom:2px;'>FLEET WATCHDOG</p>", unsafe_allow_html=True)
st.sidebar.caption(
    "Manual trigger only - runs a one-time scan across the fleet and dispatches "
    "alerts for engines currently at CRITICAL. Deduplication only lasts for this "
    "browser session (not persisted), so re-running after a page refresh may "
    "re-send an alert for the same finding."
)
watchdog_recipient_input = st.sidebar.text_input(
    "Alert recipient email(s)", value=st.session_state.get("watchdog_recipient", ""),
    placeholder="engineering@airfastindonesia.com", key="watchdog_recipient",
    help="Comma-separate multiple addresses. Nothing is sent until you click the button below.",
)
run_watchdog_now = st.sidebar.button("Run Fleet Health Scan Now", key="btn_run_watchdog", use_container_width=True)

st.sidebar.markdown("<br>" * 2, unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.markdown("<div style='font-size:0.75rem; line-height:1.5; color:#94A3B8; font-weight:400;'><b style='color:#FFFFFF; font-weight:600;'>PT. AIRFAST Indonesia</b><br>Jl. Marsekal Suryadarma No.8<br>Neglasari, Tangerang, Banten 15129<br><span style='font-size:0.7rem; color:#64748B;'>Technical Service Division</span></div>", unsafe_allow_html=True)

# ======================================================================================
# 13. GLOBAL DATA PROCESSING & PERSISTENT STATE SYNC
# ======================================================================================
df_raw = st.session_state["df_data"].copy()
df_util_current = st.session_state["df_util"].copy()
df_rep_current = st.session_state["df_rep"].copy()

missing_required, available_correction = validate_columns(df_raw)
if missing_required:
    st.error(f"Ingestion Error: Mandatory schema columns missing: {', '.join(missing_required)}. Rectify within Data Collection.")
    st.stop()

for col in REQUIRED_COLUMNS[2:] + [c for c in OPTIONAL_COLUMNS if c in df_raw.columns and c != "AML No"]:
    if df_raw[col].dtype == object:
        df_raw[col] = df_raw[col].astype(str).str.replace(",", ".", regex=False)
    df_raw[col] = pd.to_numeric(df_raw[col], errors="coerce")

df_raw["Date"] = safe_parse_dates(df_raw["Date"])

# [PATCH #7] Pengaman otomatis jika file CSV lama tidak memiliki kolom 'AML No'
if "AML No" not in df_raw.columns:
    df_raw["AML No"] = df_raw["Date"].dt.strftime("%Y%m%d").apply(lambda x: f"AML-{x}" if pd.notnull(x) else "AML-UNKN")
if "AML No" not in df_util_current.columns and not df_util_current.empty:
    df_util_current["AML No"] = df_util_current["Work (Date)"].dt.strftime("%Y%m%d").apply(lambda x: f"AML-{x}" if pd.notnull(x) else "AML-UNKN")

_rows_before_clean = len(df_raw)
df_raw = df_raw.dropna(subset=REQUIRED_COLUMNS).sort_values("Date")
_rows_dropped = _rows_before_clean - len(df_raw)
if _rows_dropped > 0:
    st.sidebar.warning(
        f"{_rows_dropped} logbook row(s) ignored - invalid or missing "
        f"Date/{'/'.join(REQUIRED_COLUMNS[2:])} values. Check Data Collection & Setup."
    )

engines_available = sorted(df_raw["Engine"].dropna().unique().tolist())
if not engines_available:
    st.error("Data Processing Error: No valid powerplant identifiers ('Engine') located within dataset.")
    st.stop()

if st.session_state["target_engine"] not in engines_available:
    st.session_state["target_engine"] = engines_available[0]

selected_engine = st.session_state["target_engine"]
use_correction = st.session_state["target_use_correction"]
baseline_n_input = st.session_state["target_baseline_n"]

df_engine = df_raw[df_raw["Engine"] == selected_engine].copy()
if len(df_engine) < 2:
    st.warning(f"Powerplant {selected_engine} contains only {len(df_engine)} logged flight cycle(s). Minimum of 2 cycles required for trend regression.")
    st.stop()

df_engine = compute_engine_trend(df_engine, int(baseline_n_input), use_correction)
status = build_status(df_engine, df_util_current)
recommendations = generate_recommendations(df_engine, status)

# ======================================================================================
# FLEET WATCHDOG - MANUAL SCAN (runs only on explicit button click, see sidebar)
# ======================================================================================
if "auto_alert_sent" not in st.session_state:
    st.session_state["auto_alert_sent"] = set()

if run_watchdog_now:
    watchdog_recipients = [r.strip() for r in watchdog_recipient_input.split(",") if r.strip()]
    if not watchdog_recipients:
        st.sidebar.error("Enter at least one recipient email before running the scan.")
    else:
        n_critical_found = 0
        for eng_check_id in engines_available:
            df_check = df_raw[df_raw["Engine"] == eng_check_id].copy()
            if len(df_check) >= 2:
                df_check_proc = compute_engine_trend(df_check, int(baseline_n_input), use_correction)
                st_check = build_status(df_check_proc, df_util_current)

                if st_check["health_level"] == EngineHealth.CRITICAL:
                    n_critical_found += 1
                    alert_key = f"{eng_check_id}_{st_check['latest']['Date'].strftime('%Y%m%d')}"

                    if alert_key not in st.session_state["auto_alert_sent"]:
                        recs_check = generate_recommendations(df_check_proc, st_check)

                        auto_report_lines = [
                            "CRITICAL THERMODYNAMIC DEGRADATION DETECTED BY FLEET WATCHDOG SCAN",
                            f"Latest Logbook Timestamp : {st_check['latest']['Date'].strftime('%Y-%m-%d')}",
                            f"Computed Residual Vector  : \u0394T5 = {st_check['d_t5']:+.1f} \u00b0C | \u0394Ng = {st_check['d_ng']:+.2f} % | \u0394Wf = {st_check['d_wf']:+.1f} PPH",
                            f"Predictive RUL Remaining  : {st_check['rul_cycles']} Flight Cycles ({st_check['proj_date']})",
                            f"RUL Linear Confidence     : {st_check['rul_confidence']}",
                            "-------------------------------------------------------------------------",
                            "IMMEDIATE MAINTENANCE DIRECTIVES REQUIRED:",
                        ]
                        for rc in recs_check:
                            auto_report_lines.extend([
                                f"[{rc['fim_ref']}] {rc['title']}",
                                f">> Priority: {rc.get('priority', 'ROUTINE')} | Est. Downtime: {rc.get('downtime', 'N/A')}",
                                f">> Thermodynamic Signature: {rc.get('signature', 'N/A')}",
                                rc['body'], 
                                ""
                            ])

                        is_delivered = send_engineering_notice(
                            engine_id=eng_check_id,
                            status_dict=st_check,
                            report_body="\n".join(auto_report_lines),
                            recipients=watchdog_recipients,
                            is_automated=True,
                        )
                        if is_delivered:
                            st.session_state["auto_alert_sent"].add(alert_key)
        if n_critical_found == 0:
            st.sidebar.success("Fleet scan complete - no engines currently at CRITICAL.")
        else:
            st.sidebar.info(f"Fleet scan complete - {n_critical_found} CRITICAL engine(s) processed.")

# ======================================================================================
# 14. PAGE 1: HOME (FLEET MATRIX & OCC HEATMAP INTEGRATION)
# ======================================================================================
if menu_selection == "Home (Fleet Matrix)":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Fleet Matrix</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='color:#475569; font-size:1.0rem; font-weight:500; margin-top:0px;'>Technical Services & Fleet Maintenance | DHC-6 Twin Otter / PT6A-34</h3>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    if not st.session_state.get("util_is_real", False):
        st.info("RUL calendar dates below use a **simulated** flight-utilization dataset (no real "
                "'Flight Utilization DHC6-400.xlsx' found). Upload the real file in Data Collection & Setup "
                "for accurate projections.")

    fleet_summary_data = []
    aircraft_map = {}
    
    for eng in engines_available:
        df_sub = df_raw[df_raw["Engine"] == eng].copy()
        if len(df_sub) >= 2:
            df_sub_proc = compute_engine_trend(df_sub, int(baseline_n_input), use_correction)
            st_sub = build_status(df_sub_proc, df_util_current)
            stat_lbl = "CRITICAL" if st_sub["health_level"] == EngineHealth.CRITICAL else ("ADVISORY" if st_sub["health_level"] == EngineHealth.ADVISORY else "NORMAL")
            rul_val = st_sub["rul_cycles"]
            accel_marker = " [ACCELERATING]" if st_sub["rul_is_linear_caution"] else ""
            rul_str = "Stable (>100 Cycles)" if rul_val >= 999 else f"{rul_val} Cycles ({st_sub['proj_date']}){accel_marker}"
            
            fleet_summary_data.append({
                "Powerplant Serial / Position": eng,
                "Status": stat_lbl,
                "Latest Δ T5": f"{st_sub['d_t5']:+.1f} °C",
                "T5 Slope": f"{st_sub['slope_t5']:+.2f} °C/cyc",
                "Latest Δ Ng": f"{st_sub['d_ng']:+.2f} %",
                "Predictive RUL (Borescope)": rul_str
            })
            
            reg_id = st_sub["reg_prefix"]
            pos = "LH Engine" if "LH" in eng else "RH Engine"
            if reg_id not in aircraft_map: aircraft_map[reg_id] = {}
            aircraft_map[reg_id][pos] = stat_lbl

    # [UI/UX UPGRADE] Kartu Metrik dipindahkan ke atas agar eksekutif langsung melihat kesimpulan angka
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Fleet Engines", len(engines_available))
    c2.metric("Logbook Utilization Rows", len(df_util_current) if not df_util_current.empty else "0 (Sim)")
    c3.metric("Defect Reports (PIREP / MAREP)", len(df_rep_current) if not df_rep_current.empty else "0 (Sim)")
    critical_count = sum(1 for item in fleet_summary_data if item["Status"] == "CRITICAL")
    c4.metric("Fleet Alert Status", f"{critical_count} CRITICAL" if critical_count > 0 else "NORMAL")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<h3 style='color:#003B6F; margin-bottom:8px;'>Operation Control Center (OCC) | Fleet Health Map</h3>", unsafe_allow_html=True)
    
    dhc6_svg_blueprint = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 80" width="100%" height="110" style="background: linear-gradient(135deg, #F8FAFC 0%, #EFF4FA 100%); border: 1px solid #CBD5E1; border-radius: 6px; padding: 4px; margin-bottom: 8px;">
<g stroke="#E2E8F0" stroke-width="0.6"><line x1="0" y1="20" x2="320" y2="20"/><line x1="0" y1="40" x2="320" y2="40"/><line x1="0" y1="60" x2="320" y2="60"/><line x1="80" y1="0" x2="80" y2="80"/><line x1="160" y1="0" x2="160" y2="80"/><line x1="240" y1="0" x2="240" y2="80"/></g>
<g fill="#003B6F"><path d="M 40 45 L 60 42 C 80 40, 120 40, 180 40 L 250 38 L 285 22 L 295 22 L 285 42 C 295 44, 298 47, 290 51 L 250 51 L 180 50 L 80 50 C 60 50, 45 49, 40 45 Z"/><path d="M 110 37 L 140 37 L 155 48 L 105 48 Z" fill="#00284D"/><ellipse cx="98" cy="43" rx="3" ry="12" fill="#f0b73d" opacity="0.9"/><line x1="98" y1="28" x2="98" y2="58" stroke="#f0b73d" stroke-width="1.5" stroke-dasharray="2,2"/><path d="M 255 38 L 280 12 L 292 12 L 285 38 Z" fill="#00284D"/></g>
<text x="12" y="18" font-family="'Plus Jakarta Sans', sans-serif" font-size="9" font-weight="800" fill="#003B6F" letter-spacing="1.5">DHC-6 TWIN OTTER</text>
<text x="12" y="30" font-family="'Plus Jakarta Sans', sans-serif" font-size="7.5" font-weight="600" fill="#64748B">TWIN TURBOPROP | P&amp;WC PT6A-34</text>
<circle cx="300" cy="15" r="4" fill="#16A34A"/></svg>"""

    import base64
    hm_cols = st.columns(3)
    col_idx = 0
    for reg, engs in sorted(aircraft_map.items()):
        with hm_cols[col_idx % 3]:
            lh_stat = engs.get("LH Engine", "UNKNOWN")
            rh_stat = engs.get("RH Engine", "UNKNOWN")
            
            def get_hm_class(st_val):
                if st_val == "CRITICAL": return "hm-red"
                if st_val == "ADVISORY": return "hm-amber"
                return "hm-green"

            img_candidates = [
                f"{reg}.jpg", f"{reg.lower()}.jpg",
                f"{reg}.jpeg", f"{reg.lower()}.jpeg",
                f"{reg}.png", f"{reg.lower()}.png",
                "dhc6.jpg", "dhc6.jpeg", "dhc6.png", "twin_otter.jpg"
            ]
            
            found_img_path = None
            for cand in img_candidates:
                if os.path.exists(cand):
                    found_img_path = cand
                    break

            if found_img_path:
                with open(found_img_path, "rb") as f_img:
                    b64_str = base64.b64encode(f_img.read()).decode()
                ext = found_img_path.split(".")[-1].lower()
                mime_type = "image/jpeg" if ext in ["jpg", "jpeg"] else "image/png"
                visual_html = f'<div style="margin-bottom:8px; border:1px solid #CBD5E1; border-radius:6px; overflow:hidden; width:100%; height:105px; background:#F8FAFC;"><img src="data:{mime_type};base64,{b64_str}" style="width:100%; height:100%; object-fit:cover; object-position:center; display:block;"></div>'
            else:
                visual_html = dhc6_svg_blueprint
                
            card_html = f"""<div class="heatmap-card">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
<span class="heatmap-reg" style="margin-bottom:0px; font-size:1.1rem;">{reg}</span>
<span style="background:#EFF4FA; color:#003B6F; font-size:0.7rem; font-weight:700; padding:2px 6px; border-radius:4px; border:1px solid #CBD5E1;">PT6A-34</span>
</div>
{visual_html}
<div class="heatmap-row {get_hm_class(lh_stat)}">
<span>#1 LH Powerplant</span><b>{lh_stat}</b>
</div>
<div class="heatmap-row {get_hm_class(rh_stat)}">
<span>#2 RH Powerplant</span><b>{rh_stat}</b>
</div>
</div>"""
            st.markdown(card_html, unsafe_allow_html=True)
        col_idx += 1

    df_fleet_matrix = pd.DataFrame(fleet_summary_data)
    st.dataframe(df_fleet_matrix, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    if not df_util_current.empty:
        st.markdown("<h3 style='color:#003B6F; margin-bottom:2px;'>Airframe Utilization Summary (Total FH / FC)</h3>", unsafe_allow_html=True)
        min_u_date = df_util_current['Work (Date)'].min().strftime('%d %b %Y')
        max_u_date = df_util_current['Work (Date)'].max().strftime('%d %b %Y')
        days_span = max(1, (df_util_current['Work (Date)'].max() - df_util_current['Work (Date)'].min()).days + 1)

        st.caption(f"Real-world accumulation rate from Flight Utilization dataset used to project calendar maintenance dates.<br>"
                   f"<span style='color:#003B6F; font-weight:600;'>Data Sampling Period:</span> {min_u_date} — {max_u_date} ({days_span} Days Recorded)", unsafe_allow_html=True)

        df_u_summary = df_util_current.groupby("Registration")[["FH", "FC"]].sum().reset_index()
        df_u_summary["Avg FC / Day"] = df_u_summary["Registration"].apply(lambda r: round(get_aircraft_utilization_rate(r, df_util_current), 1))
        
        # [UI/UX UPGRADE] Gabungkan tabel dan grafik bar berdampingan (col 1 vs col 2) agar hemat ruang vertikal!
        col_u_tbl, col_u_chart = st.columns([1, 1.8])
        with col_u_tbl:
            st.dataframe(df_u_summary, use_container_width=True, hide_index=True, height=300)
        with col_u_chart:
            fig_util = px.bar(
                df_u_summary, x='Registration', y=['FH', 'FC'], barmode='group',
                labels={'value': 'Total Value', 'Registration': 'Aircraft Registration', 'variable': 'Metric Type'},
                color_discrete_map={'FH': '#003B6F', 'FC': '#f0b73d'}, height=310
            )
            fig_util.update_layout(
                title=dict(text="<b>Fleet Utilization Balancing (Flight Hours vs. Cycles)</b>", font=dict(color="#003B6F", size=12)),
                legend=dict(title='Metric', orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
                hovermode="x unified", margin=dict(l=20, r=20, t=40, b=20), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', dragmode=False
            )
            fig_util.update_xaxes(fixedrange=True)
            fig_util.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.15)', fixedrange=True)
            st.plotly_chart(fig_util, use_container_width=True)

# ======================================================================================
# 15. PAGE 2: DATA COLLECTION & CONFIGURATION
# ======================================================================================
elif menu_selection == "Data Collection & Setup":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Data Ingestion & System Setup</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>Manage engine performance logbooks, airframe utilization files, and PIREP / MAREP defect reports.</p>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    tab_ectm, tab_util, tab_rep = st.tabs(["1. Engine Performance Logbook (.csv)", "2. Flight Utilization (.xlsx)", "3. PIREP / MAREP (.xlsx)"])
    
    with tab_ectm:
        with st.expander("Add Daily Engine Performance Record (Manual Entry)", expanded=False):
            st.caption("Log daily engine telemetry directly from pilot flight logbook without uploading a CSV.")
            with st.form("form_manual_ectm", clear_on_submit=True):
                col_f1, col_f2, col_f3, col_f4 = st.columns(4)
                with col_f1:
                    m_aml = st.text_input("AML No (Relational Key)", placeholder="e.g., OAM-2026-015").upper()
                    m_date = st.date_input("Flight Date", value=datetime.now())
                    m_eng = st.selectbox("Powerplant ID", engines_available)
                    m_alt = st.number_input("Press Alt (Ft)", min_value=0, max_value=25000, value=10000, step=500)
                with col_f2:
                    m_ioat = st.number_input("IOAT (°C)", min_value=-40.0, max_value=55.0, value=15.0, step=0.5)
                    m_ias = st.number_input("IAS (Knots)", min_value=0.0, max_value=200.0, value=135.0, step=1.0)
                    m_tq = st.number_input("Torque (TQ %)", min_value=0.0, max_value=100.0, value=42.0, step=0.5)
                with col_f3:
                    m_np = st.number_input("Prop Speed (Np %)", min_value=0, max_value=100, value=75, step=1)
                    m_t5 = st.number_input("T5 / ITT (°C)", min_value=300.0, max_value=850.0, value=624.0, step=0.5)
                    m_ng = st.number_input("Gas Gen (Ng %)", min_value=50.0, max_value=105.0, value=91.50, step=0.1)
                with col_f4:
                    m_wf = st.number_input("Fuel Flow (Wf PPH)", min_value=100.0, max_value=500.0, value=288.0, step=1.0)
                    m_otemp = st.number_input("Oil Temp (°C)", min_value=10.0, max_value=110.0, value=72.0, step=0.5)
                    m_opress = st.number_input("Oil Press (PSI)", min_value=40.0, max_value=120.0, value=91.0, step=0.5)
                
                submitted_ectm = st.form_submit_button("Save Daily Performance Record", type="primary", use_container_width=True)
                if submitted_ectm:
                    new_row = pd.DataFrame([{
                        "AML No": m_aml if m_aml else f"AML-{pd.to_datetime(m_date).strftime('%Y%m%d')}",
                        "Date": pd.to_datetime(m_date), "Engine": m_eng, "Press_Alt": float(m_alt),
                        "IOAT": float(m_ioat), "IAS": float(m_ias), "TQ": float(m_tq), "Np": int(m_np),
                        "T5": float(m_t5), "Ng": float(m_ng), "Wf": float(m_wf),
                        "Oil_Temp": float(m_otemp), "Oil_Press": float(m_opress)
                    }])
                    st.session_state["df_data"] = pd.concat([st.session_state["df_data"], new_row], ignore_index=True)
                    st.success(f"Successfully logged daily performance telemetry for {m_eng}!")
                    st.rerun()

        col_up, col_dl = st.columns([3, 1])
        with col_up:
            up_ectm = st.file_uploader("Upload Engine Performance Logbook (.csv)", type=["csv"], key="up_ectm_file")
            if up_ectm is not None:
                new_df = pd.read_csv(up_ectm)
                missing, _ = validate_columns(new_df)
                if not missing:
                    st.session_state["df_data"] = new_df
                    st.success("Engine Performance Logbook ingested successfully.")
                    st.rerun()
        with col_dl:
            st.write("")
            st.write("")
            st.download_button("Download CSV Template", data=csv_template(), file_name="AIRFAST_ECTM_Template.csv", mime="text/csv", use_container_width=True)
        
        audit_alerts = run_data_quality_audit(st.session_state["df_data"])
        if audit_alerts:
            with st.expander("Data Quality Audit Alerts Detected (Click to expand)", expanded=True):
                for alert in audit_alerts:
                    st.warning(alert)

        st.session_state["df_data"] = st.data_editor(st.session_state["df_data"], num_rows="dynamic", use_container_width=True, key="ed_ectm_ui")

    with tab_util:
        with st.expander("Add Daily Flight Utilization Record (Manual Entry)", expanded=False):
            st.caption("Log daily airframe flight hours (FH) and flight cycles (FC) to update RUL calendar projections.")
            with st.form("form_manual_util", clear_on_submit=True):
                col_u1, col_u2, col_u3 = st.columns(3)
                with col_u1:
                    u_aml = st.text_input("AML No (Relational Key)", placeholder="e.g., OAM-2026-015").upper()
                    u_reg = st.selectbox("Aircraft Registration", FLEET_REGISTRATIONS)
                    u_date = st.date_input("Work Date", value=datetime.now())
                with col_u2:
                    u_fh = st.number_input("Flight Hours (FH)", min_value=0.0, max_value=24.0, value=2.5, step=0.1)
                    u_fc = st.number_input("Flight Cycles (FC)", min_value=1, max_value=30, value=4, step=1)
                with col_u3:
                    u_bh = st.number_input("Block Hours (BH)", min_value=0.0, max_value=24.0, value=2.8, step=0.1)
                    u_from = st.text_input("From Sector", value="WAY").upper()
                    u_to = st.text_input("To Sector", value="TIM").upper()
                
                submitted_util = st.form_submit_button("Save Utilization Record", type="primary", use_container_width=True)
                if submitted_util:
                    new_u_row = pd.DataFrame([{
                        "AML No": u_aml if u_aml else f"AML-{pd.to_datetime(u_date).strftime('%Y%m%d')}",
                        "Registration": u_reg, "Work (Date)": pd.to_datetime(u_date),
                        "FH": float(u_fh), "FC": int(u_fc), "Block Hours": float(u_bh),
                        "From": u_from, "To": u_to
                    }])
                    st.session_state["df_util"] = pd.concat([st.session_state["df_util"], new_u_row], ignore_index=True)
                    st.session_state["util_is_real"] = True
                    st.success(f"Successfully logged utilization for {u_reg} ({u_fh} FH / {u_fc} FC)!")
                    st.rerun()

        st.caption("Upload Flight Utilization Excel file (e.g., `Flight Utilization DHC6-400.xlsx`) to synchronize RUL calendar projections.")
        up_util = st.file_uploader("Upload Utilization File (.xlsx)", type=["xlsx"], key="up_util_file")
        if up_util is not None:
            df_u_new = pd.read_excel(up_util)
            df_u_new['Work (Date)'] = safe_parse_dates(df_u_new['Work (Date)'])
            st.session_state["df_util"] = df_u_new.dropna(subset=['Registration', 'Work (Date)'])
            st.session_state["util_is_real"] = not st.session_state["df_util"].empty
            st.success("Flight Utilization dataset synchronized!")
            st.rerun()
        if not st.session_state.get("util_is_real", False):
            st.warning("No real utilization file found on disk. RUL calendar projections are currently using a "
                       "simulated utilization dataset - upload the real file above for accurate dates.")
        st.dataframe(st.session_state["df_util"].head(100), use_container_width=True)

    with tab_rep:
        with st.expander("Add PIREP / MAREP Defect Report (Manual Entry)", expanded=False):
            st.caption("Log pilot defect reports (PIREP) or maintenance actions (MAREP) to feed the Defect Correlator.")
            with st.form("form_manual_rep", clear_on_submit=True):
                col_r1, col_r2, col_r3 = st.columns([1, 1, 1])
                with col_r1:
                    r_aml = st.text_input("AML / Logbook No", placeholder="e.g., OAM-2026-015").upper()
                    r_date = st.date_input("Report Date", value=datetime.now())
                with col_r2:
                    r_reg = st.selectbox("Registration", FLEET_REGISTRATIONS, key="rep_reg")
                    r_pos = st.selectbox("Engine Position", ["LH", "RH", "General"])
                with col_r3:
                    r_ata = st.number_input("ATA Chapter", min_value=0, max_value=99, value=71, step=1)
                    r_pn_off = st.text_input("P/N Off (Optional)", placeholder="Part Number Removed")
                
                r_note = st.text_area("Note / Report (PIREP / MAREP Description)", placeholder="Describe pilot observation or defect symptom...")
                r_action = st.text_area("Corrective Action Taken", placeholder="Describe rectification, borescope findings, or wash results...")
                
                col_sn1, col_sn2, col_sn3 = st.columns(3)
                with col_sn1: r_sn_off = st.text_input("S/N Off", placeholder="Serial No Removed")
                with col_sn2: r_pn_on = st.text_input("P/N On", placeholder="Part Number Installed")
                with col_sn3: r_sn_on = st.text_input("S/N On", placeholder="Serial No Installed")

                submitted_rep = st.form_submit_button("Save PIREP / MAREP Report", type="primary", use_container_width=True)
                if submitted_rep:
                    new_r_row = pd.DataFrame([{
                        "AML No": r_aml if r_aml else f"{r_reg}-MANUAL", "Date": pd.to_datetime(r_date),
                        "Registration": r_reg, "ATA": int(r_ata),
                        "Note / Report": r_note if r_note else "No description provided.",
                        "Corrective Action": r_action if r_action else "Pending action.",
                        "Position": r_pos, "P/N Off": r_pn_off, "S/N Off": r_sn_off,
                        "P/N On": r_pn_on, "S/N On": r_sn_on
                    }])
                    st.session_state["df_rep"] = pd.concat([st.session_state["df_rep"], new_r_row], ignore_index=True)
                    st.session_state["df_rep"] = process_maintenance_reports(st.session_state["df_rep"])
                    st.session_state["rep_is_real"] = True
                    st.success(f"Successfully logged PIREP / MAREP report [{r_aml}] for {r_reg}!")
                    st.rerun()

        st.caption("Upload PIREP & MAREP Excel file (e.g., `Pilot & Maintenance Report DHC6-400.xlsx`) to power the Defect Correlator.")
        up_rep = st.file_uploader("Upload PIREP / MAREP File (.xlsx)", type=["xlsx"], key="up_rep_file")
        if up_rep is not None:
            df_r_new = pd.read_excel(up_rep)
            st.session_state["df_rep"] = process_maintenance_reports(df_r_new)
            st.session_state["rep_is_real"] = not st.session_state["df_rep"].empty
            st.success("PIREP / MAREP reports synchronized & mapped!")
            st.rerun()
        if not st.session_state.get("rep_is_real", False):
            st.warning("No real PIREP / MAREP file found on disk. The Defect Correlator is currently "
                       "showing simulated PIREP/MAREP entries - upload the real file above.")
        st.dataframe(st.session_state["df_rep"].head(100), use_container_width=True)

    st.markdown("---")
    st.markdown("<h3 style='color:#003B6F; margin-bottom:4px;'>Analysis Configuration & Powerplant Selection</h3>", unsafe_allow_html=True)
    with st.container(border=True):
        col_set1, col_set2, col_set3 = st.columns([1.2, 1, 1.2])
        
        def sync_config():
            if "ui_sel_eng" in st.session_state: st.session_state["target_engine"] = st.session_state["ui_sel_eng"]
            if "ui_sel_base" in st.session_state: st.session_state["target_baseline_n"] = st.session_state["ui_sel_base"]
            if "ui_sel_corr" in st.session_state: st.session_state["target_use_correction"] = st.session_state["ui_sel_corr"]

        with col_set1:
            curr_idx = engines_available.index(st.session_state["target_engine"]) if st.session_state["target_engine"] in engines_available else 0
            st.selectbox("Target Powerplant (Position)", engines_available, index=curr_idx, key="ui_sel_eng", on_change=sync_config)
        with col_set2:
            st.number_input("Reference Baseline Cycles", min_value=2, max_value=20, step=1, value=int(st.session_state["target_baseline_n"]), key="ui_sel_base", on_change=sync_config)
        with col_set3:
            st.write("") 
            st.write("")
            st.toggle("Atmospheric & Torque Normalization", value=bool(st.session_state["target_use_correction"]), key="ui_sel_corr", on_change=sync_config)
            
        sync_config()
            
    st.markdown("<br>", unsafe_allow_html=True)
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        st.button("Execute ECTM Analysis & View Trends", type="primary", use_container_width=True, on_click=navigate_to_menu, args=("Trend Analysis & RUL",))

# ======================================================================================
# 16. PAGE 3: TREND ANALYSIS & PREDICTIVE RUL (WITH DYNAMIC TIME SLICER)
# ======================================================================================
elif menu_selection == "Trend Analysis & RUL":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Thermodynamic Trend Analysis</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>Active Powerplant: <b style='color:#003B6F; background:#EFF4FA; padding:2px 8px; border-radius:4px; border:1px solid #CBD5E1;'>{selected_engine}</b> | Condition-Corrected Residual Shifts</p>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    if df_engine.attrs.get("regression_downgraded", False):
        st.warning("**Mathematical Warning:** Reference Baseline Cycles terpilih tidak cukup untuk menjalankan regresi multivariabel penuh pada parameter atmosfer. Normalisasi sementara diatur ke mode Rata-Rata (Arithmetic Mean). Disarankan menaikkan Baseline Cycles ke minimal **6 siklus** di menu Setup.")

    col_chart, col_status = st.columns([2.8, 1.2])
    with col_chart:
        # [FITUR INTERAKTIF BARU] Time-Horizon Slicer untuk memotong rentang siklus secara dinamis
        ctrl_c1, ctrl_c2 = st.columns([1, 1.5])
        with ctrl_c1:
            st.markdown("<span style='font-size:0.85rem; font-weight:700; color:#475569;'>Visual Display Horizon:</span>", unsafe_allow_html=True)
        with ctrl_c2:
            time_slice = st.radio("Time Horizon", ["All Cycles", "Last 30 Cycles", "Last 15 Cycles"], horizontal=True, label_visibility="collapsed")
        
        df_chart_display = df_engine.copy()
        if time_slice == "Last 30 Cycles" and len(df_chart_display) > 30:
            df_chart_display = df_chart_display.iloc[-30:]
        elif time_slice == "Last 15 Cycles" and len(df_chart_display) > 15:
            df_chart_display = df_chart_display.iloc[-15:]

        st.plotly_chart(make_trend_figure(df_chart_display, selected_engine, status=status), use_container_width=True)

        with st.expander("View Operational Flight Profile (Pressure Altitude Level)", expanded=False):
            fig_alt = go.Figure()
            fig_alt.add_trace(go.Scatter(
                x=df_engine["Date"], y=df_engine["Press_Alt"], mode="lines+markers",
                name="Press Alt [Ft]", line=dict(color="#475569", width=1.8), marker=dict(size=4, color="#003B6F"),
                hovertemplate="<b>%{y:,.0f} Ft</b><extra></extra>"
            ))
            fig_alt.update_layout(
                title=dict(text=f"<b>Flight Pressure Altitude Profile | Powerplant {selected_engine}</b>", font=dict(color=NAVY, size=12)),
                xaxis_title="Flight Date / Cycle", yaxis_title="Altitude [Feet]", hovermode="x unified",
                template="plotly_white", height=240, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(248,250,252,1)",
                margin=dict(l=40, r=20, t=35, b=35), dragmode=False,
                xaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=10), fixedrange=True),
                yaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=10), fixedrange=True)
            )
            st.plotly_chart(fig_alt, use_container_width=True)

        with st.expander("View Raw Observations vs. Predicted Condition Baseline"):
            cc1, cc2, cc3 = st.columns(3)
            with cc1: st.plotly_chart(make_raw_vs_predicted(df_engine, "T5", "\u00b0C", "#B42318"), use_container_width=True)
            with cc2: st.plotly_chart(make_raw_vs_predicted(df_engine, "Ng", "%", "#003B6F"), use_container_width=True)
            with cc3: st.plotly_chart(make_raw_vs_predicted(df_engine, "Wf", "PPH", "#B54708"), use_container_width=True)

    with col_status:
        st.markdown("<h3 style='margin-bottom:6px; color:#003B6F;'>Powerplant Status</h3>", unsafe_allow_html=True)
        if status["health_level"] == EngineHealth.CRITICAL:
            st.markdown("<span class='badge-red'>CRITICAL / ABNORMAL</span>", unsafe_allow_html=True)
        elif status["health_level"] == EngineHealth.ADVISORY:
            st.markdown("<span class='badge-amber'>ADVISORY / WATCH</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='badge-green'>NORMAL TREND</span>", unsafe_allow_html=True)

        st.write("")
        st.metric("Latest \u0394 T5 Residual", f"{status['d_t5']:+.1f} \u00b0C", delta=f"{status['slope_t5']:+.2f} °C/cyc", delta_color="inverse")
        st.metric("Latest \u0394 Ng Residual", f"{status['d_ng']:+.2f} %", delta=f"{status['slope_ng']:+.3f} %/cyc")
        st.metric("Latest \u0394 Wf Residual", f"{status['d_wf']:+.1f} PPH", delta=f"{status['latest']['Delta_Wf_pct']:+.1f}% shift", delta_color="inverse")

        rul_val = status["rul_cycles"]
        rul_display = "Stable (>100 Cycles)" if rul_val >= 999 else f"{rul_val} Flight Cycles"
        date_display = f"Est. Date: {status['proj_date']} ({status['fc_per_day']:.1f} cyc/day)" if rul_val < 999 else "No Intervention Scheduled"
        rul_caution_color = "#B42318" if status["rul_is_linear_caution"] else "#64748B"

        st.markdown(f"""
        <div class="rul-box">
            <div class="rul-title">Remaining Useful Life (RUL) — Sisa Umur Pakai</div>
            <div class="rul-val">{rul_display}</div>
            <div class="rul-sub">{date_display}</div>
            <div class="rul-sub" style="color:{rul_caution_color}; margin-top:4px;">[NOTE] {status['rul_confidence']}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.caption("Diagnostic Event Flags:")
        if status["isolated_t5"] or status["isolated_ng"]: st.write("▪ Isolated single-cycle shift")
        if status["sustained_t5"]: st.write("▪ Sustained upward T5 degradation")
        if status["alarm_wash"]: st.write("▪ ITT +10°C wash limit exceeded")
        if status["alarm_borescope_t5"] or status["alarm_borescope_ng"]: st.write("▪ OEM borescope limit breached")
        if not (status["isolated_t5"] or status["isolated_ng"] or status["sustained_t5"] or status["alarm_wash"] or status["alarm_borescope_t5"] or status["alarm_borescope_ng"]):
            st.write("▪ No active anomalies detected")
            
        st.markdown("---")
        st.button(
            "Cross-Check Logbook Defect Correlator", 
            use_container_width=True,
            on_click=navigate_to_menu,
            args=("Logbook & Defect Correlator", status["reg_prefix"])
        )

    st.markdown("---")
    show_cols = [c for c in ["AML No", "Date", "Engine", "T5", "Delta_T5", "Ng", "Delta_Ng", "Wf", "Delta_Wf_pct"] if c in df_engine.columns]
    st.dataframe(df_engine[show_cols].sort_values("Date", ascending=False), use_container_width=True, height=220)
    
# ======================================================================================
# 17. PAGE 4: LOGBOOK & DEFECT CORRELATOR (WITH 3-WAY RELATIONAL SSOT)
# ======================================================================================
elif menu_selection == "Logbook & Defect Correlator":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Maintenance Logbook & Defect Correlator</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>Cross-reference PIREP / MAREP defect notes and component replacement history against engine performance trends.</p>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    if df_rep_current.empty:
        st.warning("No PIREP / MAREP dataset loaded. Please upload the defect report file in Data Collection & Setup.")
        st.stop()

    if 'ATA_Desc' not in df_rep_current.columns or 'Registration' not in df_rep_current.columns:
        df_rep_current = process_maintenance_reports(df_rep_current)

    target_reg = st.session_state.get("filter_reg_kw") or status["reg_prefix"]
    
    col_filt1, col_filt2, col_filt3 = st.columns([1, 1.5, 1.5])
    with col_filt1:
        reg_list = sorted(df_rep_current['Registration'].astype(str).unique().tolist())
        default_idx = reg_list.index(target_reg) if target_reg in reg_list else 0
        sel_reg = st.selectbox("Filter Registration", reg_list, index=default_idx)
    with col_filt2:
        ata_list = ["ALL ATA CHAPTERS"] + sorted(df_rep_current['ATA_Desc'].astype(str).unique().tolist())
        def_ata_idx = next((i for i, x in enumerate(ata_list) if "71 -" in x or "72 -" in x), 0)
        sel_ata = st.selectbox("Filter ATA Chapter", ata_list, index=def_ata_idx)
    with col_filt3:
        search_kw = st.text_input("Search Keyword in Defect Note / Action", placeholder="e.g., LEAK, WASH, FCU, AGM, ITT")

    # [PATCH #7] FITUR UNGGULAN: Day-to-Day 3-Way Relational Sync Audit (SSOT Join)
    st.markdown(f"<h3 style='color:#003B6F; margin-top:10px; margin-bottom:4px;'>Day-to-Day 3-Way Relational Sync Audit ({sel_reg})</h3>", unsafe_allow_html=True)
    st.caption("Single Source of Truth (SSOT) linking **Engine Telemetry**, **Airframe Utilization (FH/FC)**, and **PIREP/MAREP Defects** via exact **AML No** relational key.")
    
    with st.expander("View 3-Way Relational Master Table (Day-to-Day Synchronizer)", expanded=True):
        df_e_sync = st.session_state["df_data"].copy()
        df_e_sync["Reg"] = df_e_sync["Engine"].astype(str).apply(lambda x: x.split("|")[0].strip())
        df_e_sync = df_e_sync[df_e_sync["Reg"] == sel_reg]
        
        sync_rows = []
        if not df_e_sync.empty and "AML No" in df_e_sync.columns:
            for aml_val, grp in df_e_sync.groupby("AML No"):
                dt_val = grp["Date"].max()
                
                # Tarik data telemetri LH & RH
                lh_row = grp[grp["Engine"].astype(str).str.contains("LH")]
                rh_row = grp[grp["Engine"].astype(str).str.contains("RH")]
                lh_t5 = f"{lh_row['Delta_T5'].values[0]:+.1f}°C" if not lh_row.empty and "Delta_T5" in lh_row.columns else "N/A"
                rh_t5 = f"{rh_row['Delta_T5'].values[0]:+.1f}°C" if not rh_row.empty and "Delta_T5" in rh_row.columns else "N/A"
                
                # Tarik data jam terbang dari file Utilization
                u_match = df_util_current[df_util_current["AML No"] == aml_val] if "AML No" in df_util_current.columns else pd.DataFrame()
                fh_val = f"{u_match['FH'].values[0]} FH / {u_match['FC'].values[0]} FC" if not u_match.empty else "N/A"
                
                # Tarik laporan kerusakan dari file PIREP/MAREP
                r_match = df_rep_current[df_rep_current["AML No"] == aml_val]
                rep_val = f"[{r_match['ATA_Desc'].values[0]}] {r_match['Corrective Action'].values[0][:45]}..." if not r_match.empty else "Normal Operations (No Defect Logged)"
                
                sync_rows.append({
                    "AML No (Key)": aml_val,
                    "Flight Date": dt_val.strftime("%Y-%m-%d") if pd.notnull(dt_val) else "N/A",
                    "Airframe Util": fh_val,
                    "#1 LH ΔT5": lh_t5,
                    "#2 RH ΔT5": rh_t5,
                    "Maintenance Record / Action": rep_val
                })
            
            df_sync_view = pd.DataFrame(sync_rows).sort_values("Flight Date", ascending=False)
            st.dataframe(df_sync_view, use_container_width=True, hide_index=True, height=220)
        else:
            st.info("Relational synchronization data is being processed. Please execute ECTM analysis in Data Setup.")

    st.markdown("---")
    df_filtered = df_rep_current[df_rep_current['Registration'] == sel_reg]
    if sel_ata != "ALL ATA CHAPTERS":
        df_filtered = df_filtered[df_filtered['ATA_Desc'] == sel_ata]

    if search_kw:
        kw_clean = re.escape(search_kw.strip())
        kw_regex = r'\b' + kw_clean + r'\b'
        df_filtered = df_filtered[
            df_filtered['Note / Report'].astype(str).str.contains(kw_regex, case=False, regex=True) | 
            df_filtered['Corrective Action'].astype(str).str.contains(kw_regex, case=False, regex=True)
        ]

    st.markdown(f"**Found {len(df_filtered)} logged defect report(s) matching criteria for {sel_reg}:**")
    
    def highlight_text(text, kw):
        if not isinstance(text, str) or not text:
            return "No description."
        if not kw:
            return text
        kw_clean = re.escape(kw.strip())
        hl_style = 'background-color: #f0b73d; color: #003B6F; font-weight: 800; padding: 1px 6px; border-radius: 3px; box-shadow: 0 1px 2px rgba(0,0,0,0.1);'
        return re.sub(r'\b(' + kw_clean + r')\b', r'<mark style="' + hl_style + r'">\1</mark>', text, flags=re.IGNORECASE)

    if df_filtered.empty:
        st.info("No PIREP / MAREP reports found matching the selected filter criteria.")
    else:
        for idx, row in df_filtered.head(15).iterrows():
            with st.container(border=True):
                c_head1, c_head2, c_head3 = st.columns([2, 1, 1])
                c_head1.markdown(f"**AML No:** `{row.get('AML No', 'N/A')}` | **ATA:** `{row.get('ATA_Desc', 'N/A')}`")
                c_head2.markdown(f"**Date:** `{row['Date'].strftime('%Y-%m-%d') if pd.notnull(row['Date']) else 'N/A'}`")
                c_head3.markdown(f"**Position:** `{row.get('Position', 'General')}`")
                
                note_text = highlight_text(str(row.get('Note / Report', 'No description.')), search_kw)
                action_text = highlight_text(str(row.get('Corrective Action', 'Pending action.')), search_kw)
                
                st.markdown(f"**Defect Reported (PIREP/MAREP):**<br><div style='background:#F8FAFC; border-left:3px solid #CBD5E1; padding:8px 12px; margin:4px 0 8px 0; border-radius:0 4px 4px 0; font-size:0.9rem; line-height:1.5;'>{note_text}</div>", unsafe_allow_html=True)
                st.markdown(f"**Corrective Action Taken:**<br><div style='background:#F8FAFC; border-left:3px solid #003B6F; padding:8px 12px; margin:4px 0 8px 0; border-radius:0 4px 4px 0; font-size:0.9rem; line-height:1.5;'>{action_text}</div>", unsafe_allow_html=True)
                
                pn_off, pn_on = row.get('P/N Off'), row.get('P/N On')
                if pd.notnull(pn_off) or pd.notnull(pn_on):
                    st.caption(f"Component Change Tracking -> P/N Off: `{pn_off}` (S/N: `{row.get('S/N Off', '-')}`) ➔ P/N On: `{pn_on}` (S/N: `{row.get('S/N On', '-')}`)")

# ======================================================================================
# 18. PAGE 5: RECOMMENDATIONS, EWO EXPORT & NOTICE TRANSMITTAL (WITH TIER 1 CARDS)
# ======================================================================================
elif menu_selection == "Recommendations & Notice Transmittal":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Maintenance Recommendations & Notice Transmittal</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>Active Powerplant: <b style='color:#003B6F; background:#EFF4FA; padding:2px 8px; border-radius:4px; border:1px solid #CBD5E1;'>{selected_engine}</b> | P&WC PT6A-34 FIM (Rev 75.0)</p>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    overall_status_label = status["status_label"]
    st.markdown(f"**Observed Shift Vector:** `ΔT5: {status['shift_t5']}` | `ΔNg: {status['shift_ng']}` | `ΔWf: {status['shift_wf']}` &nbsp;&nbsp;|&nbsp;&nbsp; **System Classification:** **{overall_status_label}**")
    st.markdown("<br>", unsafe_allow_html=True)

    # [TIER 1 UPGRADE] Structured Recommendation Cards (Replacing Plain Alerts)
    for rec in recommendations:
        lvl = rec["level"]
        badge_cls = "badge-red" if lvl == "red" else ("badge-amber" if lvl == "amber" else "badge-green")
        card_cls = f"rec-card-{lvl}"
        
        st.markdown(f"""
        <div class="rec-card-box {card_cls}">
            <div class="rec-header">
                <span class="rec-title">{rec['title']}</span>
                <span class="{badge_cls}">{rec.get('priority', 'ROUTINE')}</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:12px; font-size:0.85rem; background:#F8FAFC; padding:8px 12px; border-radius:4px; border:1px solid #F1F5F9;">
                <div><span style="color:#64748B; font-weight:600;">Thermodynamic Signature:</span> <b>{rec.get('signature', 'N/A')}</b></div>
                <div><span style="color:#64748B; font-weight:600;">Estimated Downtime:</span> <b>{rec.get('downtime', 'N/A')}</b></div>
                <div><span style="color:#64748B; font-weight:600;">FIM Manual Ref:</span> <b style="color:#003B6F;">{rec['fim_ref']}</b></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<b>Action Directives & Engineering Procedures:</b>", unsafe_allow_html=True)
            st.markdown(rec["body"])
            st.write("")

    st.markdown("---")
    st.markdown("<h3 style='color:#003B6F; margin-bottom:4px;'>Engineering Document Export</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color:#475569; font-size:0.88rem; margin-bottom:14px;'>Download technical reports or generate formal Engineering Work Orders (EWO) for line maintenance execution.</p>", unsafe_allow_html=True)
    
    report_lines = [
        f"PT. AIRFAST INDONESIA - ECTM TECHNICAL ANALYSIS REPORT",
        f"Powerplant Serial / Position: {selected_engine}",
        f"Date Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Latest Cycle: {status['latest']['Date'].strftime('%Y-%m-%d')}",
        "-------------------------------------------------------------------------",
        f"Computed Residuals: Delta T5: {status['d_t5']:+.1f} degC | Delta Ng: {status['d_ng']:+.2f} % | Delta Wf: {status['d_wf']:+.1f} PPH",
        f"System Status Classification: {overall_status_label} | Predictive RUL: {status['rul_cycles']} Cycles ({status['proj_date']})",
        f"RUL Confidence Note: {status['rul_confidence']}",
        "-------------------------------------------------------------------------",
        "MAINTENANCE DIRECTIVES & RECOMMENDATIONS:",
    ]
    for rec in recommendations: 
        report_lines += [
            f"[{rec['fim_ref']}] {rec['title']}",
            f">> Priority: {rec.get('priority', 'ROUTINE')} | Est. Downtime: {rec.get('downtime', 'N/A')}",
            f">> Thermodynamic Signature: {rec.get('signature', 'N/A')}",
            rec["body"], 
            ""
        ]
    
    col_exp1, col_exp2, col_exp3 = st.columns(3)
    with col_exp1:
        st.download_button("Download Analysis Report (.txt)", data="\n".join(report_lines).encode("utf-8"), file_name=f"ECTM_Report_{status['reg_prefix']}_{datetime.now().strftime('%Y%m%d')}.txt", mime="text/plain", use_container_width=True)
    with col_exp2:
        ewo_html_data = generate_ewo_html(selected_engine, overall_status_label, status, recommendations)
        st.download_button("Download Print-Ready Order (.html)", data=ewo_html_data.encode("utf-8"), file_name=f"AIRFAST_EWO_{status['reg_prefix']}_{datetime.now().strftime('%Y%m%d')}.html", mime="text/html", use_container_width=True, help="Open downloaded HTML in browser and press Ctrl+P for formal signed documentation.")
    with col_exp3:
        if HAS_FPDF:
            pdf_bytes = generate_ewo_pdf(selected_engine, overall_status_label, status, recommendations)
            st.download_button("Download Formal EWO (.pdf)", data=pdf_bytes, file_name=f"AIRFAST_EWO_{status['reg_prefix']}_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", use_container_width=True, help="Download native PDF formatted for immediate printing and LAE physical sign-off.")
        else:
            st.button("PDF Export Unavailable (Install fpdf2)", disabled=True, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<h3 style='color:#003B6F; margin-bottom:4px;'>MCC Emergency Transmittal Protocol (Manual & Fleet-Scan Trigger)</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color:#475569; font-size:0.88rem; margin-bottom:14px;'>Transmit urgent engineering evaluations directly to responsible Fleet Managers and Maintenance Control Center (MCC).</p>", unsafe_allow_html=True)

    st.markdown("""
    <div style="background-color:#F8FAFC; border-left:4px solid #003B6F; border-top:1px solid #E2E8F0; border-right:1px solid #E2E8F0; border-bottom:1px solid #E2E8F0; padding:12px 16px; border-radius:4px; margin-bottom:16px;">
        <b style="color:#003B6F; font-size:0.85rem; letter-spacing:0.03em; display:block; margin-bottom:4px;">FLEET WATCHDOG - MANUAL TRIGGER</b>
        <span style="color:#475569; font-size:0.8rem; line-height:1.4; display:block;">Fleet-wide CRITICAL scanning is <b>not automatic</b> - use the "Run Fleet Health Scan Now" control in the sidebar (with your own recipient address) to check all engines at once.</span>
    </div>
    """, unsafe_allow_html=True)

    can_dispatch = st.session_state.get("user_role") not in ("Guest / Viewer",)

    with st.container(border=True):
        col_em1, col_em2 = st.columns([3, 1])
        with col_em1:
            target_emails = st.text_input(
                "Recipient Email Addresses (comma-separated)", value="",
                placeholder="mcc.duty@airfastindonesia.com, chief.engineer@airfastindonesia.com",
                disabled=not can_dispatch,
            )
        with col_em2:
            st.write("")
            st.write("")
            if not can_dispatch:
                st.button("Transmit Engineering Notice", disabled=True, use_container_width=True,
                           help="Guest accounts cannot dispatch official engineering notices. Log in with an authorized account.")
            elif st.button("Transmit Engineering Notice", type="primary", use_container_width=True):
                recipients_list = [e.strip() for e in target_emails.split(",") if e.strip()]
                if not recipients_list:
                    st.error("Enter at least one recipient email address.")
                else:
                    with st.spinner("Transmitting engineering notice via secure SMTP..."):
                        success = send_engineering_notice(selected_engine, status, "\n".join(report_lines), recipients_list, is_automated=False)
                        if success: st.success("Manual Engineering Notice transmitted successfully to target recipients.")
    if not can_dispatch:
        st.caption("Signed in as Guest / Viewer - dispatching official notices is restricted to authorized engineering/maintenance accounts.")