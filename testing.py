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
import html as html_lib
import json 
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from enum import Enum

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import plotly.express as px
import ectm_v5_5_core_optimized as ectm54
from llp_integration import (
    load_llp_workbook,
    engine_llp_view,
    LLP_DEFAULT_FILENAME,
)

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
    LOW_CONFIDENCE = 0
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
       4. SIDEBAR & BUTTONS (COMPACT PILL NAV - 100% WIDTH FIX)
       ========================================================================== */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #00284D 0%, #00172D 100%) !important; 
        border-right: none !important; box-shadow: 4px 0 20px rgba(0, 0, 0, 0.12);
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] div, [data-testid="stSidebar"] b { color: #F1F5F9 !important; }
      
    /* Menetralkan label luar */
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
    .hm-gray { background: rgba(100, 116, 139, 0.08); color: #475569; border: 1px solid rgba(100, 116, 139, 0.2); }
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
    
    /* ==========================================================================
       6. FORM INPUTS & DROPDOWNS (BULLETPROOF CONTRAST OVERRIDE)
       ========================================================================== */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-testid="stTextInput"] div[data-baseweb="input"] > div,
    div[data-testid="stNumberInput"] div[data-baseweb="input"] > div,
    div[data-testid="stDateInput"] div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    div[data-baseweb="base-input"] > input {
        background-color: #FFFFFF !important;
        border-top: 2px solid #334155 !important;    /* Slate-700: Garis gelap tegas */
        border-right: 2px solid #334155 !important;
        border-bottom: 2px solid #334155 !important;
        border-left: 2px solid #334155 !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 10px rgba(0, 40, 77, 0.08) !important; /* Shadow lebih tebal */
        color: #0F172A !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    
    /* Efek saat kursor diarahkan (Hover / Focus) berubah jadi Airfast Navy + Gold Glow */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover,
    div[data-testid="stTextInput"] div[data-baseweb="input"] > div:hover,
    div[data-baseweb="select"] > div:hover,
    div[data-baseweb="input"] > div:hover,
    div[data-baseweb="select"] > div:focus-within,
    div[data-baseweb="input"] > div:focus-within {
        border-top-color: #003B6F !important;
        border-right-color: #003B6F !important;
        border-bottom-color: #003B6F !important;
        border-left-color: #003B6F !important;
        box-shadow: 0 0 0 3px rgba(240, 183, 61, 0.3) !important; /* Sorotan emas */
    }
    
    /* Memastikan teks pilihan & ketikan selalu hitam pekat terbaca jelas */
    div[data-baseweb="select"] span, 
    div[data-baseweb="select"] div, 
    input[type="text"], input[type="number"] {
        color: #0F172A !important;
        font-weight: 600 !important;
    }
    input::placeholder { color: #64748B !important; opacity: 1 !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ======================================================================================
# 3A. V5 EXECUTIVE UI/UX LAYER — visual-only overrides; analytics remain unchanged
# ======================================================================================
if False:  # UI/UX experiment disabled; preserves the original visual design.
    st.markdown(
    """
<style>
    :root {
        --airfast-navy: #002E5D;
        --airfast-blue: #075A9C;
        --airfast-gold: #ECAF2E;
        --ink: #142033;
        --muted: #607087;
        --canvas: #F4F7FB;
        --line: #DCE5F0;
        --surface: #FFFFFF;
    }

    /* A calmer visual hierarchy: one canvas, one elevation system, readable density. */
    [data-testid="stAppViewContainer"], [data-testid="stApp"], .main { background: var(--canvas) !important; }
    .block-container { max-width: 1600px !important; padding: 1.15rem 2rem 2.6rem !important; }
    [data-testid="stHeader"] { background: rgba(244,247,251,.84) !important; backdrop-filter: blur(14px); }
    [data-testid="stToolbar"] { right: 1rem !important; }
    h1, h2, h3 { color: var(--airfast-navy) !important; }
    h1 { font-size: clamp(1.55rem, 2vw, 2.05rem) !important; letter-spacing: -.035em !important; }
    h2 { font-size: 1.38rem !important; }
    h3 { font-size: 1.02rem !important; letter-spacing: -.015em !important; }

    /* Full-bleed masthead: intentionally non-sticky so it never collides with
       Streamlit's own toolbar or clips its title while scrolling. */
    div[data-testid="stElementContainer"]:has(.sticky-header-box),
    div.element-container:has(.sticky-header-box) {
        position: relative !important; top: auto !important; z-index: auto !important;
        width: 100vw !important; max-width: 100vw !important;
        margin-left: calc(50% - 50vw) !important; margin-right: calc(50% - 50vw) !important;
        margin-bottom: .75rem !important; padding: 0 !important;
        background: #002E5D !important; border: 0 !important; box-shadow: none !important;
    }
    .ectm-masthead { background: linear-gradient(112deg, #001F43 0%, #003E76 56%, #075A9C 100%); border-bottom: 4px solid #ECAF2E; }
    .ectm-masthead-inner {
        max-width: 1560px; min-height: 128px; margin: 0 auto; padding: 1.35rem 2.4rem;
        display: grid; grid-template-columns: 260px 1fr auto; gap: 2rem; align-items: center;
    }
    .ectm-brand-lockup { display: flex; gap: .65rem; align-items: center; color: #fff; }
    .ectm-brand-lockup svg { width: 36px; height: 36px; flex: 0 0 auto; }
    .ectm-brand-lockup span { display: block; color: #fff; font-size: 1.04rem; font-weight: 800; letter-spacing: .08em; line-height: 1; }
    .ectm-brand-lockup small { display: block; margin-top: .24rem; color: #BFD4E9; font-size: .55rem; font-weight: 700; letter-spacing: .11em; }
    .ectm-title-group { border-left: 1px solid rgba(255,255,255,.22); padding-left: 2rem; }
    .ectm-eyebrow { margin: 0 0 .25rem; color: #ECAF2E !important; font-size: .63rem !important; font-weight: 800 !important; letter-spacing: .15em; }
    h1.ectm-title { margin: 0 !important; color: #FFFFFF !important; font-size: clamp(1.5rem, 2.15vw, 2.28rem) !important; font-weight: 800 !important; line-height: 1.1; letter-spacing: -.04em !important; }
    .ectm-subtitle { margin: .38rem 0 0 !important; color: #D8E6F3 !important; font-size: .82rem !important; font-weight: 600 !important; }
    .ectm-system-badge { min-width: 135px; color: #fff; font-size: .68rem; font-weight: 800; line-height: 1.35; letter-spacing: .07em; text-align: left; }
    .ectm-system-badge span { display: inline-block; width: 8px; height: 8px; margin-right: 6px; background: #47D07B; border-radius: 50%; box-shadow: 0 0 0 4px rgba(71,208,123,.14); }
    .ectm-system-badge small { color: #AFC9E1; font-size: .55rem; font-weight: 700; letter-spacing: .08em; }

    /* Metric cards become scan-friendly, while keeping every existing metric intact. */
    div[data-testid="stMetric"] {
        min-height: 98px; border: 1px solid var(--line) !important;
        border-radius: 14px !important; box-shadow: 0 3px 12px rgba(22, 44, 77, .045) !important;
        background: linear-gradient(135deg, #fff 0%, #FAFCFF 100%) !important;
    }
    div[data-testid="stMetric"]::before { height: 4px !important; background: linear-gradient(90deg, var(--airfast-navy), var(--airfast-gold)) !important; }
    div[data-testid="stMetricValue"] > div { font-size: 1.62rem !important; }
    div[data-testid="stMetricDelta"] { font-size: .72rem !important; font-weight: 700 !important; }

    /* Consistent interaction language across controls. */
    div[data-testid="stButton"] > button, div[data-testid="stDownloadButton"] > button {
        min-height: 2.5rem; border-radius: 9px !important; font-weight: 750 !important;
        transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease !important;
    }
    div[data-testid="stButton"] > button:hover, div[data-testid="stDownloadButton"] > button:hover {
        transform: translateY(-1px); box-shadow: 0 7px 16px rgba(7, 45, 88, .12) !important;
    }
    div[data-testid="stButton"] > button[kind="primary"] { background: linear-gradient(135deg, #075A9C, #002E5D) !important; }
    div[data-testid="stDownloadButton"] > button { border-color: #B9C9DB !important; }

    /* Better navigation, tables and charts at operational viewing distance. */
    [data-testid="stSidebar"] { box-shadow: 5px 0 26px rgba(0, 23, 50, .16) !important; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { line-height: 1.5; }
    div[data-testid="stTabs"] { background: rgba(255,255,255,.65); border: 1px solid var(--line); border-radius: 12px; padding: 4px 7px; }
    div[data-testid="stTabs"] button[role="tab"] { border-radius: 8px !important; }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { box-shadow: inset 0 -3px 0 var(--airfast-gold); }
    [data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: white; }
    [data-testid="stPlotlyChart"] { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: #fff; padding: 3px; }
    div[data-testid="stExpander"] { border-color: var(--line) !important; box-shadow: none !important; }
    [data-testid="stAlert"] { border-radius: 10px !important; }

    /* Visible keyboard focus and a genuinely usable compact-screen layout. */
    button:focus-visible, input:focus-visible, [role="tab"]:focus-visible { outline: 3px solid rgba(236,175,46,.62) !important; outline-offset: 2px; }
    @media (max-width: 900px) {
        .block-container { padding: .85rem 1rem 2rem !important; }
        div[data-testid="stElementContainer"]:has(.sticky-header-box), div.element-container:has(.sticky-header-box) { margin-left: calc(50% - 50vw) !important; margin-right: calc(50% - 50vw) !important; }
        .ectm-masthead-inner { grid-template-columns: 1fr; gap: .7rem; min-height: auto; padding: 1rem 1.2rem 1.1rem; }
        .ectm-title-group { border-left: 0; padding-left: 0; }
        .ectm-system-badge { display: none; }
        div[data-testid="stMetric"] { min-height: 82px; padding: 12px !important; }
        div[data-testid="stTabs"] button[role="tab"] { padding: 7px 10px !important; font-size: .78rem !important; }
    }
</style>
""",
    unsafe_allow_html=True,
)

# ======================================================================================
# 4. SESSION STATE MANAGEMENT & CALLBACK HELPERS (AUTHENTICATION INTEGRATED)
# ======================================================================================
if "active_menu" not in st.session_state:
    st.session_state["active_menu"] = "Overview"
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
            /* 1. BERSIH-BERSIH: Hilangkan Sidebar, Header, dan Garis Atas */
            [data-testid="stSidebar"], [data-testid="collapsedControl"], [data-testid="stHeader"] { 
                display: none !important; 
            }
            .sticky-header-box, div[data-testid="stElementContainer"]:has(.sticky-header-box), div.element-container:has(.sticky-header-box) { 
                display: none !important; 
            }
            .block-container { 
                padding-top: 3.5rem !important; 
                max-width: 1100px !important; 
            }

            /* 2. PENYEJAJARAN: Tinggi kontainer 520px dan rata tengah vertikal */
            [data-testid="column"]:nth-of-type(2) [data-testid="stVerticalBlockBorderWrapper"] {
                height: 520px !important;
                border-radius: 16px !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: center !important;
                background-color: #FFFFFF !important;
                box-shadow: 0 10px 25px rgba(0, 40, 77, 0.05) !important;
            }

            /* 3. PERMAINAN WARNA: Kotak Input dijadikan Abu-abu Soft */
            div[data-testid="stTextInput"] div[data-baseweb="base-input"],
            div[data-testid="stTextInput"] div[data-baseweb="input"],
            div[data-testid="stTextInput"] div[data-baseweb="input"] > div {
                background-color: #F1F5F9 !important;
                border: none !important;
                border-radius: 8px !important;
            }
            div[data-testid="stTextInput"] div[data-baseweb="input"] > div:focus-within {
                background-color: #FFFFFF !important;
                border: 1.5px solid #003B6F !important;
                box-shadow: 0 0 0 3px rgba(0, 59, 111, 0.15) !important;
            }
            div[data-testid="stTextInput"] input {
                color: #0F172A !important;
                font-weight: 600 !important;
            }
            div[data-testid="stTextInput"] input::placeholder {
                color: #94A3B8 !important;
            }

            /* =========================================================
               [FIX BARU] CLASS CSS KHUSUS UNTUK TEKS HERO IMAGE
               Disimpan di sini agar !important tidak dihapus Streamlit
               ========================================================= */
            .hero-title-white {
                color: #FFFFFF !important;
                text-shadow: 0px 4px 10px rgba(0,0,0,0.7), 0px 1px 3px rgba(0,0,0,0.5) !important;
            }
            .hero-subtitle-gold {
                color: #f0b73d !important;
                text-shadow: 0px 2px 5px rgba(0,0,0,0.8) !important;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Membuat Layout Split-Screen
    col_img, col_form = st.columns([1.2, 1], gap="large")
    
    # ================= SISI KIRI (GAMBAR HERO & BRANDING) =================
    with col_img:
        hero_path = "login_hero.jpg"
        if os.path.exists(hero_path):
            import base64
            with open(hero_path, "rb") as f_img:
                b64_hero = base64.b64encode(f_img.read()).decode()
            
            # Memanggil CSS class yang sudah dibuat aman di atas
            st.markdown(f"""
<div style="border-radius: 16px; overflow: hidden; height: 520px; position: relative; box-shadow: 0 10px 25px rgba(0, 40, 77, 0.15);">
<img src="data:image/jpeg;base64,{b64_hero}" style="width: 100%; height: 100%; object-fit: cover; position: absolute; top: 0; left: 0;">
<div style="position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(0deg, rgba(0, 40, 77, 0.95) 0%, rgba(0, 40, 77, 0) 100%); padding: 40px 30px 30px 30px;">

<h2 class="hero-title-white" style="font-weight: 800; font-size: 1.8rem; margin: 0; line-height: 1.2;">Engineering the Future<br>of Fleet Reliability.</h2>

<p class="hero-subtitle-gold" style="font-weight: 600; font-size: 0.95rem; margin-top: 8px;">Engine Condition Trend Monitoring Dashboard</p>

</div>
</div>
""", unsafe_allow_html=True)
        else:
            st.markdown("""
<div style="background: linear-gradient(135deg, #00284D 0%, #00488A 100%); padding: 40px; border-radius: 16px; height: 520px; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 10px 25px rgba(0, 40, 77, 0.15);">
<div style="width: 50px; height: 4px; background: #f0b73d; margin-bottom: 20px; border-radius: 2px;"></div>
<h1 class="hero-title-white" style="font-size: 2.2rem; font-weight: 800; margin-bottom: 10px; line-height: 1.2;">Engineering the Future<br>of Fleet Reliability.</h1>
<p style="color: #94A3B8 !important; font-size: 1rem; line-height: 1.6; margin-top: 10px;">Advanced thermodynamic telemetry and FIM diagnostic integration for the AIRFAST DHC-6 Twin Otter powerplant operations.</p>
</div>
""", unsafe_allow_html=True)

    # ================= SISI KANAN (FORM LOGIN) =================
    with col_form:
        with st.container(border=True):
            logo_path = "images.png"  
            if os.path.exists(logo_path):
                import base64
                with open(logo_path, "rb") as f_img:
                    b64_logo = base64.b64encode(f_img.read()).decode()
                st.markdown(f"""
                <div style="text-align: center; padding-top: 0px; padding-bottom: 10px;">
                    <img src="data:image/png;base64,{b64_logo}" style="width: 50%; max-width: 180px; height: auto;">
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("<h2 style='text-align:center; color:#003B6F; padding-top:0px; margin:0;'>AIRFAST</h2>", unsafe_allow_html=True)
            
            st.markdown("<hr style='margin: 0px 0px 16px 0px; border: none; height: 1px; background: #E2E8F0;'>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; font-weight:700; color:#0F172A; font-size:1.05rem; margin-bottom:2px;'>Authorization Portal</p>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; font-weight:500; color:#64748B; font-size:0.85rem; margin-top:0px;'>Enter your corporate credentials to access airworthiness records.</p>", unsafe_allow_html=True)
            st.write("")

            with st.form("fullscreen_login_form", clear_on_submit=False, border=False):
                input_email = st.text_input("Corporate Email Address", placeholder="user@airfastindonesia.com").strip()
                input_password = st.text_input("Password", type="password", placeholder="••••••••")

                st.write("")
                c_btn1, c_btn2 = st.columns(2)
                with c_btn1:
                    btn_login = st.form_submit_button("Login", type="primary", use_container_width=True)
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
                        st.error("Invalid email or password.")
                        
                if btn_guest:
                    st.session_state["logged_in"] = True
                    st.session_state["user_email"] = "guest.auditor@airfast.com"
                    st.session_state["user_name"] = "External Auditor / Guest"
                    st.session_state["user_role"] = "Guest / Viewer"
                    st.rerun()
            
            st.markdown("<hr style='margin: 10px 0px 10px 0px; border: none; height: 1px; background: #E2E8F0;'>", unsafe_allow_html=True)
            st.caption("**Access Notice:** This is an internal access gate for the ECTM prototype, not a substitute "
                       "for a production authentication/audit system. Do not reuse real credentials here.")
            
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
    return pd.to_datetime(parsed, errors="coerce")

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
    # Mengembalikan DataFrame kosong murni (Tanpa data fiktif/simulasi)
    df_ectm = pd.DataFrame(columns=["AML No", "Date", "Engine", "Press_Alt", "IOAT", "IAS", "TQ", "Np", "T5", "Ng", "Wf", "Oil_Temp", "Oil_Press"])
    df_util = pd.DataFrame(columns=["AML No", "Registration", "Work (Date)", "FH", "FC", "Block Hours", "From", "To"])
    df_rep = pd.DataFrame(columns=["AML No", "Date", "Registration", "ATA", "ATA_Desc", "Note / Report", "Corrective Action", "Position", "P/N Off", "P/N On", "S/N Off", "S/N On"])

    return df_ectm, df_util, df_rep, False, False

# --- SISTEM BASIS DATA PERMANEN (SUSTAINABLE STORAGE) ---
DB_DIR = ".airfast_db"
os.makedirs(DB_DIR, exist_ok=True)
ECTM_DB_PATH = os.path.join(DB_DIR, "ectm_master.csv")
UTIL_DB_PATH = os.path.join(DB_DIR, "util_master.csv")
REP_DB_PATH = os.path.join(DB_DIR, "rep_master.csv")

def _sanitize_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    """[BUG FIX] CSV formula injection guard. "Note / Report" and
    "Corrective Action" are free-text fields any logged-in user - including
    Guest, since manual entry is intentionally open to everyone - can
    populate. If a cell's text starts with =, +, -, or @, Excel/Sheets will
    interpret it as a formula the instant this CSV is opened directly (e.g.
    for a manual backup/audit), which can silently execute unintended
    lookups or, in older Excel versions, external commands via DDE. This is
    the same underlying risk as the stored-XSS fix applied earlier to the
    Logbook page's HTML rendering - same free-text source, different output
    surface (spreadsheet instead of browser)."""
    df = df.copy()
    risky_prefixes = ("=", "+", "-", "@")
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(
            lambda v: f"'{v}" if isinstance(v, str) and v.startswith(risky_prefixes) else v
        )
    return df

def save_ectm_db(): st.session_state["df_data"].to_csv(ECTM_DB_PATH, index=False)
def save_util_db(): st.session_state["df_util"].to_csv(UTIL_DB_PATH, index=False)
def save_rep_db(): _sanitize_for_csv(st.session_state["df_rep"]).to_csv(REP_DB_PATH, index=False)


def _file_signature(paths):
    """Return a stable fingerprint for source workbooks."""
    sig = []
    for path in sorted(paths):
        try:
            stt = os.stat(path)
            sig.append((os.path.basename(path), stt.st_size, stt.st_mtime_ns))
        except OSError:
            continue
    return tuple(sig)

def _find_source_column(df, candidates):
    """Case/whitespace-insensitive lookup for source workbook headers."""
    exact = {str(c): c for c in df.columns}
    for c in candidates:
        if c in exact:
            return exact[c]
    norm = {re.sub(r"\s+", " ", str(c).strip()).lower(): c for c in df.columns}
    for c in candidates:
        key = re.sub(r"\s+", " ", str(c).strip()).lower()
        if key in norm:
            return norm[key]
    return None


def _normalise_event_column(df, position=None):
    """Preserve source Event Name; never invent an event."""
    df = df.copy()
    suffix = "1" if position == "LH" else ("2" if position == "RH" else None)
    candidates = []
    if suffix:
        candidates += [f"Event Name ({suffix})", f"Event_Name ({suffix})"]
    candidates += ["Event_Name", "Event Name", "Event", "EVENT_NAME", "EVENT"]
    src = _find_source_column(df, candidates)
    if src is not None:
        df["Event_Name"] = df[src]
        df["Event_Name"] = df["Event_Name"].astype("string").str.strip()
        df.loc[df["Event_Name"].isin(["", "<NA>", "nan", "None"]), "Event_Name"] = pd.NA
    elif "Event_Name" not in df.columns:
        df["Event_Name"] = pd.NA
    return df


def _normalise_reference_column(df, position=None):
    """Preserve AIRFAST Reference metadata using the LH/RH source convention."""
    df = df.copy()
    suffix = "1" if position == "LH" else ("2" if position == "RH" else None)
    candidates = []
    if suffix:
        candidates += [f"Reference ({suffix})", f"Reference_{suffix}"]
    candidates += ["Reference", "Reference_Name", "Reference Name"]
    src = _find_source_column(df, candidates)
    if src is not None:
        df["Reference"] = df[src]
    elif "Reference" not in df.columns:
        df["Reference"] = pd.NA
    return df

def sync_local_fleet_data(data_dir="data"):
    """Sync all local source workbooks into the persistent SSOT.

    The operation is idempotent: rerunning the dashboard does not create duplicate
    rows. Source rows are refreshed, while explicit MANUAL records are retained.
    """
    if not os.path.isdir(data_dir):
        return {"ok": False, "reason": "missing_directory", "files": 0, "ectm": 0, "util": 0, "rep": 0, "skipped": []}

    files = [os.path.join(data_dir, f) for f in os.listdir(data_dir)
             if f.lower().endswith((".xlsx", ".xls")) and not f.startswith("~")]
    if not files:
        return {"ok": True, "reason": "no_files", "files": 0, "ectm": 0, "util": 0, "rep": 0, "skipped": []}

    source_ectm, source_util, source_rep, skipped = [], [], [], []

    for filepath in files:
        filename = os.path.basename(filepath)
        try:
            raw = pd.read_excel(filepath)
        except Exception as exc:
            skipped.append(f"{filename}: {exc}")
            continue

        # 1) Flight utilization
        if "utilization" in filename.lower() or ("FH" in raw.columns and "FC" in raw.columns):
            if "Work (Date)" in raw.columns and "Registration" in raw.columns:
                u = raw.copy()
                u["Work (Date)"] = safe_parse_dates(u["Work (Date)"])
                u = u.dropna(subset=["Registration", "Work (Date)"]).copy()
                u["Registration"] = u["Registration"].astype(str).str.strip().str.upper()
                u["Data_Source"] = "LOCAL_SYNC"
                source_util.append(u)
            continue

        # 2) PIREP / MAREP
        if ("maintenance" in filename.lower() or "pirep" in filename.lower()
                or "report" in filename.lower()
                or ("ATA" in raw.columns and "Corrective Action" in raw.columns)):
            r = process_maintenance_reports(raw)
            if not r.empty:
                r["Data_Source"] = "LOCAL_SYNC"
                source_rep.append(r)
            continue

        # 3) Engine telemetry / pilot flight logbook exports
        match = re.search(r"(O[A-Z]{2})", filename.upper())
        reg_id = f"PK-{match.group(1)}" if match else "UNKNOWN"
        for num, pos in (("1", "LH"), ("2", "RH")):
            dt_col = f"DateTime ({num})"
            if dt_col not in raw.columns:
                continue
            mapping = {
                dt_col: "Date", f"ITT ({num})": "T5", f"NG ({num})": "Ng",
                f"WF ({num})": "Wf", f"IOAT ({num})": "IOAT", f"P.ALT ({num})": "Press_Alt",
                f"Torque ({num})": "TQ", f"NP ({num})": "Np", f"IAS ({num})": "IAS",
                f"Oil Temperature ({num})": "Oil_Temp", f"Oil Pressure ({num})": "Oil_Press"
            }
            missing = [c for c in mapping if c not in raw.columns]
            if missing:
                skipped.append(f"{filename} #{num}: missing {missing}")
                continue
            src = _normalise_event_column(raw, pos)
            src = _normalise_reference_column(src, pos)
            pref = f"IS PREFERRED ({num})"
            if pref in src.columns:
                src = src[src[pref].astype(str).str.upper().ne("N")].copy()
            mapped = src[list(mapping.keys())].rename(columns=mapping).copy()
            if "Event_Name" in src.columns:
                mapped["Event_Name"] = src.loc[mapped.index, "Event_Name"].values
            if "Reference" in src.columns:
                mapped["Reference"] = src.loc[mapped.index, "Reference"].values
            mapped["Engine"] = f"{reg_id} | {pos}"
            mapped["Data_Source"] = "LOCAL_SYNC"
            source_ectm.append(mapped)

    # ECTM merge: refresh source rows but preserve deliberate manual records.
    if source_ectm:
        sync = pd.concat(source_ectm, ignore_index=True)
        sync["Date"] = pd.to_datetime(sync["Date"], errors="coerce")
        sync = sync.dropna(subset=["Date"]).copy()
        if "AML No" not in sync.columns:
            sync["AML No"] = sync.apply(
                lambda r: f"AML-{str(r['Engine']).split('|')[0].strip()}-{r['Date'].strftime('%Y%m%d%H%M%S')}", axis=1
            )
        current = st.session_state["df_data"].copy()
        current["Date"] = pd.to_datetime(current.get("Date"), errors="coerce")
        if "Data_Source" not in current.columns:
            current["Data_Source"] = "LEGACY_DB"
        merged = pd.concat([current, sync], ignore_index=True)
        merged["_priority"] = merged["Data_Source"].map({"LOCAL_SYNC": 1, "LEGACY_DB": 1, "UPLOAD": 1, "MANUAL": 2}).fillna(1)
        merged = merged.sort_values(["Date", "_priority"])
        merged = merged.drop_duplicates(subset=["Date", "Engine"], keep="last").drop(columns=["_priority"])
        st.session_state["df_data"] = merged.sort_values("Date").reset_index(drop=True)

    # Utilization merge.
    if source_util:
        sync_u = pd.concat(source_util, ignore_index=True)
        cur_u = st.session_state["df_util"].copy()
        if "Data_Source" not in cur_u.columns:
            cur_u["Data_Source"] = "LEGACY_DB"
        cur_u = pd.concat([cur_u, sync_u], ignore_index=True)
        cur_u = cur_u.drop_duplicates(subset=["Registration", "Work (Date)", "FH", "FC"], keep="last")
        st.session_state["df_util"] = cur_u.reset_index(drop=True)
        st.session_state["util_is_real"] = not cur_u.empty

    # PIREP / MAREP merge.
    if source_rep:
        sync_r = process_maintenance_reports(pd.concat(source_rep, ignore_index=True))
        cur_r = st.session_state["df_rep"].copy()
        if "Data_Source" not in cur_r.columns:
            cur_r["Data_Source"] = "LEGACY_DB"
        cur_r = pd.concat([cur_r, sync_r], ignore_index=True)
        cur_r = cur_r.drop_duplicates(subset=["Registration", "Date", "ATA", "Note / Report"], keep="last")
        st.session_state["df_rep"] = process_maintenance_reports(cur_r)
        st.session_state["rep_is_real"] = not st.session_state["df_rep"].empty

    save_ectm_db()
    save_util_db()
    save_rep_db()
    return {"ok": True, "reason": "synced", "files": len(files),
            "ectm": sum(len(x) for x in source_ectm),
            "util": sum(len(x) for x in source_util),
            "rep": sum(len(x) for x in source_rep), "skipped": skipped}

if "df_data" not in st.session_state:
    if os.path.exists(ECTM_DB_PATH):
        st.session_state["df_data"] = pd.read_csv(ECTM_DB_PATH)
        st.session_state["df_util"] = pd.read_csv(UTIL_DB_PATH) if os.path.exists(UTIL_DB_PATH) else pd.DataFrame()
        st.session_state["df_rep"] = pd.read_csv(REP_DB_PATH) if os.path.exists(REP_DB_PATH) else pd.DataFrame()
        st.session_state["util_is_real"] = not st.session_state["df_util"].empty
        st.session_state["rep_is_real"] = not st.session_state["df_rep"].empty
    else:
        e_df, u_df, r_df, u_is_real, r_is_real = init_all_datasets()
        st.session_state["df_data"] = e_df
        st.session_state["df_util"] = u_df
        st.session_state["df_rep"] = r_df
        st.session_state["util_is_real"] = u_is_real
        st.session_state["rep_is_real"] = r_is_real
        save_ectm_db()
        save_util_db()
        save_rep_db()

# Auto-sync local source workbooks on rerun when any source file changed.
# The database remains the persistent SSOT between reruns.
if "_auto_sync_signature" not in st.session_state:
    st.session_state["_auto_sync_signature"] = None
_auto_data_dir = "data"
if os.path.isdir(_auto_data_dir):
    _auto_paths = [os.path.join(_auto_data_dir, f) for f in os.listdir(_auto_data_dir)
                   if f.lower().endswith((".xlsx", ".xls")) and not f.startswith("~")]
    _auto_sig = _file_signature(_auto_paths)
    if _auto_sig != st.session_state["_auto_sync_signature"]:
        _auto_result = sync_local_fleet_data(_auto_data_dir)
        if _auto_result.get("ok"):
            st.session_state["_auto_sync_signature"] = _auto_sig
            st.session_state["_auto_sync_last_result"] = _auto_result

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
            # Paksa jadi angka, yang huruf/salah ketik otomatis jadi NaN
            ioat_num = pd.to_numeric(df["IOAT"], errors="coerce")
            if (ioat_num > 55.0).any() or (ioat_num < -40.0).any():
                alerts.append("[PHYSICAL OUTLIER] IOAT exceeds standard operational atmospheric envelope (-40°C to +55°C).")
        
        if "T5" in df.columns:
            t5_num = pd.to_numeric(df["T5"], errors="coerce")
            if (t5_num <= 200).any():
                alerts.append("[SENSOR ERROR] T5 recorded below minimum operating temperature (200°C) during active flight.")
        
        for col in ["T5", "Ng", "Wf"]:
            if col in df.columns and len(df) >= 3:
                col_num = pd.to_numeric(df[col], errors="coerce")
                stuck_mask = (col_num.diff() == 0) & (col_num.diff().shift(-1) == 0)
                if stuck_mask.any():
                    alerts.append(f"[SENSOR FREEZE SUSPECTED] Column '{col}' contains identical consecutive static values for 3+ cycles.")
    return alerts

# ======================================================================================
# 7. THERMODYNAMIC LEAST-SQUARES REGRESSION & ADAPTIVE NOISE BANDING
# ======================================================================================
def fit_correction_model(df_baseline: pd.DataFrame, predictors: list, target: str):
    # [BUG FIX] Was raised to > 0.5 - an absolute cutoff in each predictor's
    # own raw units. IOAT (degC) and Press_Alt (feet) naturally have large
    # variance and always clear this bar, but TQ and Np are both
    # percentage-scale and governed close to a setpoint, so their natural
    # cycle-to-cycle std is small even when genuinely informative for the
    # correction model. Verified against all 10 real Airfast engine files at
    # baseline_n = 3/6/10 (the realistic range around the default of 6): TQ
    # and/or Np were silently dropped EVERY time, for EVERY aircraft - not
    # an edge case, a fleet-wide methodology regression. The 1e-6 threshold
    # exists only to guard against a singular/ill-conditioned regression
    # matrix from a truly-constant column, not to filter "low-signal"
    # predictors by an arbitrary absolute magnitude.
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

def determine_optimal_baseline(df_engine, min_cycles=15, max_cycles=30):
    """Validated reference-size policy."""
    eng = str(df_engine["Engine"].iloc[-1]) if len(df_engine) else ""
    target = ectm54.VALIDATED_BASELINES_CRUISE.get(eng, ectm54.CFG54.baseline_target_default)
    return min(target, len(df_engine))

@st.cache_data(show_spinner=False)
def compute_engine_trend(df_engine: pd.DataFrame, use_correction: bool = True):
    """Final validated ECTM trend engine."""
    df_engine = df_engine.sort_values("Date").reset_index(drop=True).copy()
    if df_engine.empty:
        return df_engine
    eng = str(df_engine["Engine"].iloc[-1])
    parts = [x.strip() for x in eng.split("|")]
    registration, position = parts[0], (parts[1] if len(parts)>1 else "LH")
    out = ectm54.compute_v54(df_engine, registration, position)
    out = ectm54.classify_v54(out)
    out["Delta_Ng_pct"] = out["Delta_Ng"]
    n=int(out.attrs.get("baseline_n",0))
    wf_mean=float(out.loc[out.index[:n],"Wf"].mean()) if n else 1.0
    out["Delta_Wf_pct"]=100.0*out["Delta_Wf"]/wf_mean if wf_mean else out["Delta_Wf"]
    for t in ["T5","Ng","Wf"]:
        out[f"Adaptive_Sigma_{t}"]=out.attrs.get("noise",{}).get(t,1.0)
    out.attrs["regression_downgraded"]=any(m.get("mode")!="regression" for m in out.attrs.get("models",{}).values())
    return out

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
    # [PENGAMAN LOGIKA]: Mencegah pembagian terlalu kecil jika data < 3 hari
    if days < 3: 
        return 2.5 
    
    total_fc = df_reg['FC'].sum()
    return max(0.5, total_fc / days)

# ======================================================================================
# 9. ENGINE HEALTH CLASSIFICATION & FIM DIRECTIVE GENERATION (SSOT ENGINE)
# ======================================================================================
def classify_direction(value, shift_band):
    if value > shift_band: return "UP"
    if value < -shift_band: return "DOWN"
    return "NORMAL"

def build_status(df_engine: pd.DataFrame, df_util: pd.DataFrame):
    latest=df_engine.iloc[-1]
    d_t5,d_ng,d_wf=latest["Delta_T5"],latest["Delta_Ng"],latest["Delta_Wf"]
    confidence=str(latest.get("Model_Confidence","LOW"))
    row_status=str(latest.get("ECTM_Row_Status","UNAVAILABLE"))

    # Model confidence is diagnostic metadata, not engine-health status.
    if confidence!="HIGH":
        health_level=EngineHealth.NORMAL
        status_label="NORMAL"
    elif row_status=="CRITICAL":
        health_level=EngineHealth.CRITICAL
        status_label="CRITICAL"
    elif row_status=="ADVISORY":
        health_level=EngineHealth.ADVISORY
        status_label="ADVISORY"
    else:
        health_level=EngineHealth.NORMAL
        status_label="NORMAL"

    shift_t5=classify_direction(d_t5,SHIFT_T5_C) if np.isfinite(d_t5) else "NORMAL"
    shift_ng=classify_direction(d_ng,SHIFT_NG_PCT) if np.isfinite(d_ng) else "NORMAL"
    shift_wf=classify_direction(latest.get("Delta_Wf_pct",d_wf),SHIFT_WF_PCT) if np.isfinite(d_wf) else "NORMAL"
    alarm_wash=bool(np.isfinite(d_t5) and d_t5>=T5_WASH_C)
    alarm_borescope_t5=bool(np.isfinite(d_t5) and d_t5>=T5_BORESCOPE_C)
    alarm_borescope_ng=bool(np.isfinite(d_ng) and d_ng<=NG_BORESCOPE_LOW_PCT)

    vals_t5=df_engine["Delta_T5"].dropna()
    vals_ng=df_engine["Delta_Ng"].dropna()
    sustained_t5=sustained_flag(vals_t5,T5_WASH_C,SUSTAIN_WINDOW)
    isolated_t5=isolated_spike_flag(vals_t5,T5_WASH_C)
    sustained_ng=sustained_flag(vals_ng,NG_BORESCOPE_LOW_PCT,SUSTAIN_WINDOW)
    isolated_ng=isolated_spike_flag(vals_ng,NG_BORESCOPE_LOW_PCT)

    slope_t5=rolling_slope(vals_t5,TREND_WINDOW)
    slope_ng=rolling_slope(vals_ng,TREND_WINDOW)

    if confidence=="HIGH":
        r5=calculate_rul(d_t5,slope_t5,T5_BORESCOPE_C,"UP")
        rn=calculate_rul(d_ng,slope_ng,NG_BORESCOPE_LOW_PCT,"DOWN")
        rul_cycles=min(r5,rn)
        rul_limiting_param="Ng" if rn<r5 else "T5"
    else:
        r5=rn=rul_cycles=999
        rul_limiting_param="N/A"

    mm=re.search(r"(PK-[A-Z0-9]{3,4})",str(latest["Engine"]).upper())
    reg_prefix=mm.group(1) if mm else str(latest["Engine"]).split("|")[0].strip()
    fc_per_day=get_aircraft_utilization_rate(reg_prefix,df_util)
    days_left=int(rul_cycles/fc_per_day) if fc_per_day>0 and rul_cycles<999 else 999
    proj_date=(datetime.now()+timedelta(days=days_left)).strftime("%Y-%m-%d") if rul_cycles<999 else "Stable"

    return dict(
        latest=latest,d_t5=d_t5,d_ng=d_ng,d_wf=d_wf,
        shift_t5=shift_t5,shift_ng=shift_ng,shift_wf=shift_wf,
        alarm_wash=alarm_wash,alarm_borescope_t5=alarm_borescope_t5,
        alarm_borescope_ng=alarm_borescope_ng,
        sustained_t5=sustained_t5,isolated_t5=isolated_t5,
        sustained_ng=sustained_ng,isolated_ng=isolated_ng,
        control_breach=row_status=="ADVISORY",is_abnormal=row_status=="CRITICAL",
        health_level=health_level,status_label=status_label,
        slope_t5=slope_t5,slope_ng=slope_ng,
        rul_cycles=rul_cycles,rul_limiting_param=rul_limiting_param,
        proj_date=proj_date,fc_per_day=fc_per_day,
        rul_confidence=("Unavailable because current ECTM confidence is LOW." if confidence!="HIGH"
                        else "Indicative only - assumes a constant (linear) degradation rate"),
        rul_is_linear_caution=False,
        reg_prefix=reg_prefix,model_confidence=confidence,
        ectm_signal=str(latest.get("ECTM_Signal","")),
        baseline_n=int(df_engine.attrs.get("baseline_n",0)),
        baseline_policy=df_engine.attrs.get("baseline_policy","UNKNOWN"),
        reference_model_quality=str(latest.get("Reference_Model_Quality","LOW")),
        reference_model_quality_reason=str(latest.get("Reference_Model_Quality_Reason","")),
        current_applicability=bool(latest.get("Current_Applicability",False)),
        current_domain_coverage_pct=float(latest.get("Current_Domain_Coverage_pct",0)),
        historical_domain_coverage_min_pct=float(
            latest.get("Historical_Domain_Coverage_Min_pct",
                       latest.get("Domain_Coverage_Min_pct",0))
        ),
        confidence_reason=str(latest.get("Confidence_Reason","")),
        engine_state=str(latest.get("Engine_State_Reference","UNSPECIFIED")),
        engine_state_available=bool(latest.get("Engine_State_Available",False)),
        engine_state_quality=str(latest.get("Engine_State_Quality","NOT_PROVIDED")),
    )

def generate_recommendations(df_engine: pd.DataFrame, status: dict) -> list:
    recs = []
    if status.get("model_confidence") != "HIGH":
        recs.append(dict(
            level="slate",
            title="ECTM Monitoring Note | Assessment Confidence Limited",
            fim_ref="N/A — no FIM-level diagnosis from low-confidence model",
            priority="MONITORING NOTE",
            downtime="0 Hours (No automatic maintenance action)",
            signature=(
                f"Reference quality={status.get('reference_model_quality','LOW')} | "
                f"Current applicability={'YES' if status.get('current_applicability') else 'NO'} | "
                f"Current domain coverage={status.get('current_domain_coverage_pct',0):.0f}% | "
                f"Historical min coverage={status.get('historical_domain_coverage_min_pct',0):.1f}%"
            ),
            body=("AIRFAST operational status remains NORMAL because no valid ECTM Advisory or Critical condition has been established. "
                  "ECTM confidence is limited for this engine, so the model result is not used to declare an abnormal engine condition.\n\n"
                  f"**Reason:** {status.get('confidence_reason','ECTM assessment confidence is limited.')}\n\n"
                  "**Engineering Directive:** verify the engine-state reference, operating regime, data quality, and current reference-domain applicability before using ECTM deviation for maintenance decisions.")
        ))
        return recs
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
                title="Advisory Monitoring | Statistical Baseline Trend Deviation", 
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

    # [KUNCI STATIS & LEGEND RESTORATION]
    # Koordinat y diturunkan ke -0.28 agar duduk manis di bawah teks "Flight Date / Cycle"
    fig.update_layout(
        title=dict(text=f"<b>Condition-Corrected Parameter Shift | Powerplant {engine_name}</b> ({len(df_engine)} Cycles Recorded)", font=dict(color=NAVY, size=14)),
        xaxis_title="Flight Date / Cycle", 
        yaxis_title="Residual Delta from Baseline", 
        hovermode="x unified", 
        template="plotly_white", 
        height=520,  # Ditambahkan sedikit dari 480 ke 520 agar area grafik tetap luas
        legend=dict(
            orientation="h", 
            yanchor="top", 
            y=-0.28,  # [SOLUSI] Diturunkan ke -0.28 agar bebas total dari judul sumbu X
            xanchor="center", 
            x=0.5, 
            font=dict(size=10, color="#0F172A", weight="bold"),
            bgcolor="rgba(255, 255, 255, 0.95)",
            bordercolor="#CBD5E1",
            borderwidth=1
        ), 
        paper_bgcolor="rgba(0,0,0,0)", 
        plot_bgcolor="rgba(248,250,252,1)", 
        margin=dict(l=40, r=20, t=65, b=140), # [SOLUSI] Margin bawah 140px memberi ruang eksklusif untuk 3 baris legenda
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

def make_t5_gauge_chart(d_t5: float, health_level: EngineHealth) -> go.Figure:
    # Menentukan warna jarum/bar spidometer berdasarkan level kesehatan mesin
    bar_color = "#DC2626" if health_level == EngineHealth.CRITICAL else ("#D97706" if health_level == EngineHealth.ADVISORY else ("#64748B" if health_level == EngineHealth.LOW_CONFIDENCE else "#16A34A"))
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=d_t5,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={
            'text': "<b>Δ T5 Residual to Borescope Limit</b><br><span style='color:#64748B; font-size:0.75rem;'>Max OEM Limit: +15.0 °C</span>", 
            'font': {'size': 12, 'color': NAVY}
        },
        delta={
            'reference': T5_BORESCOPE_C, 
            'increasing': {'color': "#DC2626"}, 
            'decreasing': {'color': "#16A34A"}, 
            'suffix': " °C to Limit"
        },
        number={'suffix': " °C", 'font': {'size': 22, 'color': SLATE_DARK, 'weight': "bold"}},
        gauge={
            'axis': {'range': [-5, 20], 'tickwidth': 1, 'tickcolor': SLATE_MUTED, 'dtick': 5, 'tickfont': {'size': 10}},
            'bar': {'color': bar_color, 'thickness': 0.3},
            'bgcolor': "#FFFFFF",
            'borderwidth': 1,
            'bordercolor': "#CBD5E1",
            'steps': [
                {'range': [-5, T5_WASH_C], 'color': "rgba(22, 163, 74, 0.12)"},       # Zona Hijau (Normal)
                {'range': [T5_WASH_C, T5_BORESCOPE_C], 'color': "rgba(217, 119, 6, 0.18)"},  # Zona Kuning (Wash Limit)
                {'range': [T5_BORESCOPE_C, 20], 'color': "rgba(220, 38, 38, 0.22)"}        # Zona Merah (Borescope Breach)
            ],
            'threshold': {
                'line': {'color': "#991B1B", 'width': 3},
                'thickness': 0.8,
                'value': T5_BORESCOPE_C
            }
        }
    ))
    
    # [KUNCI STATIS] dragmode=False agar spidometer tidak rusak saat di-drag audiens
    fig.update_layout(
        height=210,
        margin=dict(l=15, r=15, t=45, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        dragmode=False
    )
    return fig

# ======================================================================================
# 11. AUTOMATED EMAIL TRANSMITTAL PROTOCOL & NATIVE PDF EWO GENERATOR
# ======================================================================================
from email.mime.application import MIMEApplication

def send_engineering_notice(engine_id: str, status_dict: dict, report_body: str, recipients: list, is_automated: bool = False, recommendations: list = None, alert_key: str = None):
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
            st.toast(f"AUTOMATED ALERT FIRED: Powerplant {engine_id} breached CRITICAL limit.", icon="🚨")
            st.sidebar.error(f"AUTOMATED NOTICE TRANSMITTED\nTarget: {recipients[0] if recipients else 'N/A'}\nEngine: {engine_id} ({status_label})")
        else:
            st.info(f"[SYSTEM SIMULATION MODE - {trigger_type}] SMTP secrets not configured. Notice simulated for {engine_id} to: {', '.join(recipients)}.")
        return True

    if health == EngineHealth.CRITICAL:
        intro_text = (f"ECTM CRITICAL ALERT: An abnormal thermodynamic parameter shift (CRITICAL BREACH) has been confirmed on Powerplant {engine_id}.\n"
                      f"Trigger Source: {trigger_type}\n"
                      "Please review the powerplant condition and the applicable OEM FIM directives below:")
        subject_prefix = "[ECTM - CRITICAL]"
        header_bg = "#DC2626"
    elif health == EngineHealth.ADVISORY:
        intro_text = (f"ECTM ADVISORY: A statistical baseline deviation has been detected on Powerplant {engine_id}.\n"
                      f"Trigger Source: {trigger_type}\n"
                      "Please review the computed residuals and increase telemetry logging frequency:")
        subject_prefix = "[ECTM - ADVISORY]"
        header_bg = "#D97706"
    else:
        intro_text = (f"ROUTINE EVALUATION: Powerplant {engine_id} is operating within normal OEM thermodynamic tolerances.\n"
                      f"Trigger Source: {trigger_type}\n"
                      "Please find the routine condition logging evaluation below:")
        subject_prefix = "[ROUTINE - NORMAL]"
        header_bg = "#16A34A"

    # --- [POIN 7 FIX: EWO PDF Attachment Generation & Dynamic Body Text] ---
    pdf_bytes = None
    try:
        pdf_bytes = generate_ewo_pdf(engine_id, status_label, status_dict, recommendations if recommendations else [])
    except Exception as pdf_err:
        print(f"[PDF GEN ERROR] {engine_id}: {pdf_err}")

    if pdf_bytes:
        pdf_notice_plain = "Notice: A formal signed PDF Engineering Work Order (EWO) is attached to this email."
        pdf_notice_html = """
        <div style="background-color: #EFF4FA; border: 1px solid #CBD5E1; border-radius: 6px; padding: 12px 16px; margin-top: 24px;">
            <p style="margin: 0; color: #003B6F; font-size: 12px; font-weight: bold;">[NOTICE] Formal Engineering Work Order (EWO) Attached</p>
            <p style="margin: 4px 0 0 0; color: #475569; font-size: 12px;">A print-ready PDF document containing exact maintenance directives and sign-off blocks has been generated and attached to this email for immediate hangar distribution.</p>
        </div>"""
    else:
        pdf_notice_plain = "Notice: PDF EWO document generation was bypassed or unavailable. Please review line directives above."
        pdf_notice_html = """
        <div style="background-color: #FFFBEB; border: 1px solid #FCD34D; border-radius: 6px; padding: 12px 16px; margin-top: 24px;">
            <p style="margin: 0; color: #92400E; font-size: 12px; font-weight: bold;">[NOTICE] EWO PDF Attachment Omitted</p>
            <p style="margin: 4px 0 0 0; color: #78350F; font-size: 12px;">PDF EWO attachment was unavailable during dispatch. Please refer directly to the HTML maintenance directives above.</p>
        </div>"""

    msg = MIMEMultipart("mixed")
    msg['From'] = f"AIRFAST ECTM Automated System <{sender_email}>"
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = f"{subject_prefix} ECTM Alert: Powerplant {engine_id} Status Report"
    
    body_part = MIMEMultipart("alternative")
    
    email_plain = (
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
        f"{pdf_notice_plain}\n"
        f"Automated transmission from AIRFAST ECTM Technical Services System."
    )
    body_part.attach(MIMEText(email_plain, 'plain'))
    
    recs_html = ""
    if recommendations:
        for r in recommendations:
            clean_body = r['body'].replace('\n', '<br>').replace('**', '')
            recs_html += f"""
            <div style="background-color: #F8FAFC; border-left: 4px solid {header_bg}; padding: 12px 16px; margin-bottom: 12px; border-radius: 0 6px 6px 0; border-top: 1px solid #E2E8F0; border-right: 1px solid #E2E8F0; border-bottom: 1px solid #E2E8F0;">
                <p style="margin: 0 0 6px 0; color: #00284D; font-weight: bold; font-size: 14px;">[{r['fim_ref']}] {r['title']}</p>
                <p style="margin: 0 0 8px 0; color: #64748B; font-size: 12px;">Priority: <b>{r.get('priority', 'ROUTINE')}</b> | Est. Downtime: <b>{r.get('downtime', 'N/A')}</b></p>
                <p style="margin: 0; color: #334155; font-size: 13px; line-height: 1.5;">{clean_body}</p>
            </div>
            """
    else:
        report_body_html = report_body.replace('\n', '<br>')
        recs_html = f"<p style='color: #475569; font-size: 13px;'>{report_body_html}</p>"

    intro_html = intro_text.replace('\n', '<br>')
    email_html = f"""
    <html>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #F1F5F9; margin: 0; padding: 20px;">
        <div style="max-width: 650px; margin: 0 auto; background-color: #FFFFFF; border-radius: 8px; overflow: hidden; border: 1px solid #CBD5E1; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <div style="background-color: #003B6F; padding: 18px 22px; text-align: left; border-bottom: 4px solid #f0b73d;">
                <table style="width: 100%; border-collapse: collapse; border: none;">
                    <tr>
                        <td style="width: 70px; padding-right: 16px; vertical-align: middle;">
                            <!-- Bantalan putih (background #FFFFFF) memastikan logo tetap kontras dan jelas di atas warna Airfast Navy -->
                            <img src="cid:airfast_logo_cid" alt="AIRFAST Logo" style="width: 65px; height: auto; display: block; border-radius: 6px; background-color: #FFFFFF; padding: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                        </td>
                        <td style="vertical-align: middle;">
                            <h2 style="margin: 0; color: #FFFFFF; font-size: 18px; font-weight: 800; letter-spacing: 0.5px;">PT. AIRFAST INDONESIA</h2>
                            <p style="margin: 2px 0 0 0; color: #f0b73d; font-size: 12px; font-weight: 700; letter-spacing: 0.5px;">TECHNICAL SERVICES DIVISION</p>
                            <p style="margin: 2px 0 0 0; color: #94A3B8; font-size: 11px; font-weight: 600; text-transform: uppercase;">Engine Condition Trend Monitoring Transmittal</p>
                        </td>
                    </tr>
                </table>
            </div>
            
            <div style="padding: 24px;">
                <!-- [FIX: STRUKTUR TABEL ANTI-NEMPEL UNTUK ID MESIN & BADGE STATUS] -->
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    <tr>
                        <td style="text-align: left; vertical-align: middle; padding-bottom: 15px; padding-right: 20px; border-bottom: 1px solid #E2E8F0;">
                            <span style="font-size: 11px; color: #64748B; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 2px;">Powerplant Position</span>
                            <span style="font-size: 16px; color: #0F172A; font-weight: 800; display: block;">{engine_id}</span>
                        </td>
                        <td style="text-align: right; vertical-align: middle; padding-bottom: 15px; border-bottom: 1px solid #E2E8F0; width: 170px; white-space: nowrap;">
                            <span style="background-color: {header_bg}; color: #FFFFFF; padding: 6px 14px; border-radius: 4px; font-size: 11px; font-weight: 800; letter-spacing: 0.5px; text-transform: uppercase; display: inline-block; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">{status_label}</span>
                        </td>
                    </tr>
                </table>
                
                <p style="color: #334155; font-size: 14px; line-height: 1.6; margin-top: 5px;">{intro_html}</p>
                
                <h4 style="color: #003B6F; font-size: 14px; margin: 20px 0 10px 0; text-transform: uppercase; border-bottom: 2px solid #003B6F; padding-bottom: 4px;">Thermodynamic Residual Vector</h4>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 13px;">
                    <tr style="background-color: #F8FAFC; text-align: left;">
                        <th style="padding: 10px; border: 1px solid #E2E8F0; color: #475569;">Parameter</th>
                        <th style="padding: 10px; border: 1px solid #E2E8F0; color: #475569;">Residual Delta</th>
                        <th style="padding: 10px; border: 1px solid #E2E8F0; color: #475569;">OEM Limit / Status</th>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #E2E8F0; font-weight: bold; color: #0F172A;">Delta T5 (ITT)</td>
                        <td style="padding: 10px; border: 1px solid #E2E8F0; font-weight: bold; color: {'#DC2626' if status_dict['alarm_borescope_t5'] else '#0F172A'};">{status_dict['d_t5']:+.1f} &deg;C</td>
                        <td style="padding: 10px; border: 1px solid #E2E8F0; color: #64748B;">Max +15.0 &deg;C (Borescope)</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #E2E8F0; font-weight: bold; color: #0F172A;">Delta Ng (Gas Gen)</td>
                        <td style="padding: 10px; border: 1px solid #E2E8F0; font-weight: bold; color: {'#DC2626' if status_dict['alarm_borescope_ng'] else '#0F172A'};">{status_dict['d_ng']:+.2f} %</td>
                        <td style="padding: 10px; border: 1px solid #E2E8F0; color: #64748B;">Min -1.0% to -1.5%</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #E2E8F0; font-weight: bold; color: #0F172A;">Delta Wf (Fuel Flow)</td>
                        <td style="padding: 10px; border: 1px solid #E2E8F0; font-weight: bold; color: #0F172A;">{status_dict['d_wf']:+.1f} PPH</td>
                        <td style="padding: 10px; border: 1px solid #E2E8F0; color: #64748B;">Statistical Baseline Band</td>
                    </tr>
                </table>
                
                <h4 style="color: #003B6F; font-size: 14px; margin: 20px 0 10px 0; text-transform: uppercase; border-bottom: 2px solid #003B6F; padding-bottom: 4px;">Line Maintenance Directives</h4>
                {recs_html}
                
                {pdf_notice_html}
            </div>
            
            <div style="background-color: #F8FAFC; padding: 15px 24px; border-top: 1px solid #E2E8F0; text-align: center; font-size: 11px; color: #64748B;">
                <p style="margin: 0;">Transmitted via AIRFAST ECTM Watchdog | Evaluated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p style="margin: 4px 0 0 0;">Do not reply directly to this system transmission address.</p>
            </div>
        </div>
    </body>
    </html>
    """
    body_part.attach(MIMEText(email_html, 'html'))

    # [BUG FIX] Was: msg.attach(body_part) directly, with the CID logo
    # attached separately as a sibling of body_part under multipart/mixed.
    # cid: references inside HTML need their image to live in the SAME
    # multipart/related container as the HTML for reliable inline rendering
    # - a flat mixed structure works in lenient clients (Gmail) but risks a
    # broken image icon or a duplicated visible attachment in stricter ones
    # (notably Outlook desktop, which many corporate MCC recipients use).
    related_part = MIMEMultipart("related")
    related_part.attach(body_part)

    logo_file_path = "images.png"  # Menggunakan file logo yang sama dengan sidebar login
    if os.path.exists(logo_file_path):
        try:
            with open(logo_file_path, "rb") as f_img:
                logo_part = MIMEImage(f_img.read())
                # Menetapakan Content-ID agar bisa dipanggil oleh <img src="cid:airfast_logo_cid"> di HTML
                logo_part.add_header('Content-ID', '<airfast_logo_cid>')
                logo_part.add_header('Content-Disposition', 'inline', filename="airfast_logo.png")
                related_part.attach(logo_part)
        except Exception as img_err:
            print(f"[EMAIL LOGO WARNING] Gagal menyisipkan logo CID: {img_err}")

    msg.attach(related_part)
    
    if pdf_bytes:
        pdf_part = MIMEApplication(pdf_bytes, _subtype="pdf")
        filename = f"AIRFAST_EWO_{status_dict.get('reg_prefix', 'ENG')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        pdf_part.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(pdf_part)

    # --- [POIN 1 & 6 FIX: Preserved Error Details & Reduced Timeout] ---
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=5) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        if is_automated:
            st.toast(f"AUTOMATED NOTICE TRANSMITTED: Critical alert for {engine_id} delivered to {recipients[0] if recipients else 'MCC'}.", icon="✅")
        return True
    except Exception as ssl_err:
        try:
            with smtplib.SMTP(smtp_server, 587, timeout=5) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            if is_automated:
                st.toast(f"AUTOMATED NOTICE TRANSMITTED: Critical alert for {engine_id} delivered to {recipients[0] if recipients else 'MCC'}.", icon="✅")
            return True
        except Exception as tls_err:
            # Preserved detail error asli untuk console & UI
            err_detail = f"SSL: {type(ssl_err).__name__}: {ssl_err} | TLS: {type(tls_err).__name__}: {tls_err}"
            print(f"[SMTP FAILURE] {engine_id}: {err_detail}")
            save_to_pending_queue(engine_id, status_dict, report_body, recipients, recommendations, alert_key=alert_key)
            
            # [POIN 2 FIX: Visual Feedback di UI untuk Jalur Otomatis]
            if is_automated:
                st.toast(f"⚠️ SMTP Failure for {engine_id}. Alert saved to Offline Queue.", icon="⚠️")
                st.sidebar.warning(f"WATCHDOG SMTP QUEUED: {engine_id}\nDetail: {type(tls_err).__name__}")
            else:
                st.warning(f"SMTP Transmittal Failed for **{engine_id}**. Details: `{err_detail}`. Notice preserved in Pending Transmittal Queue.")
            return False

# --- [PERSISTENT DISK LEDGER / ANTI-SPAM ENGINE] ---
LEDGER_FILE_PATH = os.path.join(".streamlit_cache", "alert_dispatch_ledger.json")

def load_alert_ledger() -> dict:
    if not os.path.exists(LEDGER_FILE_PATH):
        return {}
    try:
        with open(LEDGER_FILE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_alert_to_ledger(alert_key: str, engine_id: str, flight_date: str, recipients: list):
    os.makedirs(os.path.dirname(LEDGER_FILE_PATH), exist_ok=True)
    ledger = load_alert_ledger()
    ledger[alert_key] = {
        "dispatch_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "engine_id": engine_id,
        "flight_date": flight_date,
        "recipients": recipients
    }
    try:
        with open(LEDGER_FILE_PATH, "w") as f:
            json.dump(ledger, f, indent=4)
    except Exception as e:
        print(f"Failed to save alert ledger: {e}")

def is_alert_already_sent(alert_key: str) -> bool:
    ledger = load_alert_ledger()
    return alert_key in ledger
# ---------------------------------------------------

# --- [PENDING TRANSMITTAL QUEUE / FAILOVER ENGINE] ---
QUEUE_FILE_PATH = os.path.join(".streamlit_cache", "pending_transmittal_queue.json")

def load_pending_queue() -> dict:
    if not os.path.exists(QUEUE_FILE_PATH):
        return {}
    try:
        with open(QUEUE_FILE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_to_pending_queue(engine_id: str, status_dict: dict, report_body: str, recipients: list, recommendations: list = None, alert_key: str = None):
    os.makedirs(os.path.dirname(QUEUE_FILE_PATH), exist_ok=True)
    queue = load_pending_queue()
    queue_key = f"{engine_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # [BUG FIX] flight_date and alert_key were previously not preserved here,
    # so retry_pending_queue() had no way to register a successful retry in
    # the dedup ledger - meaning a retried alert could be sent AGAIN by a
    # later watchdog scan for the same underlying finding. alert_key is only
    # set for watchdog-originated sends (see execute_silent_watchdog); manual
    # ad-hoc dispatches from the Recommendations page intentionally pass
    # alert_key=None, since a human resend shouldn't be ledger-gated.
    flight_date_str = None
    try:
        latest_row = status_dict.get("latest")
        if latest_row is not None and pd.notnull(latest_row.get("Date")):
            flight_date_str = pd.to_datetime(latest_row["Date"]).strftime("%Y-%m-%d")
    except Exception:
        flight_date_str = None

    # Sanitasi status_dict agar 100% aman diserialisasi ke JSON (mencegah crash akibat Enum/Timestamp)
    safe_status = {
        "health_level": status_dict["health_level"].name if hasattr(status_dict["health_level"], "name") else str(status_dict["health_level"]),
        "status_label": str(status_dict.get("status_label", "UNKNOWN")),
        "d_t5": float(status_dict.get("d_t5", 0.0)),
        "d_ng": float(status_dict.get("d_ng", 0.0)),
        "d_wf": float(status_dict.get("d_wf", 0.0)),
        "alarm_borescope_t5": bool(status_dict.get("alarm_borescope_t5", False)),
        "alarm_borescope_ng": bool(status_dict.get("alarm_borescope_ng", False)),
        "reg_prefix": str(status_dict.get("reg_prefix", "ENG"))
    }
    
    queue[queue_key] = {
        "failed_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "engine_id": engine_id,
        "status_dict": safe_status,
        "report_body": report_body,
        "recipients": recipients,
        "recommendations": recommendations if recommendations else [],
        "alert_key": alert_key,
        "flight_date": flight_date_str
    }
    try:
        with open(QUEUE_FILE_PATH, "w") as f:
            json.dump(queue, f, indent=4)
    except Exception as e:
        print(f"Failed to save pending queue: {e}")

def remove_from_pending_queue(queue_key: str):
    queue = load_pending_queue()
    if queue_key in queue:
        del queue[queue_key]
        try:
            with open(QUEUE_FILE_PATH, "w") as f:
                json.dump(queue, f, indent=4)
        except Exception as e:
            print(f"Failed to remove from queue: {e}")

def retry_pending_queue() -> tuple:
    queue = load_pending_queue()
    if not queue:
        return 0, 0
    success_count = 0
    fail_count = 0
    for key, item in list(queue.items()):
        safe_status = item["status_dict"]
        # Rekonstruksi tipe Enum EngineHealth untuk pemanggilan ulang
        h_str = safe_status.get("health_level", "NORMAL")
        if "CRITICAL" in h_str:
            safe_status["health_level"] = EngineHealth.CRITICAL
        elif "ADVISORY" in h_str:
            safe_status["health_level"] = EngineHealth.ADVISORY
        else:
            safe_status["health_level"] = EngineHealth.NORMAL
        
        is_sent = send_engineering_notice(
            engine_id=item["engine_id"],
            status_dict=safe_status,
            report_body=item["report_body"],
            recipients=item["recipients"],
            is_automated=False,
            recommendations=item.get("recommendations", [])
        )
        if is_sent:
            remove_from_pending_queue(key)
            success_count += 1
            # [BUG FIX] Previously a successful retry was never registered in
            # the dedup ledger, so a later watchdog scan for the same
            # underlying CRITICAL finding could send a duplicate alert. Only
            # register when alert_key was actually set (watchdog-originated
            # sends) - manual ad-hoc dispatches intentionally stay ungated.
            if item.get("alert_key"):
                save_alert_to_ledger(
                    item["alert_key"], item["engine_id"],
                    item.get("flight_date", "N/A"), item["recipients"]
                )
        else:
            fail_count += 1
    return success_count, fail_count
# -----------------------------------------------------
   
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

# --- [SILENT BACKGROUND WATCHDOG TRIGGER ENGINE] ---
def execute_silent_watchdog(engines_to_scan: list = None, custom_recipients: list = None, is_manual_trigger: bool = False):
    fresh_df = st.session_state["df_data"].copy()
    fresh_util = st.session_state["df_util"].copy()
    base_n = int(st.session_state.get("target_baseline_n", 6))
    use_corr = bool(st.session_state.get("target_use_correction", True))

    # --- FIX: Paksa konversi ke angka agar Watchdog tidak mencoba menghitung teks ---
    cols_to_numeric = ["T5", "Ng", "Wf", "IOAT", "Press_Alt", "TQ", "Np", "Oil_Temp", "Oil_Press"]
    for col in cols_to_numeric:
        if col in fresh_df.columns:
            if fresh_df[col].dtype == object:
                fresh_df[col] = fresh_df[col].astype(str).str.replace(",", ".", regex=False)
            fresh_df[col] = pd.to_numeric(fresh_df[col], errors="coerce")
    # --------------------------------------------------------------------------------

    fresh_df["Date"] = safe_parse_dates(fresh_df["Date"])
    fresh_df = fresh_df.dropna(subset=REQUIRED_COLUMNS).sort_values("Date")
    
    recipients = custom_recipients
    if not recipients:
        try:
            sec_recs = st.secrets["email"].get("mcc_recipients")
            if sec_recs:
                recipients = sec_recs if isinstance(sec_recs, list) else [r.strip() for r in str(sec_recs).split(",") if r.strip()]
        except Exception:
            pass
    if not recipients:
        ui_recs = [r.strip() for r in st.session_state.get("watchdog_recipient", "").split(",") if r.strip()]
        recipients = ui_recs if ui_recs else []

    if not recipients:
        if is_manual_trigger:
            st.sidebar.error("Transmittal aborted: No recipient email address provided.")
        return 0, 0, 0

    scan_list = engines_to_scan if engines_to_scan else sorted(fresh_df["Engine"].dropna().unique().tolist())
    n_crit = 0
    n_sent = 0
    n_already_sent = 0

    for eng_id in scan_list:
        df_check = fresh_df[fresh_df["Engine"] == eng_id].copy()
        if len(df_check) >= 2:
            df_check_proc = compute_engine_trend(df_check, use_corr)
            st_check = build_status(df_check_proc, fresh_util)
            
            if st_check["health_level"] == EngineHealth.CRITICAL:
                n_crit += 1
                flight_dt_str = st_check['latest']['Date'].strftime('%Y-%m-%d')
                
                # [POIN 10 FIX: Key menyertakan level kesehatan agar aman dari revisi data]
                alert_key = f"{eng_id}_{st_check['latest']['Date'].strftime('%Y%m%d')}_{st_check['health_level'].name}"
                
                if not is_alert_already_sent(alert_key):
                    recs_check = generate_recommendations(df_check_proc, st_check)
                    trigger_lbl = "FLEET WATCHDOG MANUAL SCAN" if is_manual_trigger else "SILENT BACKGROUND WATCHDOG"
                    auto_report_lines = [
                        f"CRITICAL THERMODYNAMIC DEGRADATION DETECTED BY {trigger_lbl}",
                        f"Latest Logbook Timestamp : {flight_dt_str}",
                        f"Computed Residual Vector  : \u0394T5 = {st_check['d_t5']:+.1f} \u00b0C | \u0394Ng = {st_check['d_ng']:+.2f} % | \u0394Wf = {st_check['d_wf']:+.1f} PPH",
                        f"Predictive RUL Remaining  : {st_check['rul_cycles']} Flight Cycles ({st_check['proj_date']})",
                        f"RUL Confidence            : {st_check['rul_confidence']}",
                        "-------------------------------------------------------------------------",
                        "IMMEDIATE MAINTENANCE DIRECTIVES REQUIRED:",
                    ]
                    for rc in recs_check:
                        auto_report_lines.extend([
                            f"[{rc['fim_ref']}] {rc['title']}",
                            f">> Priority: {rc.get('priority', 'ROUTINE')} | Est. Downtime: {rc.get('downtime', 'N/A')}",
                            f">> Thermodynamic Signature: {rc.get('signature', 'N/A')}",
                            rc['body'], ""
                        ])
                    
                    is_delivered = send_engineering_notice(
                        engine_id=eng_id, status_dict=st_check,
                        report_body="\n".join(auto_report_lines),
                        recipients=recipients, is_automated=not is_manual_trigger, recommendations=recs_check,
                        alert_key=alert_key
                    )
                    if is_delivered:
                        save_alert_to_ledger(alert_key, eng_id, flight_dt_str, recipients)
                        n_sent += 1
                else:
                    n_already_sent += 1
                    print(f"[SILENT BYPASS] Alert for {alert_key} was already transmitted previously.")
                    
    return n_crit, n_sent, n_already_sent
# -------------------------------------------------------------------

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
    st.session_state["active_menu"] = "Overview"
    st.rerun()

st.sidebar.markdown("---")

all_menus = [
    "Overview", 
    "Data Collection", 
    "Data Analysis", 
    "Logbook", 
    "Recommendations"
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
    "Also runs automatically after a new logbook entry or CSV upload. This button "
    "triggers an additional full-fleet scan on demand. Deduplication is persisted "
    "to disk (alert_dispatch_ledger.json) - the same engine + date + status "
    "combination will not be re-alerted even across browser sessions or app restarts."
)
watchdog_recipient_input = st.sidebar.text_input(
    "Alert recipient email(s)", value=st.session_state.get("watchdog_recipient", ""),
    placeholder="engineering@airfastindonesia.com", key="watchdog_recipient",
    help="Comma-separate multiple addresses. Nothing is sent until you click the button below.",
)
run_watchdog_now = st.sidebar.button("Run Fleet Health Scan Now", key="btn_run_watchdog", use_container_width=True)

st.sidebar.markdown("<br>" * 2, unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style='font-size:0.75rem; line-height:1.5; color:#94A3B8; font-weight:400;'>
    <b style='color:#FFFFFF; font-weight:600;'>PT. AIRFAST Indonesia</b><br>
    Jl. Marsekal Suryadarma No.8<br>Neglasari, Tangerang, Banten 15129<br>
    <span style='font-size:0.7rem; color:#64748B;'>Technical Service Division</span><br>
    <span style='font-size:0.72rem; color:#f0b73d; font-weight:700; letter-spacing:0.05em;'>SYSTEM RELEASE v2.0 (2ND EDITION)</span>
</div>
""", unsafe_allow_html=True)

# ======================================================================================
# 13. GLOBAL DATA PROCESSING & PERSISTENT STATE SYNC
# ======================================================================================
df_raw = st.session_state["df_data"].copy()
df_util_current = st.session_state["df_util"].copy()
df_rep_current = st.session_state["df_rep"].copy()

# [ENTERPRISE FIX] Pastikan kolom kalender dari CSV dibaca kembali sebagai objek Datetime
if not df_util_current.empty and "Work (Date)" in df_util_current.columns:
    df_util_current["Work (Date)"] = safe_parse_dates(df_util_current["Work (Date)"])
if not df_rep_current.empty and "Date" in df_rep_current.columns:
    df_rep_current["Date"] = safe_parse_dates(df_rep_current["Date"])

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
# [BUG FIX] The original fallback was f"AML-{date}" - date only, with no
# aircraft identity. Since the SSOT correlator (Logbook & Defect Correlator
# page) does an EXACT match on "AML No" across all 3 datasets, two different
# aircraft/engines with telemetry logged on the same calendar date would get
# an IDENTICAL fallback key - causing PK-OAM's row to silently pull in
# PK-OCH's utilization/defect data (or vice versa) whenever this fallback
# path is used. This is not a rare edge case: it fires for any legacy CSV
# without the new "AML No" column, and for any manual-entry row where the
# AML field is left blank (both very likely in normal daily use). Fix:
# include the registration/engine identity in the fallback key so it stays
# unique per aircraft, not just per date.
# --- KODE BARU (Pengaman Sel Kosong / NaN & Type Guard) ---
def _build_fallback_aml(reg_series: pd.Series, date_series: pd.Series) -> pd.Series:
    """[BUG FIX] Previously built via Series "+" concatenation, which
    crashed in production with TypeError on Streamlit Cloud's Python 3.14
    + newest pandas: that environment defaults string columns to
    PyArrow-backed dtype, and its "+"/"__radd__" operator overloads raised
    inside pyarrow's operator dispatch when mixed with plain Python string
    literals in this exact pattern. .astype(str) alone was not a reliable
    fix, since pandas 3.x can map .astype(str) to the same arrow-backed
    dtype rather than legacy object dtype. Building the value with plain
    Python f-strings row-by-row sidesteps pandas/pyarrow operator dispatch
    entirely, so it is correct regardless of which string dtype a given
    pandas version defaults to."""
    dates_fmt = pd.to_datetime(date_series, errors="coerce")
    return pd.Series(
        [
            f"AML-{reg if pd.notnull(reg) and str(reg).strip() else 'UNKN'}-"
            f"{d.strftime('%Y%m%d') if pd.notnull(d) else 'UNKN'}"
            for reg, d in zip(reg_series, dates_fmt)
        ],
        index=reg_series.index,
    )

if "AML No" not in df_raw.columns:
    _fallback_reg = df_raw["Engine"].astype(str).str.split("|").str[0].str.strip()
    df_raw["AML No"] = _build_fallback_aml(_fallback_reg, df_raw["Date"])
else:
    # Jika kolom AML No sudah ada, isi sel yang kosong/NaN dengan fallback ID otomatis
    _fallback_reg = df_raw["Engine"].astype(str).str.split("|").str[0].str.strip()
    _fallback_key = _build_fallback_aml(_fallback_reg, df_raw["Date"])
    df_raw["AML No"] = df_raw["AML No"].replace(["", "NAN", "nan", "None"], np.nan).fillna(_fallback_key)
    
if "AML No" not in df_util_current.columns and not df_util_current.empty:
    _fallback_reg_u = df_util_current["Registration"].astype(str) if "Registration" in df_util_current.columns else pd.Series("UNKN", index=df_util_current.index)
    df_util_current["AML No"] = _build_fallback_aml(_fallback_reg_u, df_util_current.get("Work (Date)"))
    
if "AML No" in df_raw.columns:
    df_raw["AML No"] = df_raw["AML No"].astype(str).str.strip().str.upper()
if "AML No" in df_util_current.columns and not df_util_current.empty:
    df_util_current["AML No"] = df_util_current["AML No"].astype(str).str.strip().str.upper()
if "AML No" in df_rep_current.columns and not df_rep_current.empty:
    df_rep_current["AML No"] = df_rep_current["AML No"].astype(str).str.strip().str.upper()

_rows_before_clean = len(df_raw)
df_raw = df_raw.dropna(subset=REQUIRED_COLUMNS).sort_values("Date")
_rows_dropped = _rows_before_clean - len(df_raw)
if _rows_dropped > 0:
    st.sidebar.warning(
        f"{_rows_dropped} logbook row(s) ignored - invalid or missing "
        f"Date/{'/'.join(REQUIRED_COLUMNS[2:])} values. Check Data Collection & Setup."
    )

engines_available = sorted(df_raw["Engine"].dropna().unique().tolist())

# [ENTERPRISE FIX] Cegah Deadlock UI jika database benar-benar kosong
if not engines_available:
    engines_available = ["NO DATA"]
    if menu_selection != "Data Collection":
        st.warning("⚠️ **Database Telemetri Kosong.** Silakan buka menu **Data Collection** di samping dan klik tombol biru 'Sync All Fleet Data' atau lakukan input manual.")
        st.stop()

if st.session_state["target_engine"] not in engines_available:
    st.session_state["target_engine"] = engines_available[0]

selected_engine = st.session_state["target_engine"]
use_correction = st.session_state["target_use_correction"]
baseline_n_input = st.session_state.get("target_baseline_n", 6)

# ======================================================================================
# LLP PARALLEL DATA LAYER
# IMPORTANT: LLP never modifies ECTM health classification, confidence, baseline or RUL.
# ======================================================================================
@st.cache_data(show_spinner=False)
def _load_llp_cached(path_str: str, mtime_ns: int):
    return load_llp_workbook(path_str)

_llp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), LLP_DEFAULT_FILENAME)
_llp_mtime_ns = os.stat(_llp_path).st_mtime_ns if os.path.exists(_llp_path) else 0
df_llp_all, llp_meta, llp_issues = _load_llp_cached(_llp_path, _llp_mtime_ns)
df_llp_engine = engine_llp_view(df_llp_all, selected_engine)
llp_report_dates = df_llp_engine["Report Date"].dropna() if not df_llp_engine.empty else pd.Series(dtype="datetime64[ns]")

df_engine = df_raw[df_raw["Engine"] == selected_engine].copy()

# Inisialisasi default aman untuk mencegah error saat kosong
status = {"reg_prefix": "PK-OAM", "status_label": "N/A", "health_level": EngineHealth.NORMAL} 
recommendations = []

if len(df_engine) < 2:
    if menu_selection != "Data Collection":
        st.warning(f"⚠️ Powerplant {selected_engine} memiliki kurang dari 2 data historis. Silakan tambahkan data di menu **Data Collection**.")
        st.stop()
else:
    # Hanya jalankan kalkulasi termodinamika rumit jika datanya ada
    df_engine = compute_engine_trend(df_engine, use_correction)
    status = build_status(df_engine, df_util_current)
    recommendations = generate_recommendations(df_engine, status)

# ======================================================================================
# FLEET WATCHDOG - MANUAL SCAN (SINGLE SOURCE OF TRUTH TRIGGER)
# ======================================================================================
if run_watchdog_now:
    watchdog_recipients = [r.strip() for r in watchdog_recipient_input.split(",") if r.strip()]
    if not watchdog_recipients:
        st.sidebar.error("Enter at least one recipient email before running the scan.")
    else:
        with st.spinner("Executing fleet-wide thermodynamic health scan..."):
            n_crit, n_sent, n_already = execute_silent_watchdog(
                engines_to_scan=engines_available, 
                custom_recipients=watchdog_recipients, 
                is_manual_trigger=True
            )
        if n_crit == 0:
            st.sidebar.success("Fleet scan complete - no engines currently at CRITICAL.")
        elif n_already == n_crit:
            st.sidebar.info(f"Scan complete - {n_crit} CRITICAL engine(s) detected, but all notices were already transmitted previously. No duplicate emails sent.")
        else:
            st.sidebar.success(f"Scan complete - {n_crit} CRITICAL engine(s) processed ({n_sent} new alert(s) dispatched).")

# ======================================================================================
# 14. PAGE 1: HOME (FLEET MATRIX & OCC HEATMAP INTEGRATION)
# ======================================================================================
if menu_selection == "Overview":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Overview</h1>", unsafe_allow_html=True)
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
            df_sub_proc = compute_engine_trend(df_sub, use_correction)
            st_sub = build_status(df_sub_proc, df_util_current)
            stat_lbl = (
                "CRITICAL" if st_sub["health_level"] == EngineHealth.CRITICAL else
                "ADVISORY" if st_sub["health_level"] == EngineHealth.ADVISORY else
                "NORMAL"
            )
            rul_val = st_sub["rul_cycles"]
            accel_marker = " [ACCELERATING]" if st_sub["rul_is_linear_caution"] else ""
            rul_str = (
                "RUL NOT ASSESSED — ECTM CONFIDENCE LOW"
                if st_sub["model_confidence"] != "HIGH"
                else ("Stable (>100 Cycles)" if rul_val >= 999
                      else f"{rul_val} Cycles ({st_sub['proj_date']}){accel_marker}")
            )
            
            fleet_summary_data.append({
                "Powerplant Serial / Position": eng,
                "Status": stat_lbl,
                "ECTM Confidence": ("HIGH" if st_sub["model_confidence"] == "HIGH" else "LOW — LIMITED"),
                "Monitoring Note": (
                    "ECTM reference model applicable."
                    if st_sub["model_confidence"] == "HIGH"
                    else st_sub.get("confidence_reason", "ECTM assessment confidence is limited.")
                ),
                "Latest Δ T5": f"{st_sub['d_t5']:+.1f} °C",
                "T5 Slope": f"{st_sub['slope_t5']:+.2f} °C/cyc",
                "Latest Δ Ng": f"{st_sub['d_ng']:+.2f} %",
                "Predictive RUL (Borescope)": rul_str
            })
            
            reg_id = st_sub["reg_prefix"]
            pos = "LH Engine" if "LH" in eng else "RH Engine"
            if reg_id not in aircraft_map: aircraft_map[reg_id] = {}
            aircraft_map[reg_id][pos] = stat_lbl

    # [UX] Fleet command summary: status first, supporting data second.
    normal_count = sum(1 for item in fleet_summary_data if item["Status"] == "NORMAL")
    advisory_count = sum(1 for item in fleet_summary_data if item["Status"] == "ADVISORY")
    critical_count = sum(1 for item in fleet_summary_data if item["Status"] == "CRITICAL")

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Engines Monitored", len(engines_available))
    k2.metric("NORMAL", normal_count)
    k3.metric("ADVISORY", advisory_count)
    k4.metric("CRITICAL", critical_count)
    k5.metric("PIREP / MAREP", len(df_rep_current) if not df_rep_current.empty else "0")

    _sync_result = st.session_state.get("_auto_sync_last_result", {})
    _sync_files = _sync_result.get("files", 0)
    _sync_label = "Auto-sync active" if _sync_result else "Database loaded"
    st.caption(
        f"Data status: **{_sync_label}** · "
        f"Source workbooks detected: **{_sync_files}** · "
        f"Telemetry records: **{len(df_raw):,}** · "
        f"Utilization records: **{len(df_util_current):,}** · "
        f"LLP coverage: **{df_llp_all['Engine Key'].nunique() if not df_llp_all.empty else 0}/{len(engines_available)} engines**"
    )

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("<h3 style='color:#003B6F; margin-bottom:8px;'>Operation Control Center (OCC) | Fleet Health Map</h3>", unsafe_allow_html=True)
    
    dhc6_svg_blueprint = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 80" width="100%" height="110" style="background: linear-gradient(135deg, #F8FAFC 0%, #EFF4FA 100%); border: 1px solid #CBD5E1; border-radius: 6px; padding: 4px; margin-bottom: 8px;">
<g stroke="#E2E8F0" stroke-width="0.6"><line x1="0" y1="20" x2="320" y2="20"/><line x1="0" y1="40" x2="320" y2="40"/><line x1="0" y1="60" x2="320" y2="60"/><line x1="80" y1="0" x2="80" y2="80"/><line x1="160" y1="0" x2="160" y2="80"/><line x1="240" y1="0" x2="240" y2="80"/></g>
<g fill="#003B6F"><path d="M 40 45 L 60 42 C 80 40, 120 40, 180 40 L 250 38 L 285 22 L 295 22 L 285 42 C 295 44, 298 47, 290 51 L 250 51 L 180 50 L 80 50 C 60 50, 45 49, 40 45 Z"/><path d="M 110 37 L 140 37 L 155 48 L 105 48 Z" fill="#00284D"/><ellipse cx="98" cy="43" rx="3" ry="12" fill="#f0b73d" opacity="0.9"/><line x1="98" y1="28" x2="98" y2="58" stroke="#f0b73d" stroke-width="1.5" stroke-dasharray="2,2"/><path d="M 255 38 L 280 12 L 292 12 L 285 38 Z" fill="#00284D"/></g>
<text x="12" y="18" font-family="'Plus Jakarta Sans', sans-serif" font-size="9" font-weight="800" fill="#003B6F" letter-spacing="1.5">DHC-6 TWIN OTTER</text>
<text x="12" y="30" font-family="'Plus Jakarta Sans', sans-serif" font-size="7.5" font-weight="600" fill="#64748B">TWIN TURBOPROP | P&amp;WC PT6A-34</text>
<circle cx="300" cy="15" r="4" fill="#16A34A"/></svg>"""

    import base64
    # [UI/UX UPGRADE: 5-COLUMN OCC FLEET COMMAND DECK]
    # Menampilkan 5 pesawat DHC-6 AIRFAST sejajar dalam satu baris eksekutif di layar Wide
    hm_cols = st.columns(5)
    col_idx = 0
    for reg, engs in sorted(aircraft_map.items()):
        with hm_cols[col_idx % 5]:
            lh_stat = engs.get("LH Engine", "UNKNOWN")
            rh_stat = engs.get("RH Engine", "UNKNOWN")
            
            def get_hm_class(st_val):
                if st_val == "CRITICAL": return "hm-red"
                if st_val == "ADVISORY": return "hm-amber"
                if st_val == "NORMAL": return "hm-green"
                return "hm-gray"  # Unrecognized health status - fail-safe, not fail-green

            # Sistem otomatis mencari foto pesawat berdasarkan registrasi
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
                visual_html = f'<div style="margin-bottom:8px; border:1px solid #CBD5E1; border-radius:6px; overflow:hidden; width:100%; height:90px; background:#F8FAFC;"><img src="data:{mime_type};base64,{b64_str}" style="width:100%; height:100%; object-fit:cover; object-position:center; display:block;"></div>'
            else:
                visual_html = dhc6_svg_blueprint
                
            card_html = f"""<div class="heatmap-card" style="padding: 10px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
<span class="heatmap-reg" style="margin-bottom:0px; font-size:0.95rem;">{reg}</span>
<span style="background:#EFF4FA; color:#003B6F; font-size:0.65rem; font-weight:700; padding:2px 5px; border-radius:4px; border:1px solid #CBD5E1;">PT6A-34</span>
</div>
{visual_html}
<div class="heatmap-row {get_hm_class(lh_stat)}" style="font-size:0.72rem; padding:4px 6px;">
<span>#1 LH</span><b>{lh_stat}</b>
</div>
<div class="heatmap-row {get_hm_class(rh_stat)}" style="font-size:0.72rem; padding:4px 6px;">
<span>#2 RH</span><b>{rh_stat}</b>
</div>
 </div>
 <div style="margin-top:6px; font-size:0.68rem; color:#64748B; line-height:1.35;">
   {("ECTM assessment limited — see engine detail." if any(
       x["Powerplant Serial / Position"] in [f"{reg} | LH", f"{reg} | RH"]
       and x["ECTM Confidence"] != "HIGH" for x in fleet_summary_data
   ) else "ECTM reference assessment available.")}
 </div>"""
            st.markdown(card_html, unsafe_allow_html=True)
        col_idx += 1

    df_fleet_matrix = pd.DataFrame(fleet_summary_data)

    # 1. Fungsi pewarnaan status
    def highlight_status(val):
        status = str(val).strip().upper()
        if status == 'NORMAL':
            return 'background-color: #d1e7dd; color: #0f5132; font-weight: bold;'
        elif status == 'ADVISORY':
            return 'background-color: #fff3cd; color: #664d03; font-weight: bold;'
        elif status == 'CRITICAL':
            return 'background-color: #f8d7da; color: #842029; font-weight: bold;'
        return ''

    # Main overview table: keep only fast-scan fields.
    overview_cols = [
        "Powerplant Serial / Position", "Status", "ECTM Confidence",
        "Latest Δ T5", "T5 Slope", "Latest Δ Ng", "Predictive RUL (Borescope)"
    ]
    overview_cols = [c for c in overview_cols if c in df_fleet_matrix.columns]
    df_overview = df_fleet_matrix[overview_cols].copy()

    try:
        styled_df = df_overview.style.map(highlight_status, subset=["Status"])
    except AttributeError:
        styled_df = df_overview.style.applymap(highlight_status, subset=["Status"])

    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    limited_df = df_fleet_matrix[
        df_fleet_matrix["ECTM Confidence"].astype(str).str.startswith("LOW")
    ][["Powerplant Serial / Position", "Status", "ECTM Confidence", "Monitoring Note"]].copy()
    if not limited_df.empty:
        with st.expander(f"ECTM Assessment Notes — {len(limited_df)} engine(s) with limited assessment"):
            st.dataframe(limited_df, use_container_width=True, hide_index=True)

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
elif menu_selection == "Data Collection":
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
                    m_date = st.date_input("Flight Date", value=datetime.now().date())
                    m_time = st.time_input("Flight Time (Local)", value=datetime.now().time())
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
                
                if st.form_submit_button("Save Daily Performance Record", type="primary", use_container_width=True):
                    _m_reg_fallback = str(m_eng).split("|")[0].strip()
                    flight_dt = datetime.combine(m_date, m_time) # Gabungkan tanggal & jam untuk presisi MRO
                    new_row = pd.DataFrame([{
                        "AML No": m_aml if m_aml else f"AML-{_m_reg_fallback}-{flight_dt.strftime('%Y%m%d%H%M')}",
                        "Date": flight_dt.strftime('%Y-%m-%d %H:%M:%S'),
                        "Engine": m_eng, "Press_Alt": float(m_alt),
                        "IOAT": float(m_ioat), "IAS": float(m_ias), "TQ": float(m_tq), "Np": int(m_np),
                        "T5": float(m_t5), "Ng": float(m_ng), "Wf": float(m_wf),
                        "Oil_Temp": float(m_otemp), "Oil_Press": float(m_opress)
                    }])
                    
                    # Gabungkan data, hapus duplikat (jika ada input ganda di hari yang sama), dan simpan permanen
                    st.session_state["df_data"] = pd.concat([st.session_state["df_data"], new_row], ignore_index=True)
                    st.session_state["df_data"] = st.session_state["df_data"].drop_duplicates(subset=["Date", "Engine"], keep="last").sort_values("Date")
                    
                    save_ectm_db()
                    execute_silent_watchdog(engines_to_scan=[m_eng]) # Pindai anomali otomatis
                    
                    st.success(f"Successfully logged daily performance telemetry for {m_eng}!")
                    st.rerun()
                    
        st.markdown("<p style='font-size:0.95rem; font-weight:600; color:#003B6F;'>⚡ Server Directory Auto-Sync (Fleet MRO Integration)</p>", unsafe_allow_html=True)
        st.caption("One-click synchronization. The system will automatically scan the local `data/` directory, extract all raw #1 and #2 aircraft engine Excel exports, map thermodynamic parameters, and build the persistent database.")
        
        if st.button("🔄 Sync All Fleet Data from Local Server", type="primary", use_container_width=True):
            with st.spinner("Enterprise Sync: membaca seluruh source workbook..."):
                result = sync_local_fleet_data("data")
            if not result.get("ok"):
                st.error("Directory 'data' tidak ditemukan. Pastikan source workbook tersedia di folder project.")
            else:
                st.success(
                    f"Enterprise Sync Complete — ECTM: {result.get('ectm', 0):,} rows | "
                    f"Utilization: {result.get('util', 0):,} rows | "
                    f"PIREP/MAREP: {result.get('rep', 0):,} rows."
                )
                if result.get("skipped"):
                    st.warning("Sebagian source tidak terbaca: " + " | ".join(result["skipped"][:5]))
                execute_silent_watchdog()
                st.rerun()

        st.session_state["df_data"] = st.data_editor(st.session_state["df_data"], num_rows="dynamic", use_container_width=True)
        if st.button("Save Manual Edits to Database"):
            save_ectm_db()
            st.success("Manual edits saved to database!")

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
                        "AML No": u_aml if u_aml else f"AML-{u_reg}-{pd.to_datetime(u_date).strftime('%Y%m%d')}",
                        "Registration": u_reg, "Work (Date)": pd.to_datetime(u_date),
                        "FH": float(u_fh), "FC": int(u_fc), "Block Hours": float(u_bh),
                        "From": u_from, "To": u_to
                    }])
                    new_u_row["Data_Source"] = "MANUAL"
                    st.session_state["df_util"] = pd.concat([st.session_state["df_util"], new_u_row], ignore_index=True)
                    st.session_state["df_util"] = st.session_state["df_util"].drop_duplicates(
                        subset=["Registration", "Work (Date)", "FH", "FC"], keep="last"
                    )
                    st.session_state["util_is_real"] = True
                    save_util_db()
                    st.success(f"Successfully logged utilization for {u_reg} ({u_fh} FH / {u_fc} FC)!")
                    st.rerun()

        st.caption("Upload Flight Utilization Excel file (e.g., `Flight Utilization DHC6-400.xlsx`) to synchronize RUL calendar projections.")
        up_util = st.file_uploader("Upload Utilization File (.xlsx)", type=["xlsx"], key="up_util_file")
        if up_util is not None:
            df_u_new = pd.read_excel(up_util)
            df_u_new['Work (Date)'] = safe_parse_dates(df_u_new['Work (Date)'])
            df_u_new = df_u_new.dropna(subset=['Registration', 'Work (Date)']).copy()
            df_u_new["Data_Source"] = "UPLOAD"
            cur_u = st.session_state["df_util"].copy()
            if "Data_Source" not in cur_u.columns:
                cur_u["Data_Source"] = "LEGACY_DB"
            st.session_state["df_util"] = pd.concat([cur_u, df_u_new], ignore_index=True).drop_duplicates(
                subset=["Registration", "Work (Date)", "FH", "FC"], keep="last"
            )
            st.session_state["util_is_real"] = not st.session_state["df_util"].empty
            save_util_db()
            st.success("Flight Utilization dataset synchronized and persisted!")
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
                        "AML No": r_aml if r_aml else f"AML-{r_reg}-{pd.to_datetime(r_date).strftime('%Y%m%d')}",
                        "Date": pd.to_datetime(r_date),
                        "Registration": r_reg, "ATA": int(r_ata),
                        "Note / Report": r_note if r_note else "No description provided.",
                        "Corrective Action": r_action if r_action else "Pending action.",
                        "Position": r_pos, "P/N Off": r_pn_off, "S/N Off": r_sn_off,
                        "P/N On": r_pn_on, "S/N On": r_sn_on
                    }])
                    st.session_state["df_rep"] = pd.concat([st.session_state["df_rep"], new_r_row], ignore_index=True)
                    st.session_state["df_rep"] = process_maintenance_reports(st.session_state["df_rep"])
                    st.session_state["df_rep"]["Data_Source"] = st.session_state["df_rep"].get("Data_Source", "LEGACY_DB")
                    st.session_state["df_rep"].loc[st.session_state["df_rep"].index[-1], "Data_Source"] = "MANUAL"
                    st.session_state["rep_is_real"] = True
                    save_rep_db()
                    st.success(f"Successfully logged PIREP / MAREP report [{r_aml}] for {r_reg}!")
                    st.rerun()

        st.caption("Upload PIREP & MAREP Excel file (e.g., `Pilot & Maintenance Report DHC6-400.xlsx`) to power the Defect Correlator.")
        up_rep = st.file_uploader("Upload PIREP / MAREP File (.xlsx)", type=["xlsx"], key="up_rep_file")
        if up_rep is not None:
            df_r_new = process_maintenance_reports(pd.read_excel(up_rep))
            df_r_new["Data_Source"] = "UPLOAD"
            cur_r = st.session_state["df_rep"].copy()
            if "Data_Source" not in cur_r.columns:
                cur_r["Data_Source"] = "LEGACY_DB"
            st.session_state["df_rep"] = process_maintenance_reports(
                pd.concat([cur_r, df_r_new], ignore_index=True).drop_duplicates(
                    subset=["Registration", "Date", "ATA", "Note / Report"], keep="last"
                )
            )
            st.session_state["rep_is_real"] = not st.session_state["df_rep"].empty
            save_rep_db()
            st.success("PIREP / MAREP reports synchronized, merged, and persisted!")
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
            if "ui_sel_corr" in st.session_state: st.session_state["target_use_correction"] = st.session_state["ui_sel_corr"]

        with col_set1:
            curr_idx = engines_available.index(st.session_state["target_engine"]) if st.session_state["target_engine"] in engines_available else 0
            st.selectbox("Target Powerplant (Position)", engines_available, index=curr_idx, key="ui_sel_eng", on_change=sync_config)
        with col_set3:
            st.write("") 
            st.write("")
            st.toggle("Atmospheric & Torque Normalization", value=bool(st.session_state["target_use_correction"]), key="ui_sel_corr", on_change=sync_config)
            
        sync_config()
            
    st.markdown("<br>", unsafe_allow_html=True)
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        st.button("Analyze Data", type="primary", use_container_width=True, on_click=navigate_to_menu, args=("Data Analysis",))

# ======================================================================================
# 16. PAGE 3: TREND ANALYSIS & PREDICTIVE RUL (WITH DYNAMIC TIME SLICER)
# ======================================================================================
elif menu_selection == "Data Analysis":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Engine Detail & Trend Analysis</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>"
        f"Active Powerplant: <b style='color:#003B6F; background:#EFF4FA; padding:2px 8px; "
        f"border-radius:4px; border:1px solid #CBD5E1;'>{selected_engine}</b> "
        f"| Condition-Corrected Residual Assessment</p>",
        unsafe_allow_html=True
    )
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    if df_engine.attrs.get("regression_downgraded", False):
        st.warning("**Mathematical Warning:** Rentang kalibrasi logbook yang diunggah belum memiliki variasi atmosfer (Suhu & Ketinggian) yang memadai untuk regresi termodinamika multivariabel. Kalkulasi sementara diturunkan ke mode *Arithmetic Mean*. Disarankan untuk melakukan 'Auto-Sync' data MRO tambahan agar akurasi prediksi baseline menjadi optimal.")

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
        st.markdown("<h3 style='margin-bottom:6px; color:#003B6F;'>Engine Health Status</h3>", unsafe_allow_html=True)
        if status["health_level"] == EngineHealth.CRITICAL:
            st.markdown("<span class='badge-red'>CRITICAL</span>", unsafe_allow_html=True)
        elif status["health_level"] == EngineHealth.ADVISORY:
            st.markdown("<span class='badge-amber'>ADVISORY</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='badge-green'>NORMAL</span>", unsafe_allow_html=True)

        # Compact "why" summary: explain the classification without replacing the detailed flags below.
        if status["health_level"] == EngineHealth.CRITICAL:
            _why_status = "Persistent ECTM/FIM-level deviation detected."
        elif status["health_level"] == EngineHealth.ADVISORY:
            _why_status = "ECTM monitoring threshold or early-warning condition detected."
        else:
            _why_status = "No valid ECTM Advisory or Critical condition declared."

        st.markdown(
            f"<div style='margin-top:9px;padding:9px 11px;background:#F8FAFC;"
            f"border:1px solid #E2E8F0;border-radius:7px;font-size:0.80rem;color:#475569;'>"
            f"<b style='color:#334155;'>Assessment Summary</b><br>{_why_status}</div>",
            unsafe_allow_html=True
        )

        if status["model_confidence"] != "HIGH":
            reason = status.get("confidence_reason", "ECTM assessment confidence is limited.")
            st.markdown(
                f"<div style='margin-top:8px;padding:9px 12px;border-left:4px solid #D97706;"
                f"background:#FFF7ED;border-radius:0 6px 6px 0;color:#7C2D12;font-size:0.82rem;'>"
                f"<b>ECTM Assessment Limited</b><br>"
                f"<span style='color:#92400E;'>ECTM Confidence: LOW</span><br>"
                f"{reason}<br>"
                f"<span style='color:#64748B;'>This does not indicate an Advisory or Critical engine condition.</span>"
                f"</div>",
                unsafe_allow_html=True
            )

        st.write("")
        
        # --- [V2.0 UPGRADE: RADIAL GAUGE INDICATOR FOR DELTA T5] ---
        st.plotly_chart(make_t5_gauge_chart(status['d_t5'], status['health_level']), use_container_width=True)
        # -----------------------------------------------------------
        
        st.metric("Latest \u0394 T5 Residual", f"{status['d_t5']:+.1f} \u00b0C", delta=f"{status['slope_t5']:+.2f} °C/cyc", delta_color="inverse")
        st.metric("Latest \u0394 Ng Residual", f"{status['d_ng']:+.2f} %", delta=f"{status['slope_ng']:+.3f} %/cyc")
        st.metric("Latest \u0394 Wf Residual", f"{status['d_wf']:+.1f} PPH", delta=f"{status['latest']['Delta_Wf_pct']:+.1f}% shift", delta_color="inverse")

        rul_val = status["rul_cycles"]
        rul_display = (
            "RUL NOT ASSESSED — ECTM CONFIDENCE LOW"
            if status["model_confidence"] != "HIGH"
            else ("Stable (>100 Cycles)" if rul_val >= 999 else f"{rul_val} Flight Cycles")
        )
        date_display = f"Est. Date: {status['proj_date']} ({status['fc_per_day']:.1f} cyc/day)" if rul_val < 999 else "No Intervention Scheduled"
        rul_caution_color = "#B42318" if status["rul_is_linear_caution"] else "#64748B"

        st.markdown(f"""
        <div class="rul-box">
            <div class="rul-title">Remaining Useful Life (RUL)</div>
            <div class="rul-val">{rul_display}</div>
            <div class="rul-sub">{date_display}</div>
            <div class="rul-sub" style="color:{rul_caution_color}; margin-top:4px;">[NOTE] {status['rul_confidence']}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("<h4 style='color:#003B6F; margin-bottom:4px;'>ECTM Diagnostic Flags</h4>", unsafe_allow_html=True)
        st.caption("These flags explain the ECTM assessment and do not replace the Engine Health Status.")
        if status["isolated_t5"] or status["isolated_ng"]: st.write("▪ Isolated single-cycle shift detected")
        if status["sustained_t5"]: st.write("▪ Sustained upward T5 trend detected")
        if status["alarm_wash"]: st.write("▪ ITT +10°C wash limit exceeded")
        if status["alarm_borescope_t5"] or status["alarm_borescope_ng"]: st.write("▪ OEM borescope limit breached")
        if not (status["isolated_t5"] or status["isolated_ng"] or status["sustained_t5"] or status["alarm_wash"] or status["alarm_borescope_t5"] or status["alarm_borescope_ng"]):
            st.write("▪ No active anomalies detected")
            
        st.markdown("---")
        st.button(
            "Cross-Check Logbook Defect Correlator", 
            use_container_width=True,
            on_click=navigate_to_menu,
            args=("Logbook", status["reg_prefix"])
        )

    # ==================================================================================
    # ==================================================================================
    # LLP COMPONENT LIFE — FULL-WIDTH MAINTENANCE PLANNING PANEL
    # ==================================================================================
    st.markdown("---")
    st.markdown(
        "<h3 style='color:#003B6F; margin-bottom:2px;'>LLP Component Life & Maintenance Planning</h3>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Component-life information is shown as a separate maintenance-planning layer. "
        "It does not change the ECTM Engine Health Status."
    )

    if df_llp_engine.empty:
        if llp_meta.get("available", False):
            st.info(
                f"No LLP component records were mapped to **{selected_engine}** in the current workbook."
            )
        else:
            st.info(
                f"LLP source unavailable. Place **{LLP_DEFAULT_FILENAME}** beside the dashboard "
                "to enable component-life monitoring. ECTM analysis remains unaffected."
            )
    else:
        _llp_report_date = (
            llp_report_dates.max().strftime("%d %b %Y")
            if not llp_report_dates.empty else "Not available"
        )
        _llp_overdue = int((df_llp_engine["Life Status"] == "OVERDUE").sum())
        _llp_fh_count = int((df_llp_engine["Basis"].astype(str).str.upper() == "FH").sum())
        _llp_fc_count = int((df_llp_engine["Basis"].astype(str).str.upper() == "FC").sum())

        # Compact planning snapshot. No "due soon" threshold is invented here.
        l1, l2, l3, l4 = st.columns(4)
        l1.metric("LLP Components", len(df_llp_engine))
        l2.metric("Overdue", _llp_overdue)
        l3.metric("FH-Based", _llp_fh_count)
        l4.metric("FC-Based", _llp_fc_count)

        st.caption(
            f"LLP source report date: **{_llp_report_date}** · "
            f"Source workbook: **{llp_meta.get('source_file', LLP_DEFAULT_FILENAME)}**"
        )

        if llp_issues:
            _engine_issues = [
                x for x in llp_issues
                if selected_engine.split("|")[0].strip().upper() in x.upper()
            ]
            if _engine_issues:
                st.warning(
                    "**LLP Source Metadata Warning:** " + " ".join(_engine_issues)
                )

        _llp_display = df_llp_engine[
            [
                "Component", "P/N", "S/N", "Basis", "Remaining",
                "Estimated Due Date", "Work Reference", "Life Status"
            ]
        ].copy()

        _llp_display["Remaining"] = _llp_display.apply(
            lambda r: (
                f"{r['Remaining']:,.1f} {r['Basis']}"
                if pd.notna(r["Remaining"]) and str(r["Basis"]).strip()
                else (
                    "Not available"
                    if pd.isna(r["Remaining"])
                    else f"{r['Remaining']:,.1f}"
                )
            ),
            axis=1,
        )
        _llp_display["Estimated Due Date"] = _llp_display["Estimated Due Date"].apply(
            lambda x: x.strftime("%d %b %Y") if pd.notna(x) else "Not projected"
        )
        _llp_display = _llp_display.rename(columns={
            "Remaining": "Life Remaining",
            "Estimated Due Date": "Estimated Due",
            "Work Reference": "Work Ref.",
            "Life Status": "Status",
        })

        # Semantic formatting is deliberately restricted to LLP Status.
        try:
            _llp_styled = _llp_display.style.map(
                lambda v: (
                    "font-weight:700; color:#B91C1C;"
                    if str(v).upper() == "OVERDUE"
                    else "font-weight:600; color:#166534;"
                ),
                subset=["Status"],
            )
        except AttributeError:
            _llp_styled = _llp_display.style.applymap(
                lambda v: (
                    "font-weight:700; color:#B91C1C;"
                    if str(v).upper() == "OVERDUE"
                    else "font-weight:600; color:#166534;"
                ),
                subset=["Status"],
            )

        st.dataframe(
            _llp_styled,
            use_container_width=True,
            hide_index=True,
            height=min(520, 56 + 42 * len(_llp_display)),
            column_config={
                "Component": st.column_config.TextColumn(
                    "Component", width="large"
                ),
                "P/N": st.column_config.TextColumn(
                    "P/N", width="medium"
                ),
                "S/N": st.column_config.TextColumn(
                    "S/N", width="medium"
                ),
                "Basis": st.column_config.TextColumn(
                    "Basis", width="small"
                ),
                "Life Remaining": st.column_config.TextColumn(
                    "Life Remaining", width="medium"
                ),
                "Estimated Due": st.column_config.TextColumn(
                    "Estimated Due", width="medium"
                ),
                "Work Ref.": st.column_config.TextColumn(
                    "Work Ref.", width="medium"
                ),
                "Status": st.column_config.TextColumn(
                    "Status", width="small"
                ),
            },
        )

        with st.expander("View LLP Source & Traceability Details", expanded=False):
            st.caption(
                "Source-level fields are retained for auditability. "
                "The dashboard does not silently correct source metadata discrepancies."
            )
            st.dataframe(
                df_llp_engine[
                    [
                        "Component #", "Component", "P/N", "S/N",
                        "Work Reference", "Work Description", "Interval",
                        "Last Accomplishment", "Accumulated", "Expiration",
                        "Remaining", "Basis", "Estimated Due Date",
                        "Status", "Installed At", "Current Profile"
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("---")
    with st.expander("View Raw Flight Observations", expanded=False):
        st.caption("Raw telemetry is provided for investigation and traceability; the ECTM assessment above remains the primary interpretation layer.")
        show_cols = [c for c in ["AML No", "Date", "Engine", "T5", "Delta_T5", "Ng", "Delta_Ng", "Wf", "Delta_Wf_pct"] if c in df_engine.columns]
        st.dataframe(
            df_engine[show_cols].sort_values("Date", ascending=False),
            use_container_width=True,
            height=260
        )
    
# ======================================================================================
# 17. PAGE 4: LOGBOOK & DEFECT CORRELATOR (WITH 3-WAY RELATIONAL SSOT)
# ======================================================================================
elif menu_selection == "Logbook":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Maintenance Logbook</h1>", unsafe_allow_html=True)
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
                
                # [BULLETPROOF FIX] Paksa parsing ke datetime agar aman dari error strftime
                dt_parsed = pd.to_datetime(dt_val, errors="coerce")
                dt_str = dt_parsed.strftime("%Y-%m-%d") if pd.notnull(dt_parsed) else "N/A"
                
                # Tarik data telemetri LH & RH
                lh_row = grp[grp["Engine"].astype(str).str.contains("LH")]
                rh_row = grp[grp["Engine"].astype(str).str.contains("RH")]
                lh_t5 = f"{lh_row['Delta_T5'].values[0]:+.1f}°C" if not lh_row.empty and "Delta_T5" in lh_row.columns else "N/A"
                rh_t5 = f"{rh_row['Delta_T5'].values[0]:+.1f}°C" if not rh_row.empty and "Delta_T5" in rh_row.columns else "N/A"
                
                # Tarik data jam terbang dari file Utilization
                u_match = pd.DataFrame()
                if not df_util_current.empty and "Work (Date)" in df_util_current.columns:
                    mask_u_aml = df_util_current["AML No"] == aml_val
                    mask_u_date = (df_util_current.get("Registration", "") == sel_reg) & (df_util_current["Work (Date)"].dt.strftime("%Y-%m-%d") == dt_str)
                    u_match = df_util_current[mask_u_aml | mask_u_date]
                fh_val = f"{u_match['FH'].values[0]:.1f} FH / {u_match['FC'].values[0]:.0f} FC" if not u_match.empty else "N/A"
                
                # Evaluasi PIREP/MAREP
                r_match = pd.DataFrame()
                if not df_rep_current.empty and "Date" in df_rep_current.columns:
                    mask_r_aml = df_rep_current["AML No"] == aml_val
                    mask_r_date = (df_rep_current.get("Registration", "") == sel_reg) & (df_rep_current["Date"].dt.strftime("%Y-%m-%d") == dt_str)
                    r_match = df_rep_current[mask_r_aml | mask_r_date]
                rep_val = f"[{r_match['ATA_Desc'].values[0]}] {r_match['Corrective Action'].values[0][:45]}..." if not r_match.empty else "Normal Operations (No Defect Logged)"
                
                sync_rows.append({
                    "AML No (Key)": aml_val,
                    "Flight Date": dt_str,
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
        safe_text = html_lib.escape(text)
        if not kw:
            return safe_text
        kw_clean = re.escape(html_lib.escape(kw.strip()))
        hl_style = 'background-color: #f0b73d; color: #003B6F; font-weight: 800; padding: 1px 6px; border-radius: 3px; box-shadow: 0 1px 2px rgba(0,0,0,0.1);'
        return re.sub(r'\b(' + kw_clean + r')\b', r'<mark style="' + hl_style + r'">\1</mark>', safe_text, flags=re.IGNORECASE)

    if df_filtered.empty:
        st.info("No PIREP / MAREP reports found matching the selected filter criteria.")
    else:
        for idx, row in df_filtered.head(15).iterrows():
            with st.container(border=True):
                c_head1, c_head2, c_head3 = st.columns([2, 1, 1])
                c_head1.markdown(f"**AML No:** `{row.get('AML No', 'N/A')}` | **ATA:** `{row.get('ATA_Desc', 'N/A')}`")
                safe_dt = pd.to_datetime(row['Date'], errors='coerce')
                c_head2.markdown(f"**Date:** `{safe_dt.strftime('%Y-%m-%d') if pd.notnull(safe_dt) else 'N/A'}`")
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
elif menu_selection == "Recommendations":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Maintenance Recommendations & Notice Transmittal</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>Active Powerplant: <b style='color:#003B6F; background:#EFF4FA; padding:2px 8px; border-radius:4px; border:1px solid #CBD5E1;'>{selected_engine}</b> | P&WC PT6A-34 FIM (Rev 75.0)</p>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    overall_status_label = status["status_label"]
    st.markdown(f"**Observed Shift Vector:** `ΔT5: {status['shift_t5']}` | `ΔNg: {status['shift_ng']}` | `ΔWf: {status['shift_wf']}` &nbsp;&nbsp;|&nbsp;&nbsp; **Engine Health Status:** **{overall_status_label}**")
    st.markdown("<br>", unsafe_allow_html=True)

    # [TIER 1 UPGRADE] Structured Recommendation Cards (Integrated Enterprise Checklist)
    for rec in recommendations:
        lvl = rec["level"]
        badge_cls = "badge-red" if lvl == "red" else ("badge-amber" if lvl == "amber" else "badge-green")
        card_cls = f"rec-card-{lvl}"
        border_color = "#DC2626" if lvl == "red" else ("#D97706" if lvl == "amber" else "#16A34A")
        
        # Pisahkan paragraf penjelasan umum dengan daftar instruksi (Line Engineering Directives)
        parts = rec["body"].split("**Line Engineering Directives:**")
        overview = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", parts[0].replace("\n", "<br>").strip())
        directives = parts[1].strip() if len(parts) > 1 else ""
        
        # Format daftar instruksi menjadi Callout Checklist Box bernomor yang elegan
        directives_html = ""
        if directives:
            lines = [line.strip() for line in directives.split("\n") if line.strip()]
            if any(re.match(r"^\d+\.", line) for line in lines):
                cleaned_lines = [re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", re.sub(r"^\d+\.\s*", "", line)) for line in lines]
                list_items = "".join([f"<li style='margin-bottom: 8px; line-height: 1.5;'>{line}</li>" for line in cleaned_lines])
                content_body = f"<ol style='margin: 0; padding-left: 20px; color: #0F172A; font-size: 0.9rem; font-weight: 500;'>{list_items}</ol>"
            else:
                formatted_text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", directives)
                content_body = f"<p style='margin: 0; color: #0F172A; font-size: 0.9rem; line-height: 1.6; font-weight: 500;'>{formatted_text}</p>"
                
            # [ANTI-CODE BLOCK & ZERO EMOTICON] Ditulis padat tanpa spasi awal dan tanpa emotikon
            directives_html = f"<div style='background: #F8FAFC; border-left: 4px solid {border_color}; padding: 14px 18px; border-radius: 0 8px 8px 0; margin-top: 14px; border-top: 1px solid #E2E8F0; border-right: 1px solid #E2E8F0; border-bottom: 1px solid #E2E8F0;'><span style='color: #003B6F; font-weight: 800; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; display: block; margin-bottom: 8px;'>Line Engineering Directives & Action Checklist:</span>{content_body}</div>"
        
        st.markdown(f"""
        <div class="rec-card-box {card_cls}" style="background: #FFFFFF; border: 1px solid #CBD5E1; border-left: 6px solid {border_color}; border-radius: 12px; padding: 18px; margin-bottom: 20px; box-shadow: 0 6px 18px -3px rgba(0, 40, 77, 0.06);">
            <div class="rec-header" style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid #E2E8F0; padding-bottom: 12px; margin-bottom: 14px;">
                <span class="rec-title" style="font-size: 1.15rem; font-weight: 800; color: #00284D;">{rec['title']}</span>
                <span class="{badge_cls}">{rec.get('priority', 'ROUTINE')}</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom: 14px; font-size:0.85rem; background: #EFF4FA; padding: 10px 14px; border-radius: 6px; border: 1px solid #CBD5E1;">
                <div><span style="color:#475569; font-weight:600;">Thermodynamic Signature:</span> <b style="color:#0F172A;">{rec.get('signature', 'N/A')}</b></div>
                <div><span style="color:#475569; font-weight:600;">Estimated Downtime:</span> <b style="color:#0F172A;">{rec.get('downtime', 'N/A')}</b></div>
                <div><span style="color:#475569; font-weight:600;">FIM Manual Ref:</span> <b style="color:#003B6F;">{rec['fim_ref']}</b></div>
            </div>
            <div style="color: #334155; font-size: 0.92rem; line-height: 1.6; font-weight: 500;">
                {overview}
            </div>
            {directives_html}
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("<h3 style='color:#003B6F; margin-bottom:4px;'>Engineering Document Export</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color:#475569; font-size:0.88rem; margin-bottom:14px;'>Download technical reports or generate formal Engineering Work Orders (EWO) for line maintenance execution.</p>", unsafe_allow_html=True)
    
    report_lines = [
        f"PT. AIRFAST INDONESIA - ECTM TECHNICAL ANALYSIS REPORT",
        f"Powerplant Serial / Position: {selected_engine}",
        f"Date Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Latest Cycle: {status['latest']['Date'].strftime('%Y-%m-%d')}",
        "-------------------------------------------------------------------------",
        f"Computed Residuals: Delta T5: {status['d_t5']:+.1f} degC | Delta Ng: {status['d_ng']:+.2f} % | Delta Wf: {status['d_wf']:+.1f} PPH",
        f"Engine Health Status: {overall_status_label} | ECTM Confidence: {status['model_confidence']}",
        f"ECTM Confidence Reason: {status['confidence_reason']}",
        f"Predictive RUL: {'NOT ASSESSED — ECTM CONFIDENCE LOW' if status['model_confidence'] != 'HIGH' else str(status['rul_cycles']) + ' Cycles (' + str(status['proj_date']) + ')'}",
        f"RUL Confidence: {status['rul_confidence']}",
        f"LLP Components Mapped: {len(df_llp_engine)} | LLP Report Date: {(llp_report_dates.max().strftime('%Y-%m-%d') if not llp_report_dates.empty else 'Not available')}",
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

    # --- [FAILOVER MONITOR / PENDING QUEUE UI] ---
    pending_queue = load_pending_queue()
    if pending_queue:
        n_pending = len(pending_queue)
        with st.container(border=True):
            st.markdown(f"""
            <div style="background-color: rgba(217, 119, 6, 0.1); border-left: 4px solid #D97706; padding: 14px 18px; border-radius: 0 8px 8px 0; margin-bottom: 14px;">
                <span style="color: #D97706; font-weight: 800; font-size: 0.88rem; text-transform: uppercase; letter-spacing: 0.05em; display: block;">Offline Failover Alert: {n_pending} Pending Notice(s) Queued</span>
                <span style="color: #334155; font-size: 0.85rem; line-height: 1.5; display: block; margin-top: 4px; font-weight: 500;">
                    Previous SMTP transmittals failed due to network timeout or offline connectivity at the hangar/strip. Notices and PDF work orders are safely preserved in the local persistent cache.
                </span>
            </div>
            """, unsafe_allow_html=True)
            
            q_rows = []
            for q_key, q_item in pending_queue.items():
                q_rows.append({
                    "Powerplant ID": q_item["engine_id"],
                    "Failed Timestamp": q_item["failed_timestamp"],
                    "Target MCC Recipients": ", ".join(q_item["recipients"]),
                    "Status Classification": q_item["status_dict"].get("status_label", "UNKNOWN")
                })
            st.dataframe(pd.DataFrame(q_rows), use_container_width=True, hide_index=True, height=120)
            
            if st.button(f"Retry Dispatch Now ({n_pending} Pending Notices)", type="primary", use_container_width=True, key="btn_retry_queue"):
                with st.spinner("Re-attempting SMTP transmission to MCC for all queued notices..."):
                    succ, fail = retry_pending_queue()
                    if succ > 0:
                        st.success(f"Successfully dispatched {succ} notice(s) to MCC!")
                    if fail > 0:
                        st.error(f"Failed to dispatch {fail} notice(s). Network connection may still be unreachable.")
                    st.rerun()
            st.write("")
    # ---------------------------------------------
    
    st.markdown("<p style='color:#475569; font-size:0.88rem; margin-bottom:14px;'>Transmit urgent engineering evaluations directly to responsible Fleet Managers and Maintenance Control Center (MCC).</p>", unsafe_allow_html=True)

    # =========================================================================
    # MANUAL TRIGGER (FULL HUMAN OVERRIDE - BEBAS KIRIM KAPAN SAJA)
    # =========================================================================
    st.markdown("""
    <div style="background-color:#F8FAFC; border-left:4px solid #003B6F; border-top:1px solid #E2E8F0; border-right:1px solid #E2E8F0; border-bottom:1px solid #E2E8F0; padding:12px 16px; border-radius:4px; margin-bottom:16px;">
        <b style="color:#003B6F; font-size:0.85rem; letter-spacing:0.03em; display:block; margin-bottom:4px;">EXECUTIVE NOTICE TRANSMITTAL & FLEET OVERRIDE</b>
        <span style="color:#475569; font-size:0.8rem; line-height:1.5; display:block;">
            <b>Manual Dispatch:</b> Bypasses the anti-spam ledger, allowing you to transmit EWO notices multiple times to any custom recipient.<br>
            <b>Fleet Watchdog:</b> To run an automated CRITICAL health scan across all engines at once, use the <i>"Run Fleet Health Scan Now"</i> control in the sidebar.
        </span>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        col_em1, col_em2 = st.columns([3, 1])
        with col_em1:
            # Email langsung diisi di 'value' supaya tidak sekadar placeholder abu-abu
            default_recipients = "mcc.duty@airfastindonesia.com, chief.engineer@airfastindonesia.com"
            target_emails = st.text_input(
                "Recipient Email Addresses (comma-separated)", 
                value=default_recipients,
                key="manual_email_input"
            )
        with col_em2:
            st.write("")
            st.write("")
            # Tombol kirim selalu aktif tanpa pengecekan can_dispatch atau ledger
            if st.button("Transmit Engineering Notice", type="primary", use_container_width=True):
                recipients_list = [e.strip() for e in target_emails.split(",") if e.strip()]
                if not recipients_list:
                    st.error("❌ Enter at least one recipient email address.")
                else:
                    with st.spinner("Transmitting engineering notice via secure SMTP..."):
                        # Panggil fungsi kirim email TANPA menyertakan alert_key (Bypass Ledger)
                        success = send_engineering_notice(
                            selected_engine, 
                            status, 
                            "\n".join(report_lines), 
                            recipients_list, 
                            is_automated=False, 
                            recommendations=recommendations
                        )
                        if success: 
                            st.success(f"✅ Manual Engineering Notice transmitted successfully to: {', '.join(recipients_list)}")
