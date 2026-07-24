"""
========================================================================================
 ENTERPRISE ECTM & FLEET MAINTENANCE CONTROL SYSTEM (FINAL PRODUCTION RELEASE v4)
 PT. AIRFAST INDONESIA | DHC-6 TWIN OTTER / P&WC PT6A-34 FLEET
========================================================================================
 Architecture : Standalone Enterprise SaaS (Streamlit / Plotly / Multi-Linear Regression)
 Compliance   : P&WC PT6A-34 Fault Isolation Manual (P/N 3021242, Rev 75.0)
 Enhancements : - [v4] Single Source of Truth (SSOT) via EngineHealth Enum (Anti-Contradiction)
                - [v4] Clean Tooltip UI (Rounded Residuals & Simplified Hovertemplate)
                - Automated Data Quality & Outlier Audit (Pre-Flight Ingestion Check)
                - Adaptive Expanding Statistical Noise Banding (Dynamic Control Limits)
                - Robust Regex Registration Matching for Defect Correlator
                - Dual-Protocol SMTP Fallback (SSL Port 465 -> STARTTLS Port 587)
                - Native Print-Ready PDF Engineering Work Order (EWO) Generator
========================================================================================
"""

import io
import os
import re
import smtplib
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
# EXECUTIVE DASHBOARD HEADER (TOP-RIGHT LOGO)
# ======================================================================================

# Membagi area atas menjadi 2 kolom: Kiri untuk Judul Dasbor (lebar), Kanan untuk Logo (ringkas)
header_col1, header_col2 = st.columns([4, 1.2])

with header_col1:
    st.title("ECTM Fleet Diagnostics Matrix")
    st.markdown("**PT. AIRFAST Indonesia** | DHC-6 / P&WC PT6A-34 Engine Telemetry")

with header_col2:
    # Logo SVG kompak warna Navy & Gold, diatur rata kanan (float right / text-align right)
    top_right_logo_svg = """
    <div style="text-align: right; padding-top: 15px;">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 50" width="100%" height="100%" style="max-width: 220px;">
          <!-- Ikon Monogram 'A' / Emblem Sayap Kompak -->
          <g transform="translate(0, 3)">
            <path d="M 20 2 L 40 42 L 30 42 L 20 20 L 10 42 L 0 42 Z" fill="#003B6F"/>
            <path d="M 20 15 L 28 32 L 20 24 L 12 32 Z" fill="#F0B73D"/>
          </g>
          <!-- Teks Brand Rapi dan Proporsional -->
          <g transform="translate(52, 32)">
            <text x="0" y="0" font-family="'Plus Jakarta Sans', 'Segoe UI', sans-serif" font-size="24" font-weight="800" fill="#003B6F" letter-spacing="1">ALDO</text>
            <text x="70" y="0" font-family="'Plus Jakarta Sans', 'Segoe UI', sans-serif" font-size="24" font-weight="300" fill="#64748B" letter-spacing="1">AEROSPACE</text>
          </g>
        </svg>
    </div>
    """
    st.markdown(top_right_logo_svg, unsafe_allow_html=True)

# Garis pembatas elegan sebelum masuk ke metrik dasbor
st.markdown("<hr style='margin-top: -5px; margin-bottom: 20px; border: 0; height: 1px; background: #E2E8F0;'>", unsafe_allow_html=True)
st.markdown(
    """
    <style>
    .stAlert { color: #1f2937 !important; }
    div[data-baseweb="notification"], div.element-container stMarkdown { color: inherit; }
    .st-emotion-cache-1wivap2, div[data-testid="stNotification"] { color: #1f2937 !important; }
    </style>
""",
    unsafe_allow_html=True,
)

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

REQUIRED_COLUMNS = ["Date", "Engine", "T5", "Ng", "Wf"]
CORRECTION_CANDIDATES = ["IOAT", "Press_Alt", "TQ", "Np"]
OPTIONAL_COLUMNS = CORRECTION_CANDIDATES + ["IAS", "Oil_Temp", "Oil_Press"]

NAVY = "#003B6F"
GOLD = "#f0b73d"
SLATE_DARK = "#0F172A"
SLATE_MUTED = "#64748B"

# ======================================================================================
# 3. ENTERPRISE AVIATION SAAS STYLING (CUSTOM CSS)
# ======================================================================================
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }

    [data-testid="stAppViewContainer"], [data-testid="stApp"], .main {
        background-color: #FFFFFF !important; color: #0F172A !important;
    }
    [data-testid="stHeader"] { background-color: transparent !important; }
    
    h1, h2, h3, h4 { color: #003B6F !important; font-weight: 700 !important; letter-spacing: -0.02em; }
    h1 { font-size: 1.85rem !important; }
    h2 { font-size: 1.35rem !important; }
    h3 { font-size: 1.15rem !important; }
    
    div[data-testid="stMetric"] {
        background-color: #F8FAFC !important; border: 1px solid #E2E8F0 !important;
        border-left: 4px solid #003B6F !important; padding: 14px 16px !important;
        border-radius: 6px !important; box-shadow: none !important;
    }
    div[data-testid="stMetricLabel"] > label > p {
        color: #475569 !important; font-weight: 600 !important; font-size: 0.82rem !important;
        text-transform: uppercase; letter-spacing: 0.05em;
    }
    div[data-testid="stMetricValue"] > div { color: #0F172A !important; font-weight: 700 !important; font-size: 1.45rem !important; }

    [data-testid="stSidebar"] {
        background-color: #003B6F !important; border-right: 1px solid #00284D !important;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] div, [data-testid="stSidebar"] b {
        color: #F8FAFC !important;
    }
    
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        padding: 12px 16px !important; margin-bottom: 4px !important;
        border-bottom: 1px solid rgba(255,255,255,0.08) !important;
        cursor: pointer; transition: all 0.15s ease-in-out; width: 100%; border-radius: 4px !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background-color: rgba(255,255,255,0.08) !important; padding-left: 20px !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] p {
        font-size: 0.92rem !important; font-weight: 500 !important; color: #CBD5E1 !important; margin: 0 !important;
    }
    
    [data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"] {
        border-left: 4px solid #f0b73d !important; background-color: rgba(255,255,255,0.12) !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"] p {
        color: #FFFFFF !important; font-weight: 700 !important;
    }

    [data-testid="stSidebar"] div[data-baseweb="radio"] div[role="radio"] div {
        background-color: transparent !important; border-color: #f0b73d !important;
    }
    [data-testid="stSidebar"] div[data-baseweb="radio"] div[role="radio"][aria-checked="true"] div:first-child {
        background-color: #f0b73d !important; border-color: #f0b73d !important;
    }
    
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #003B6F !important; color: #FFFFFF !important;
        font-weight: 600 !important; font-size: 0.95rem !important;
        border-radius: 6px !important; padding: 10px 20px !important;
        border: 1px solid #003B6F !important; transition: all 0.2s ease !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background-color: #00284D !important; border-color: #f0b73d !important; color: #f0b73d !important;
    }

    div[data-testid="stDownloadButton"] > button, div[data-testid="stButton"] > button[kind="secondary"] {
        background-color: #FFFFFF !important; color: #0F172A !important;
        font-weight: 600 !important; font-size: 0.88rem !important;
        border-radius: 6px !important; border: 1px solid #CBD5E1 !important;
        transition: all 0.15s ease !important;
    }
    div[data-testid="stDownloadButton"] > button:hover, div[data-testid="stButton"] > button[kind="secondary"]:hover {
        background-color: #F8FAFC !important; border-color: #003B6F !important; color: #003B6F !important;
    }

    .gold-bar { height: 3px; width: 60px; background-color: #f0b73d; margin-top: -8px; margin-bottom: 20px; }
    
    .badge-red { background:#FEF2F2; color:#991B1B; border:1px solid #FECACA; border-radius:4px;
                 padding:4px 12px; font-weight:700; font-size:0.78rem; letter-spacing:0.05em; text-transform:uppercase; display:inline-block;}
    .badge-amber { background:#FFFBEB; color:#92400E; border:1px solid #FDE68A; border-radius:4px;
                   padding:4px 12px; font-weight:700; font-size:0.78rem; letter-spacing:0.05em; text-transform:uppercase; display:inline-block;}
    .badge-green { background:#F0FDF4; color:#166534; border:1px solid #BBF7D0; border-radius:4px;
                   padding:4px 12px; font-weight:700; font-size:0.78rem; letter-spacing:0.05em; text-transform:uppercase; display:inline-block;}
    
    .rul-box { background:#F8FAFC; border:1px solid #CBD5E1; border-left:4px solid #f0b73d;
               padding:12px 16px; border-radius:6px; margin-top:10px; margin-bottom:10px; }
    .rul-title { font-size:0.82rem; font-weight:700; color:#475569; text-transform:uppercase; letter-spacing:0.05em; }
    .rul-val { font-size:1.2rem; font-weight:800; color:#003B6F; margin-top:2px; }
    .rul-sub { font-size:0.78rem; font-weight:500; color:#64748B; margin-top:2px; }

    .fim-ref { display:inline-block; background:#F1F5F9; color:#334155; border:1px solid #CBD5E1;
               border-radius: 4px; padding: 2px 8px; font-size:0.75rem; font-weight:600; margin-left:6px;}
    hr { border-color: #E2E8F0 !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ======================================================================================
# 4. SESSION STATE MANAGEMENT & CALLBACK HELPERS
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

# [POIN 1 REVISI] Database Akun Resmi Airfast (Berdasarkan struktur jabatan CMM)
USER_DATABASE = {
    "admin@airfastindonesia.com": {
        "password": "admin123",
        "role": "Chief Engineer / Admin",
        "name": "Wayan Adi (Chief Inspector)"
    },
    "engineer@airfastindonesia.com": {
        "password": "eng123",
        "role": "Powerplant Engineer",
        "name": "Rochadin (TS Supervisor)"
    },
    "officer@airfastindonesia.com": {
        "password": "entry123",
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

# ======================================================================================
# 5. DATA NORMALIZATION & INGESTION MODULE
# ======================================================================================
def process_maintenance_reports(df_rep: pd.DataFrame) -> pd.DataFrame:
    if df_rep.empty:
        return pd.DataFrame(columns=['AML No', 'Date', 'Registration', 'ATA', 'ATA_Desc', 'Note / Report', 'Corrective Action', 'Position', 'P/N Off', 'P/N On'])
    
    df_rep = df_rep.copy()
    if 'Date' in df_rep.columns:
        df_rep['Date'] = pd.to_datetime(df_rep['Date'], errors='coerce')
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
                
            rows_ectm.append(dict(
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
                df_util['Work (Date)'] = pd.to_datetime(df_util['Work (Date)'], errors='coerce')
                df_util = df_util.dropna(subset=['Registration', 'Work (Date)']).sort_values('Work (Date)')
                util_is_real = not df_util.empty
            except Exception:
                df_util = pd.DataFrame()
            break

    if df_util.empty:
        util_rows = []
        for reg in ["PK-OAM", "PK-OCH", "PK-OCG", "PK-OCI", "PK-OCF"]:
            for d in range(60):
                fc = int(rng.choice([2, 4, 6, 8], p=[0.2, 0.4, 0.3, 0.1]))
                fh = round(fc * rng.uniform(0.6, 0.9), 1)
                util_rows.append(dict(
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
            {"AML No": "OAM-2026-001", "Date": "2026-06-10", "Registration": "PK-OAM", "ATA": 71, "ATA_Desc": "71 - Powerplant General", "Note / Report": "Pilot reported engine T5 ITT running 8 deg C above normal during cruise at 10,000 ft.", "Corrective Action": "Performed Compressor Performance Recovery Wash per AMM 71-00-00. Ground run test SAT. ITT dropped by 7 deg C.", "Position": "LH", "P/N Off": np.nan, "P/N On": np.nan, "S/N Off": np.nan, "S/N On": np.nan},
            {"AML No": "OAM-2026-002", "Date": "2026-05-26", "Registration": "PK-OAM", "ATA": 77, "ATA_Desc": "77 - Engine Indicating", "Note / Report": "ITT cockpit gauge flickered and showed momentary high spike during climb.", "Corrective Action": "Checked ITT wiring harness and thermocouple terminal connections. Found loose ground wire. Re-torqued and tested SAT.", "Position": "RH", "P/N Off": "3021100", "P/N On": "3021100", "S/N Off": "TH-991", "S/N On": "TH-992"},
            {"AML No": "OCH-2026-003", "Date": "2026-06-20", "Registration": "PK-OCH", "ATA": 72, "ATA_Desc": "72 - Engine", "Note / Report": "High T5 trend paired with Ng drop. Suspected CT vane erosion or bleed valve leak.", "Corrective Action": "Scheduled engine for mandatory borescope inspection. Replaced faulty compressor bleed valve assembly.", "Position": "LH", "P/N Off": "3100250-01", "P/N On": "3100250-01", "S/N Off": "BV-102", "S/N On": "BV-884"},
            {"AML No": "OCH-2026-004", "Date": "2026-06-05", "Registration": "PK-OCH", "ATA": 73, "ATA_Desc": "73 - Engine Fuel & Control", "Note / Report": "All engine parameters (Ng, ITT, Wf) reading slightly lower than baseline at cruise power.", "Corrective Action": "Inspected P3 pneumatic sensing line. Found minor air leak at FCU Bellows B-nut fitting. Re-sealed and leak tested SAT.", "Position": "RH", "P/N Off": np.nan, "P/N On": np.nan, "S/N Off": np.nan, "S/N On": np.nan},
            {"AML No": "OCG-2026-005", "Date": "2026-06-15", "Registration": "PK-OCG", "ATA": 79, "ATA_Desc": "79 - Engine Oil", "Note / Report": "Oil temperature slightly elevated by 3 deg C over the last 10 sectors.", "Corrective Action": "Inspected oil cooler matrix and cleaned external dust accumulation. Re-verified oil pressure relief valve setting.", "Position": "LH", "P/N Off": np.nan, "P/N On": np.nan, "S/N Off": np.nan, "S/N On": np.nan},
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
    cols = REQUIRED_COLUMNS + [c for c in OPTIONAL_COLUMNS if c not in REQUIRED_COLUMNS]
    example = pd.DataFrame([{"Date": "2026-06-01", "Engine": "PK-OAM | LH (SN: PC-E101)", "Press_Alt": 11000, "IOAT": 12.0, "IAS": 135.0, "TQ": 42.0, "Np": 75, "T5": 624.0, "Ng": 91.50, "Wf": 288.0, "Oil_Temp": 72.5, "Oil_Press": 91.0}])
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
                alerts.append("⚠️ Physical Outlier: IOAT exceeds standard operational atmospheric envelope (-40°C to +55°C).")
        if "T5" in df.columns and (df["T5"] <= 0).any():
            alerts.append("⚠️ Sensor Error: T5 recorded at or below 0°C during engine operation.")
        
        for col in ["T5", "Ng", "Wf"]:
            if col in df.columns and len(df) >= 3:
                stuck_mask = (df[col].diff() == 0) & (df[col].diff().shift(-1) == 0)
                if stuck_mask.any():
                    alerts.append(f"🔒 Sensor Freeze Suspected: Column '{col}' contains identical consecutive static values for 3+ cycles.")
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
    n = max(2, min(baseline_n, len(df_engine)))
    df_baseline = df_engine.iloc[:n]
    predictors = [c for c in CORRECTION_CANDIDATES if c in df_engine.columns] if use_correction else []
    models = {}
    is_downgraded = False
    
    for target in ["T5", "Ng", "Wf"]:
        models[target] = fit_correction_model(df_baseline, predictors, target)
        if models[target].get("downgraded", False) and use_correction and len(predictors) > 0:
            is_downgraded = True
        df_engine[f"{target}_pred"] = apply_correction_model(models[target], df_engine)
        # [UI FIX] Pembulatan 2 desimal langsung di level dataframe untuk mencegah tooltip overflow
        df_engine[f"Delta_{target}"] = (df_engine[target] - df_engine[f"{target}_pred"]).round(2)
        
    df_engine["Delta_Ng_pct"] = df_engine["Delta_Ng"]
    baseline_wf_mean = df_baseline["Wf"].mean()
    df_engine["Delta_Wf_pct"] = (100 * df_engine["Delta_Wf"] / (baseline_wf_mean if baseline_wf_mean != 0 else 1.0)).round(2)
    
    noise = {t: max(df_engine.loc[: n - 1, f"Delta_{t}"].std(ddof=0), 1e-6) for t in ["T5", "Ng", "Wf"]}
    for t in ["T5", "Ng", "Wf"]:
        rolling_std = df_engine[f"Delta_{t}"].rolling(window=TREND_WINDOW, min_periods=n).std()
        df_engine[f"Adaptive_Sigma_{t}"] = rolling_std.fillna(noise[t]).clip(lower=noise[t], upper=noise[t] * 3).round(2)

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
    
    # [SSOT CORE] Penentuan keparahan absolut di satu tempat agar UI, PDF, dan Email tidak bertentangan
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
        rul_cycles=rul_cycles, proj_date=proj_date, fc_per_day=fc_per_day,
        rul_confidence=rul_confidence, rul_is_linear_caution=rul_is_linear_caution,
        reg_prefix=reg_prefix
    )

def generate_recommendations(df_engine: pd.DataFrame, status: dict) -> list:
    recs = []
    if status["isolated_t5"] or status["isolated_ng"]:
        recs.append(dict(level="amber", title="Possible Indicating System Anomaly (Isolated Point Shift)", fim_ref="FIM Table 101, Note 2",
            body=("The latest observation indicates a rapid single-cycle parameter shift inconsistent with preceding thermodynamic regression trends. "
                  "Per OEM manual guidance, isolated spikes are predominantly caused by instrumentation calibration drift or electrical transmitter faults.\n\n"
                  "**Line Engineering Directives:**\n1. Verify source flight-log entries to rule out transcription errors.\n"
                  "2. Conduct instrumentation calibration check on T5 / Ng cockpit indicators and engine transmitter units per AMM Ref. 77-00-00.\n"
                  "3. Defer invasive hardware maintenance; confirm whether shift persists across subsequent operating cycles.")))
    if status["alarm_borescope_t5"] or status["alarm_borescope_ng"]:
        recs.append(dict(level="red", title="Mandatory Hot-Section Borescope Inspection Required", fim_ref="FIM Fig. 103 Sheet 9, Note 3",
            body=(f"Thermodynamic residuals breached critical OEM limits: Delta T5 = **{status['d_t5']:+.1f} °C** (Limit: +15.0 °C) / "
                  f"Delta Ng = **{status['d_ng']:+.2f} %** (Limit: -1.0% to -1.5%).\n\n**Line Engineering Directives:**\n"
                  "1. Ground powerplant and schedule immediate hot-section borescope inspection per AMM Ref. 72-00-00.\n"
                  "2. Inspect combustion chamber liner, small exit duct, CT stator vanes, and CT rotor blades for thermal distortion or severe erosion.\n"
                  "3. Execute compressor performance recovery wash protocols upon completion of mechanical inspections.\n"
                  "4. If structural distress exceeds repairable AMM limits, route powerplant to an approved P&WC overhaul facility.")))
    elif status["alarm_wash"] or status["sustained_t5"]:
        recs.append(dict(level="amber", title="Compressor Performance Recovery Wash Recommended", fim_ref="FIM Fig. 103 Sheet 9, Note 3",
            body=(f"Delta T5 demonstrates a sustained upward degradation trend reaching **{status['d_t5']:+.1f} °C** above installation baseline.\n\n"
                  "**Line Engineering Directives:**\n1. Execute compressor performance recovery wash per AMM Ref. 71-00-00.\n"
                  "2. Perform engine ground test run post-wash to confirm ITT recovery and re-verify baseline calibration.\n"
                  "3. Inspect fuel nozzle assemblies for spray pattern distortion if fuel flow deviation (ΔWf) is concurrently elevated.")))
    t5, ng, wf = status["shift_t5"], status["shift_ng"], status["shift_wf"]
    if t5 == "UP" and ng == "DOWN" and wf == "UP":
        recs.append(dict(level="amber", title="Compressor Aerodynamic Efficiency Loss / Bleed Valve Anomaly", fim_ref="FIM Table 101 / Fig. 103",
            body=("Thermodynamic Signature: **ITT Increase | Ng Decrease | Fuel Flow Increase**. Consistent with aerodynamic efficiency degradation.\n\n"
                  "**Line Engineering Directives:**\n1. Perform compressor desalination or performance recovery wash.\n"
                  "2. Inspect compressor bleed valve operation and diaphragm integrity (Ref. 75-30-00) to confirm full acoustic closure.\n"
                  "3. Execute visual and borescope examination of first-stage compressor blades for FOD per AMM Ref. 72-30-05.")))
    elif t5 == "UP" and ng == "UP" and wf == "UP":
        recs.append(dict(level="amber", title="Compressor Turbine Nozzle Area Enlargement", fim_ref="FIM Table 101 / Fig. 103 Sheet 1",
            body=("Thermodynamic Signature: **ITT Increase | Ng Increase | Fuel Flow Increase**. Consistent with effective nozzle area enlargement.\n\n"
                  "**Line Engineering Directives:**\n1. Schedule Hot Section Inspection (HSI) at next available maintenance window.\n"
                  "2. Inspect Compressor Turbine (CT) stator vanes for trailing-edge erosion, cracking, or bowing.\n"
                  "3. Verify power turbine vane ring class average specification per AMM Ref. 72-50-03.")))
    elif t5 == "DOWN" and ng == "DOWN" and wf == "DOWN":
        recs.append(dict(level="amber", title="Pneumatic Sensing Reference Leak / FCU Calibration Drift", fim_ref="FIM Table 101",
            body=("Thermodynamic Signature: **Uniform downward shift across all parameters**. Indicates pneumatic sensing line leakage or FCU drift.\n\n"
                  "**Line Engineering Directives:**\n1. Inspect P3 and Py pneumatic sensing lines, fittings, and FCU bellows for leakage.\n"
                  "2. Conduct instrumentation calibration check on cockpit indicators and engine transmitter units.")))
    
    if not recs:
        if status["health_level"] == EngineHealth.ADVISORY:
            recs.append(dict(
                level="amber", 
                title="Advisory Watch | Statistical Baseline Trend Deviation", 
                fim_ref="FIM Table 101 (Statistical Control)",
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
                body=("All monitored thermodynamic parameters remain within acceptable OEM operating tolerances. Condition-corrected residuals are stable.\n\n"
                      "**Line Engineering Directives:** Continue routine ECTM logbook recording and periodic trend evaluations.")
            ))
    return recs

# ======================================================================================
# 10. PLOTLY VISUALIZATION ENGINE (CLEAN HOVERTEMPLATE UI)
# ======================================================================================
def make_trend_figure(df_engine: pd.DataFrame, engine_name: str) -> go.Figure:
    fig = go.Figure()
    
    # [UI FIX] Menghapus duplikasi info cuaca di hover agar tooltip tidak panjang menutupi grafik
    specs = [("Delta_T5", "\u0394 T5 (ITT) [\u00b0C]", "#B42318"), ("Delta_Ng", "\u0394 Ng [%]", "#003B6F"), ("Delta_Wf", "\u0394 Wf [PPH]", "#B54708")]
    for col, label, color in specs:
        fig.add_trace(go.Scatter(
            x=df_engine["Date"], y=df_engine[col], mode="lines+markers", name=label, 
            line=dict(color=color, width=2), marker=dict(size=5, color=color),
            hovertemplate="<b>%{y:+.2f}</b><extra></extra>"
        ))
        ma = df_engine[col].rolling(3, min_periods=1).mean().round(2)
        fig.add_trace(go.Scatter(x=df_engine["Date"], y=ma, mode="lines", name=f"{label} (3-cyc MA)", line=dict(color=color, width=1, dash="dot"), opacity=0.4, showlegend=False, hoverinfo="skip"))

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

    fig.add_hline(y=T5_WASH_C, line_dash="dash", line_color="#B54708", line_width=1, annotation_text="ITT +10°C (Wash Limit)", annotation_font=dict(size=10, color="#B54708"))
    fig.add_hline(y=T5_BORESCOPE_C, line_dash="dash", line_color="#B42318", line_width=1, annotation_text="ITT +15°C (Borescope Limit)", annotation_font=dict(size=10, color="#B42318"))

    fig.update_layout(
        title=dict(text=f"<b>Condition-Corrected Parameter Shift | Powerplant {engine_name}</b> ({len(df_engine)} Cycles Recorded)", font=dict(color=NAVY, size=14)),
        xaxis_title="Flight Date / Cycle", yaxis_title="Residual Delta from Baseline", hovermode="x unified", template="plotly_white", height=480,
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5, font=dict(size=11)), 
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(248,250,252,1)", margin=dict(l=40, r=20, t=70, b=80),
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=11, color="#475569")), 
        yaxis=dict(showgrid=True, gridcolor="#F1F5F9", zeroline=True, zerolinecolor="#94A3B8", zerolinewidth=1, tickfont=dict(size=11, color="#475569"))
    )
    return fig

def make_raw_vs_predicted(df_engine: pd.DataFrame, param: str, unit: str, color: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_engine["Date"], y=df_engine[param], mode="lines+markers", name=f"Actual {param}", line=dict(color=color, width=1.8), marker=dict(size=4)))
    fig.add_trace(go.Scatter(x=df_engine["Date"], y=df_engine[f"{param}_pred"], mode="lines", name="Predicted Baseline", line=dict(color="#64748B", width=1.5, dash="dash")))
    fig.update_layout(
        title=dict(text=f"<b>{param} | Actual vs. Condition Baseline ({unit})</b>", font=dict(color=NAVY, size=12)), 
        template="plotly_white", height=320, hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="center", x=0.5, font=dict(size=10)), 
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(248,250,252,1)", margin=dict(l=40, r=20, t=60, b=80),
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=10)), yaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=10))
    )
    return fig

# ======================================================================================
# 11. AUTOMATED EMAIL DISPATCH PROTOCOL (SSOT INTEGRATED) & NATIVE PDF EWO GENERATOR
# ======================================================================================
def send_engineering_notice(engine_id: str, status_dict: dict, report_body: str, recipients: list):
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

    if not live_mode:
        st.info(f"**[SYSTEM SIMULATION MODE]** SMTP secrets not configured in `.streamlit/secrets.toml`. "
                f"In production, notice for **{engine_id} ({status_label})** is dispatched to: `{', '.join(recipients)}`.")
        return True

    # [SSOT ANTI-CONTRADICTION] Evaluasi menggunakan status Enum absolut, bukan tebak-tebakan string
    if health == EngineHealth.CRITICAL:
        intro_text = (f"An abnormal thermodynamic parameter shift has been confirmed on Powerplant {engine_id}.\n"
                      "Please immediately review the computed residuals and OEM-referenced maintenance directives below:")
        subject_prefix = "[URGENT - CRITICAL]"
    elif health == EngineHealth.ADVISORY:
        intro_text = (f"A statistical baseline deviation (Advisory Watch) has been detected on Powerplant {engine_id}.\n"
                      "Please review the computed residuals and monitoring directives below:")
        subject_prefix = "[ADVISORY - WATCH]"
    else:
        intro_text = (f"Powerplant {engine_id} is operating normal within OEM thermodynamic tolerances.\n"
                      "Please find the routine condition logging evaluation and trend summary below:")
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
        f"Date Evaluated               : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
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
        return True
    except Exception as ssl_err:
        try:
            with smtplib.SMTP(smtp_server, 587, timeout=10) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            return True
        except Exception as tls_err:
            st.error(f"SMTP Transmission Failure (SSL Error: {ssl_err} | TLS Error: {tls_err})")
            return False

def generate_ewo_html(engine_id: str, status_label: str, status_dict: dict, recs: list) -> str:
    date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    latest_date = status_dict['latest']['Date'].strftime('%Y-%m-%d')
    rows_html = ""
    for r in recs:
        rows_html += f'<div style="border: 1px solid #CBD5E1; padding: 12px; margin-bottom: 10px; border-radius: 4px;"><b style="color: #003B6F; font-size: 14px;">[{r["fim_ref"]}] {r["title"]}</b><p style="font-size: 12px; color: #334155; margin-top: 6px; white-space: pre-line;">{r["body"]}</p><div style="margin-top: 10px; font-size: 11px; color: #64748B;">[ &nbsp; ] Action Completed &nbsp;&nbsp;&nbsp;&nbsp; Mech Sign: __________________ &nbsp;&nbsp;&nbsp;&nbsp; Date: ______________</div></div>'
    return f'<!DOCTYPE html><html><head><title>Engineering Work Order - {engine_id}</title><style>body {{ font-family: Arial, sans-serif; color: #0F172A; margin: 40px; }} .header {{ border-bottom: 3px solid #003B6F; padding-bottom: 10px; margin-bottom: 20px; }} .title {{ font-size: 20px; font-weight: bold; color: #003B6F; }} .subtitle {{ font-size: 12px; color: #64748B; font-weight: bold; letter-spacing: 1px; }} .meta-table {{ width: 100%; margin-bottom: 20px; border-collapse: collapse; }} .meta-table td, .meta-table th {{ padding: 6px; border: 1px solid #E2E8F0; font-size: 12px; }} .meta-table th {{ background: #F8FAFC; text-align: left; color: #475569; }} .section-title {{ font-size: 14px; font-weight: bold; color: #003B6F; margin-top: 20px; margin-bottom: 10px; text-transform: uppercase; }} .footer {{ margin-top: 40px; border-top: 1px solid #CBD5E1; padding-top: 15px; font-size: 11px; color: #64748B; display: flex; justify-content: space-between; }} .sign-box {{ width: 200px; border-top: 1px solid #000; text-align: center; margin-top: 40px; font-size: 11px; padding-top: 5px; }}</style></head><body><div class="header"><div class="title">PT. AIRFAST INDONESIA</div><div class="subtitle">TECHNICAL SERVICES DIVISION | ENGINEERING WORK ORDER (EWO)</div></div><table class="meta-table"><tr><th>Powerplant Serial / Position</th><td><b>{engine_id}</b></td><th>Document Type</th><td>ECTM Directive Order</td></tr><tr><th>Evaluation Timestamp</th><td>{date_str}</td><th>Latest Logbook Date</th><td>{latest_date}</td></tr><tr><th>System Status Classification</th><td colspan="3"><b style="color: {"#B42318" if "ABNORMAL" in status_label else "#003B6F"};">{status_label}</b></td></tr><tr><th>Thermodynamic Residuals</th><td colspan="3">Δ T5: <b>{status_dict["d_t5"]:+.1f} °C</b> (Slope: {status_dict["slope_t5"]:+.2f}) | Δ Ng: <b>{status_dict["d_ng"]:+.2f} %</b> | Δ Wf: <b>{status_dict["d_wf"]:+.1f} PPH</b></td></tr></table><div class="section-title">OEM Maintenance Directives & Action Checklist</div>{rows_html}<div style="display: flex; justify-content: space-between; margin-top: 30px;"><div class="sign-box">Licensed Aircraft Engineer (LAE)</div><div class="sign-box">Chief Inspector / Quality Control</div></div><div class="footer"><div>PT. AIRFAST Indonesia | DHC-6 / PT6A-34 Fleet Maintenance Program</div><div>Generated by Enterprise ECTM System</div></div></body></html>'

def generate_ewo_pdf(engine_id: str, status_label: str, status_dict: dict, recs: list) -> bytes:
    if not HAS_FPDF: return b""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(0, 59, 111)
    pdf.cell(0, 8, "PT. AIRFAST INDONESIA", ln=True, align="L")
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5, "TECHNICAL SERVICES DIVISION | ENGINEERING WORK ORDER (EWO)", ln=True, align="L")
    pdf.ln(4)
    
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(45, 7, "Powerplant Serial:", border=1)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(145, 7, f"  {engine_id}", border=1, ln=True)
    pdf.set_font("Arial", "", 9)
    pdf.cell(45, 7, "Status Classification:", border=1)
    if "ABNORMAL" in status_label: pdf.set_text_color(180, 35, 24)
    else: pdf.set_text_color(0, 59, 111)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(145, 7, f"  {status_label}", border=1, ln=True)
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Arial", "", 9)
    pdf.cell(45, 7, "Thermodynamic Residuals:", border=1)
    pdf.cell(145, 7, f"  Delta T5: {status_dict['d_t5']:+.1f} degC | Delta Ng: {status_dict['d_ng']:+.2f} % | Delta Wf: {status_dict['d_wf']:+.1f} PPH", border=1, ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(0, 59, 111)
    pdf.cell(0, 8, "OEM MAINTENANCE DIRECTIVES & ACTION CHECKLIST", ln=True)
    
    for r in recs:
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(0, 59, 111)
        pdf.cell(0, 6, f"[{r['fim_ref']}] {r['title']}", ln=True)
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(51, 65, 85)
        clean_body = r['body'].replace("**", "").replace("\u2192", "->").replace("\u0394", "Delta ")
        pdf.multi_cell(0, 4.5, clean_body)
        pdf.ln(1)
        pdf.set_font("Arial", "I", 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, "[   ] Action Completed    Mech Sign: __________________    Date: ______________", ln=True)
        pdf.ln(3)
        
    pdf.ln(8)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(95, 8, "Licensed Aircraft Engineer (LAE): ___________________", align="L")
    pdf.cell(95, 8, "Quality Control / Inspector: ___________________", align="R", ln=True)
    
    try:
        res = pdf.output()
        return res.encode("latin-1", errors="replace") if isinstance(res, str) else bytes(res)
    except Exception:
        return pdf.output(dest="S").encode("latin-1", errors="replace")

# ======================================================================================
# 11.5. FULL-SCREEN AUTHORIZATION GATE (LOGIN SECURITY GATE)
# ======================================================================================
if not st.session_state.get("logged_in", False):
    # Menyembunyikan sidebar bawaan streamlit saat berada di halaman login
    st.markdown("""
        <style>
            [data-testid="stSidebar"] { display: none !important; }
            [data-testid="collapsedControl"] { display: none !important; }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>" * 2, unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 1.4, 1])
    
    with col_l2:
        with st.container(border=True):
            st.markdown("<h2 style='text-align:center; color:#003B6F; margin-bottom:0px;'>PT. AIRFAST INDONESIA</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; color:#f0b73d; font-weight:700; font-size:0.8rem; letter-spacing:0.1em; margin-top:0px;'>TECHNICAL SERVICES DIVISION</p>", unsafe_allow_html=True)
            st.markdown("<hr style='margin: 10px 0px 20px 0px;'>", unsafe_allow_html=True)
            
            st.markdown("<p style='text-align:center; font-weight:600; color:#334155; font-size:0.95rem;'>Enterprise ECTM & Fleet Diagnostics Portal<br><span style='font-size:0.8rem; font-weight:400; color:#64748B;'>Please authenticate to access airworthiness telemetry and maintenance records.</span></p>", unsafe_allow_html=True)
            st.write("")
            
            with st.form("fullscreen_login_form", clear_on_submit=False):
                input_email = st.text_input("Corporate Email Address", placeholder="user@airfastindonesia.com").strip()
                input_password = st.text_input("Password", type="password", placeholder="••••••••")
                
                st.write("")
                c_btn1, c_btn2 = st.columns(2)
                with c_btn1:
                    btn_login = st.form_submit_button("🔐 Login to Portal", type="primary", use_container_width=True)
                with c_btn2:
                    btn_guest = st.form_submit_button("👤 Continue as Guest", use_container_width=True)
                    
                if btn_login:
                    if input_email in USER_DATABASE and USER_DATABASE[input_email]["password"] == input_password:
                        user_info = USER_DATABASE[input_email]
                        st.session_state["logged_in"] = True
                        st.session_state["user_email"] = input_email
                        st.session_state["user_name"] = user_info["name"]
                        st.session_state["user_role"] = user_info["role"]
                        st.success("Authorization successful! Redirecting to dashboard...")
                        st.rerun()
                    else:
                        st.error("❌ Invalid Email or Password. Access denied under CASR Part 135.")
                        
                if btn_guest:
                    st.session_state["logged_in"] = True
                    st.session_state["user_email"] = "guest.auditor@airfast.com"
                    st.session_state["user_name"] = "External Auditor / Guest"
                    st.session_state["user_role"] = "Guest / Viewer"
                    st.rerun()
            
            st.markdown("<hr style='margin: 15px 0px 10px 0px;'>", unsafe_allow_html=True)
            st.caption("🔒 **Security Advisory:** Authorized personnel only. System activity is continuously monitored and logged in compliance with Airfast Corporate Quality Management System (CQMS).")
            
    # ---> MAGISNYA DI SINI: Menghentikan eksekusi kode di bawahnya sampai login berhasil! <---
    st.stop()

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

# --------------------------------------------------------------------------------------
# USER PROFILE CARD & LOGOUT BUTTON
# --------------------------------------------------------------------------------------

role_badge_style = {
    "Chief Engineer / Admin": ("#F0FDF4", "#166534", "#BBF7D0", "Level 3: Full System Authority"),
    "Powerplant Engineer": ("#FFFBEB", "#92400E", "#FDE68A", "Level 2: Diagnostics & Analytics"),
    "Data Entry Officer": ("#EFF6FF", "#1E40AF", "#BFDBFE", "Level 1: Telemetry Ingestion"),
    "Guest / Viewer": ("#F1F5F9", "#334155", "#CBD5E1", "Level 0: Read-Only Overview")
}
bg_c, txt_c, brd_c, role_desc = role_badge_style.get(st.session_state["user_role"], ("#F1F5F9", "#334155", "#CBD5E1", "Unknown Role"))

st.sidebar.markdown(f"""
<div style="background-color: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); padding: 12px 14px; border-radius: 6px; margin-bottom: 12px;">
    <span style="color: #f0b73d !important; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; display: block;">👤 LOGGED IN AS</span>
    <span style="color: #FFFFFF !important; font-size: 0.95rem; font-weight: 700; display: block; margin-top: 2px;">{st.session_state['user_name']}</span>
    <span style="color: #94A3B8 !important; font-size: 0.75rem; display: block; margin-bottom: 8px;">{st.session_state['user_email']}</span>
    <div style="background-color: {bg_c}; border: 1px solid {brd_c}; padding: 4px 8px; border-radius: 4px; display: inline-block; width: 100%; text-align: center;">
        <span style="color: {txt_c} !important; font-size: 0.68rem; font-weight: 700;">🔒 {role_desc}</span>
    </div>
</div>
""", unsafe_allow_html=True)

if st.sidebar.button("🚪 Logout Portal", use_container_width=True):
    st.session_state["logged_in"] = False
    st.session_state["user_email"] = ""
    st.session_state["user_name"] = "Guest Viewer"
    st.session_state["user_role"] = "Guest / Viewer"
    st.session_state["active_menu"] = "Home (Fleet Matrix)"
    st.rerun()

st.sidebar.markdown("---")

# --------------------------------------------------------------------------------------
# DYNAMIC MENU FILTERING BERDASARKAN ROLE
# --------------------------------------------------------------------------------------
all_menus = [
    "Home (Fleet Matrix)", 
    "Data Collection & Setup", 
    "Trend Analysis & RUL", 
    "Logbook & Defect Correlator", 
    "Recommendations & Dispatch"
]

if st.session_state["user_role"] == "Guest / Viewer":
    allowed_menus = ["Home (Fleet Matrix)"]
elif st.session_state["user_role"] == "Data Entry Officer":
    allowed_menus = ["Home (Fleet Matrix)", "Data Collection & Setup"]
elif st.session_state["user_role"] == "Powerplant Engineer":
    allowed_menus = ["Home (Fleet Matrix)", "Data Collection & Setup", "Trend Analysis & RUL", "Logbook & Defect Correlator"]
else:
    allowed_menus = all_menus

if st.session_state["active_menu"] not in allowed_menus:
    st.session_state["active_menu"] = allowed_menus[0]

menu_selection = st.sidebar.radio(
    "Navigation Menu",
    allowed_menus,
    index=allowed_menus.index(st.session_state["active_menu"]) if st.session_state["active_menu"] in allowed_menus else 0,
    key="active_menu_radio",
    label_visibility="collapsed",
)

st.session_state["active_menu"] = menu_selection

st.sidebar.markdown("<br>" * 4, unsafe_allow_html=True)
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

for col in REQUIRED_COLUMNS[2:] + [c for c in OPTIONAL_COLUMNS if c in df_raw.columns]:
    df_raw[col] = pd.to_numeric(df_raw[col], errors="coerce")

df_raw["Date"] = pd.to_datetime(df_raw["Date"], errors="coerce")

_rows_before_clean = len(df_raw)
df_raw = df_raw.dropna(subset=REQUIRED_COLUMNS).sort_values("Date")
_rows_dropped = _rows_before_clean - len(df_raw)
if _rows_dropped > 0:
    st.sidebar.warning(
        f"⚠️ {_rows_dropped} logbook row(s) ignored - invalid or missing "
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
# 14. PAGE 1: HOME (FLEET MATRIX & UTILIZATION INTEGRATION)
# ======================================================================================
if menu_selection == "Home (Fleet Matrix)":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Engine Condition Trend Monitoring Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='color:#475569; font-size:1.05rem; font-weight:500; margin-top:0px;'>Technical Services & Fleet Maintenance | DHC-6 Twin Otter / PT6A-34</h3>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    if not st.session_state.get("util_is_real", False):
        st.info("ℹ️ RUL calendar dates below use a **simulated** flight-utilization dataset (no real "
                "'Flight Utilization DHC6-400.xlsx' found). Upload the real file in Data Collection & Setup "
                "for accurate projections.", icon="ℹ️")

    fleet_summary_data = []
    for eng in engines_available:
        df_sub = df_raw[df_raw["Engine"] == eng].copy()
        if len(df_sub) >= 2:
            df_sub_proc = compute_engine_trend(df_sub, int(baseline_n_input), use_correction)
            st_sub = build_status(df_sub_proc, df_util_current)
            stat_lbl = "CRITICAL" if st_sub["health_level"] == EngineHealth.CRITICAL else ("ADVISORY" if st_sub["health_level"] == EngineHealth.ADVISORY else "NORMAL")
            rul_val = st_sub["rul_cycles"]
            accel_marker = " ⚠ accelerating" if st_sub["rul_is_linear_caution"] else ""
            rul_str = "Stable (>100 Cycles)" if rul_val >= 999 else f"{rul_val} Cycles ({st_sub['proj_date']}){accel_marker}"
            
            fleet_summary_data.append({
                "Powerplant Serial / Position": eng,
                "Status": stat_lbl,
                "Latest Δ T5": f"{st_sub['d_t5']:+.1f} °C",
                "T5 Slope": f"{st_sub['slope_t5']:+.2f} °C/cyc",
                "Latest Δ Ng": f"{st_sub['d_ng']:+.2f} %",
                "Predictive RUL (Borescope)": rul_str
            })
            
    df_fleet_matrix = pd.DataFrame(fleet_summary_data)
    st.dataframe(df_fleet_matrix, use_container_width=True, hide_index=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Fleet Engines", len(engines_available))
    c2.metric("Logbook Utilization Rows", len(df_util_current) if not df_util_current.empty else "0 (Sim)")
    c3.metric("Defect Reports (PIREP/MAREP)", len(df_rep_current) if not df_rep_current.empty else "0 (Sim)")
    critical_count = sum(1 for item in fleet_summary_data if item["Status"] == "CRITICAL")
    c4.metric("Fleet Alert Status", f"{critical_count} CRITICAL" if critical_count > 0 else "NORMAL")
    
    st.markdown("---")
    if not df_util_current.empty:
        st.markdown("<h3 style='color:#003B6F; margin-bottom:4px;'>Airframe Utilization Summary (Total FH / FC)</h3>", unsafe_allow_html=True)
        st.caption("Real-world accumulation rate from Flight Utilization dataset used to project calendar maintenance dates.")
        df_u_summary = df_util_current.groupby("Registration")[["FH", "FC"]].sum().reset_index()
        df_u_summary["Avg FC / Day"] = df_u_summary["Registration"].apply(lambda r: round(get_aircraft_utilization_rate(r, df_util_current), 1))
        st.dataframe(df_u_summary, use_container_width=True, hide_index=True)

        # =========================================================================
        # ⬇️ PENAMBAHAN KODE REVISI POIN 4 (GRAFIK UTILITAS ARMADA) ⬇️
        # =========================================================================
        st.write("") # Spasi vertikal tipis
        
        # Membuat grafik batang berdampingan dari dataframe df_u_summary yang sudah dihitung di atas
        fig_util = px.bar(
            df_u_summary,
            x='Registration',
            y=['FH', 'FC'],
            barmode='group',
            labels={
                'value': 'Total Value',
                'Registration': 'Aircraft Registration',
                'variable': 'Metric Type'
            },
            color_discrete_map={
                'FH': '#003B6F',  # Navy Airfast (Jam Terbang)
                'FC': '#f0b73d'   # Gold Airfast (Siklus Terbang)
            },
            height=380
        )

        fig_util.update_layout(
            title=dict(
                text="<b>Fleet Utilization Balancing (Flight Hours vs. Flight Cycles)</b>",
                font=dict(color="#003B6F", size=13)
            ),
            legend=dict(
                title='Metric',
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            hovermode="x unified",
            margin=dict(l=20, r=20, t=50, b=20),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        fig_util.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.15)')

        st.plotly_chart(fig_util, use_container_width=True)
        # =========================================================================
        # ⬆️ BATAS KODE PENAMBAHAN POIN 4 ⬆️
        # =========================================================================

# ======================================================================================
# 15. PAGE 2: DATA COLLECTION & CONFIGURATION
# ======================================================================================
elif menu_selection == "Data Collection & Setup":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Data Ingestion & System Setup</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>Manage ECTM logbooks, airframe utilization files, and pilot/maintenance defect reports.</p>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    tab_ectm, tab_util, tab_rep = st.tabs(["1. ECTM Logbook (.csv)", "2. Flight Utilization (.xlsx)", "3. Maintenance Reports (.xlsx)"])
    
    # -------------------------------------------------------------------------
    # TAB 1: ECTM LOGBOOK (PERFORMANCE TELEMETRY)
    # -------------------------------------------------------------------------
    with tab_ectm:
        # [POIN 5 REVISI] OPSI A: DAILY MANUAL ENTRY FORM (ECTM PERFORMANCE)
        with st.expander("✍️ Add Daily Engine Performance Record (Manual Entry)", expanded=False):
            st.caption("Log daily engine telemetry directly from pilot flight logbook without uploading a CSV.")
            with st.form("form_manual_ectm", clear_on_submit=True):
                col_f1, col_f2, col_f3, col_f4 = st.columns(4)
                with col_f1:
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
                
                submitted_ectm = st.form_submit_button("💾 Save Daily ECTM Record", type="primary", use_container_width=True)
                if submitted_ectm:
                    new_row = pd.DataFrame([{
                        "Date": pd.to_datetime(m_date), "Engine": m_eng, "Press_Alt": float(m_alt),
                        "IOAT": float(m_ioat), "IAS": float(m_ias), "TQ": float(m_tq), "Np": int(m_np),
                        "T5": float(m_t5), "Ng": float(m_ng), "Wf": float(m_wf),
                        "Oil_Temp": float(m_otemp), "Oil_Press": float(m_opress)
                    }])
                    st.session_state["df_data"] = pd.concat([st.session_state["df_data"], new_row], ignore_index=True)
                    st.success(f"Successfully logged daily performance telemetry for {m_eng}!")
                    st.rerun()

        # OPSI B: BULK UPLOAD (.CSV) & AUDIT EDITING
        col_up, col_dl = st.columns([3, 1])
        with col_up:
            up_ectm = st.file_uploader("Upload Engine Logbook File (.csv)", type=["csv"], key="up_ectm_file")
            if up_ectm is not None:
                new_df = pd.read_csv(up_ectm)
                missing, _ = validate_columns(new_df)
                if not missing:
                    st.session_state["df_data"] = new_df
                    st.success("ECTM Logbook ingested successfully.")
                    st.rerun()
        with col_dl:
            st.write("")
            st.write("")
            st.download_button("Download CSV Template", data=csv_template(), file_name="AIRFAST_ECTM_Template.csv", mime="text/csv", use_container_width=True)
        
        audit_alerts = run_data_quality_audit(st.session_state["df_data"])
        if audit_alerts:
            with st.expander("⚠️ Data Quality Audit Alerts Detected (Click to expand)", expanded=True):
                for alert in audit_alerts:
                    st.warning(alert)

        st.session_state["df_data"] = st.data_editor(st.session_state["df_data"], num_rows="dynamic", use_container_width=True, key="ed_ectm_ui")

    # -------------------------------------------------------------------------
    # TAB 2: FLIGHT UTILIZATION (FH / FC TRACKING)
    # -------------------------------------------------------------------------
    with tab_util:
        # [POIN 5 REVISI] OPSI A: DAILY MANUAL ENTRY FORM (FLIGHT UTILIZATION)
        with st.expander("✍️ Add Daily Flight Utilization Record (Manual Entry)", expanded=False):
            st.caption("Log daily airframe flight hours (FH) and flight cycles (FC) to update RUL calendar projections.")
            with st.form("form_manual_util", clear_on_submit=True):
                col_u1, col_u2, col_u3 = st.columns(3)
                with col_u1:
                    u_reg = st.selectbox("Aircraft Registration", ["PK-OAM", "PK-OCH", "PK-OCG", "PK-OCI", "PK-OCF"])
                    u_date = st.date_input("Work Date", value=datetime.now())
                with col_u2:
                    u_fh = st.number_input("Flight Hours (FH)", min_value=0.0, max_value=24.0, value=2.5, step=0.1)
                    u_fc = st.number_input("Flight Cycles (FC)", min_value=1, max_value=30, value=4, step=1)
                with col_u3:
                    u_bh = st.number_input("Block Hours (BH)", min_value=0.0, max_value=24.0, value=2.8, step=0.1)
                    u_from = st.text_input("From Sector", value="WAY").upper()
                    u_to = st.text_input("To Sector", value="TIM").upper()
                
                submitted_util = st.form_submit_button("💾 Save Utilization Record", type="primary", use_container_width=True)
                if submitted_util:
                    new_u_row = pd.DataFrame([{
                        "Registration": u_reg, "Work (Date)": pd.to_datetime(u_date),
                        "FH": float(u_fh), "FC": int(u_fc), "Block Hours": float(u_bh),
                        "From": u_from, "To": u_to
                    }])
                    st.session_state["df_util"] = pd.concat([st.session_state["df_util"], new_u_row], ignore_index=True)
                    st.session_state["util_is_real"] = True
                    st.success(f"Successfully logged utilization for {u_reg} ({u_fh} FH / {u_fc} FC)!")
                    st.rerun()

        # OPSI B: BULK UPLOAD (.XLSX)
        st.caption("Upload Flight Utilization Excel file (e.g., `Flight Utilization DHC6-400.xlsx`) to synchronize RUL calendar projections.")
        up_util = st.file_uploader("Upload Utilization File (.xlsx)", type=["xlsx"], key="up_util_file")
        if up_util is not None:
            df_u_new = pd.read_excel(up_util)
            df_u_new['Work (Date)'] = pd.to_datetime(df_u_new['Work (Date)'], errors='coerce')
            st.session_state["df_util"] = df_u_new.dropna(subset=['Registration', 'Work (Date)'])
            st.session_state["util_is_real"] = not st.session_state["df_util"].empty
            st.success("Flight Utilization dataset synchronized!")
            st.rerun()
        if not st.session_state.get("util_is_real", False):
            st.warning("⚠️ No real utilization file found on disk. RUL calendar projections are currently using a "
                       "**simulated** utilization dataset - upload the real file above for accurate dates.")
        st.dataframe(st.session_state["df_util"].head(100), use_container_width=True)

    # -------------------------------------------------------------------------
    # TAB 3: MAINTENANCE REPORTS (PIREP / MAREP DEFECTS)
    # -------------------------------------------------------------------------
    with tab_rep:
        # [POIN 5 REVISI] OPSI A: DAILY MANUAL ENTRY FORM (DEFECT REPORTING)
        with st.expander("✍️ Add Pilot / Maintenance Defect Report (Manual Entry)", expanded=False):
            st.caption("Log pilot defect reports (PIREP) or maintenance actions (MAREP) to feed the Defect Correlator.")
            with st.form("form_manual_rep", clear_on_submit=True):
                col_r1, col_r2, col_r3 = st.columns([1, 1, 1])
                with col_r1:
                    r_aml = st.text_input("AML / Logbook No", placeholder="e.g., OAM-2026-015").upper()
                    r_date = st.date_input("Report Date", value=datetime.now())
                with col_r2:
                    r_reg = st.selectbox("Registration", ["PK-OAM", "PK-OCH", "PK-OCG", "PK-OCI", "PK-OCF"], key="rep_reg")
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

                submitted_rep = st.form_submit_button("💾 Save Defect / Maintenance Report", type="primary", use_container_width=True)
                if submitted_rep:
                    new_r_row = pd.DataFrame([{
                        "AML No": r_aml if r_aml else f"{r_reg}-MANUAL", "Date": pd.to_datetime(r_date),
                        "Registration": r_reg, "ATA": int(r_ata),
                        "Note / Report": r_note if r_note else "No description provided.",
                        "Corrective Action": r_action if r_action else "Pending maintenance action.",
                        "Position": r_pos, "P/N Off": r_pn_off, "S/N Off": r_sn_off,
                        "P/N On": r_pn_on, "S/N On": r_sn_on
                    }])
                    st.session_state["df_rep"] = pd.concat([st.session_state["df_rep"], new_r_row], ignore_index=True)
                    st.session_state["df_rep"] = process_maintenance_reports(st.session_state["df_rep"])
                    st.session_state["rep_is_real"] = True
                    st.success(f"Successfully logged maintenance report [{r_aml}] for {r_reg}!")
                    st.rerun()

        # OPSI B: BULK UPLOAD (.XLSX)
        st.caption("Upload Pilot & Maintenance Report Excel file (e.g., `Pilot & Maintenance Report DHC6-400.xlsx`) to power the Defect Correlator.")
        up_rep = st.file_uploader("Upload Maintenance Report File (.xlsx)", type=["xlsx"], key="up_rep_file")
        if up_rep is not None:
            df_r_new = pd.read_excel(up_rep)
            st.session_state["df_rep"] = process_maintenance_reports(df_r_new)
            st.session_state["rep_is_real"] = not st.session_state["df_rep"].empty
            st.success("Maintenance Reports synchronized & mapped!")
            st.rerun()
        if not st.session_state.get("rep_is_real", False):
            st.warning("⚠️ No real maintenance report file found on disk. The Defect Correlator is currently "
                       "showing **simulated** PIREP/MAREP entries - upload the real file above.")
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
# 16. PAGE 3: TREND ANALYSIS & PREDICTIVE RUL
# ======================================================================================
elif menu_selection == "Trend Analysis & RUL":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Thermodynamic Trend Analysis</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>Active Powerplant: <b style='color:#003B6F; background:#EFF4FA; padding:2px 8px; border-radius:4px; border:1px solid #CBD5E1;'>{selected_engine}</b> | Condition-Corrected Residual Shifts</p>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    if df_engine.attrs.get("regression_downgraded", False):
        st.warning("⚠️ **Mathematical Warning:** Reference Baseline Cycles terpilih tidak cukup untuk menjalankan regresi multivariabel penuh pada parameter atmosfer. Normalisasi sementara diatur ke mode Rata-Rata (Arithmetic Mean). Disarankan menaikkan Baseline Cycles ke minimal **6 siklus** di menu Setup.")

    col_chart, col_status = st.columns([3, 1])
    with col_chart:
        st.plotly_chart(make_trend_figure(df_engine, selected_engine), use_container_width=True)
        with st.expander("View Raw Observations vs. Predicted Condition Baseline"):
            cc1, cc2, cc3 = st.columns(3)
            with cc1: st.plotly_chart(make_raw_vs_predicted(df_engine, "T5", "\u00b0C", "#B42318"), use_container_width=True)
            with cc2: st.plotly_chart(make_raw_vs_predicted(df_engine, "Ng", "%", "#003B6F"), use_container_width=True)
            with cc3: st.plotly_chart(make_raw_vs_predicted(df_engine, "Wf", "PPH", "#B54708"), use_container_width=True)

    with col_status:
        st.markdown("<h3 style='margin-bottom:8px; color:#003B6F;'>Powerplant Status</h3>", unsafe_allow_html=True)
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
            <div class="rul-title">Predictive RUL (Borescope Limit)</div>
            <div class="rul-val">{rul_display}</div>
            <div class="rul-sub">{date_display}</div>
            <div class="rul-sub" style="color:{rul_caution_color}; margin-top:4px;">⚠ {status['rul_confidence']}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.caption("Diagnostic Event Flags:")
        if status["isolated_t5"] or status["isolated_ng"]: st.write("▪ Isolated single-cycle shift detected")
        if status["sustained_t5"]: st.write("▪ Sustained upward T5 degradation confirmed")
        if status["alarm_wash"]: st.write("▪ ITT +10°C wash limit exceeded")
        if status["alarm_borescope_t5"] or status["alarm_borescope_ng"]: st.write("▪ OEM borescope threshold breached")
        if not (status["isolated_t5"] or status["isolated_ng"] or status["sustained_t5"] or status["alarm_wash"] or status["alarm_borescope_t5"] or status["alarm_borescope_ng"]):
            st.write("▪ No active anomalies detected")
            
        st.markdown("---")
        st.button(
            "🔗 Cross-Check Logbook Defect Correlator", 
            use_container_width=True,
            on_click=navigate_to_menu,
            args=("Logbook & Defect Correlator", status["reg_prefix"])
        )

    st.markdown("---")
    show_cols = [c for c in ["Date", "Engine", "T5", "Delta_T5", "Ng", "Delta_Ng", "Wf", "Delta_Wf_pct"] if c in df_engine.columns]
    st.dataframe(df_engine[show_cols].sort_values("Date", ascending=False), use_container_width=True, height=240)

# ======================================================================================
# 17. PAGE 4: LOGBOOK & DEFECT CORRELATOR
# ======================================================================================
elif menu_selection == "Logbook & Defect Correlator":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Maintenance Logbook & Defect Correlator</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>Cross-reference PIREP / MAREP defect notes and component replacement history against ECTM trends.</p>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    if df_rep_current.empty:
        st.warning("No Pilot & Maintenance Report dataset loaded. Please upload `Pilot & Maintenance Report DHC6-400.xlsx` in Data Collection.")
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

    df_filtered = df_rep_current[df_rep_current['Registration'] == sel_reg]
    if sel_ata != "ALL ATA CHAPTERS":
        df_filtered = df_filtered[df_filtered['ATA_Desc'] == sel_ata]
    if search_kw:
        kw = search_kw.lower()
        df_filtered = df_filtered[df_filtered['Note / Report'].astype(str).str.lower().str.contains(kw) | 
                                  df_filtered['Corrective Action'].astype(str).str.lower().str.contains(kw)]

    st.markdown(f"**Found {len(df_filtered)} logged defect report(s) matching criteria for {sel_reg}:**")
    
    if df_filtered.empty:
        st.info("No maintenance reports found matching the selected filter criteria.")
    else:
        for idx, row in df_filtered.head(15).iterrows():
            with st.container(border=True):
                c_head1, c_head2, c_head3 = st.columns([2, 1, 1])
                c_head1.markdown(f"**AML No:** `{row.get('AML No', 'N/A')}` | **ATA:** `{row.get('ATA_Desc', 'N/A')}`")
                c_head2.markdown(f"**Date:** `{row['Date'].strftime('%Y-%m-%d') if pd.notnull(row['Date']) else 'N/A'}`")
                c_head3.markdown(f"**Position:** `{row.get('Position', 'General')}`")
                
                st.markdown(f"**Defect Reported (PIREP/MAREP):**\n> {row.get('Note / Report', 'No description.')}")
                st.markdown(f"**Corrective Action Taken:**\n> {row.get('Corrective Action', 'Pending action.')}")
                
                pn_off, pn_on = row.get('P/N Off'), row.get('P/N On')
                if pd.notnull(pn_off) or pd.notnull(pn_on):
                    st.caption(f"🔧 Component Change Tracking -> P/N Off: `{pn_off}` (S/N: `{row.get('S/N Off', '-')}`) ➔ P/N On: `{pn_on}` (S/N: `{row.get('S/N On', '-')}`)")

# ======================================================================================
# 18. PAGE 5: RECOMMENDATIONS, EWO EXPORT & DISPATCH
# ======================================================================================
elif menu_selection == "Recommendations & Dispatch":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Maintenance Recommendations & Dispatch</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>Active Powerplant: <b style='color:#003B6F; background:#EFF4FA; padding:2px 8px; border-radius:4px; border:1px solid #CBD5E1;'>{selected_engine}</b> | P&WC PT6A-34 FIM (Rev 75.0)</p>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    overall_status_label = status["status_label"]
    st.markdown(f"**Observed Shift Vector:** `ΔT5: {status['shift_t5']}` | `ΔNg: {status['shift_ng']}` | `ΔWf: {status['shift_wf']}` &nbsp;&nbsp;|&nbsp;&nbsp; **System Classification:** **{overall_status_label}**")
    st.markdown("<br>", unsafe_allow_html=True)

    level_fn = {"red": st.error, "amber": st.warning, "green": st.success}
    for rec in recommendations:
        with st.container(border=True):
            level_fn[rec["level"]](f"**{rec['title']}**")
            st.caption(f"OEM Manual Reference: {rec['fim_ref']}")
            st.markdown(rec["body"])

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
    for rec in recommendations: report_lines += [f"[{rec['fim_ref']}] {rec['title']}", rec["body"], ""]
    
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
    st.markdown("<h3 style='color:#003B6F; margin-bottom:4px;'>Automated Emergency Dispatch Protocol</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color:#475569; font-size:0.88rem; margin-bottom:14px;'>Transmit urgent engineering evaluations directly to responsible Fleet Managers and Maintenance Control Center (MCC).</p>", unsafe_allow_html=True)
    
    with st.container(border=True):
        col_em1, col_em2 = st.columns([3, 1])
        with col_em1:
            target_emails = st.text_input("Recipient Email Addresses (comma-separated)", value="chief.engineers@airfastindonesia.com, mcc.duty@airfastindonesia.com")
        with col_em2:
            st.write("")
            st.write("")
            if st.button("Dispatch Notice to MCC", type="primary", use_container_width=True):
                with st.spinner("Transmitting engineering notice via secure SMTP..."):
                    recipients_list = [e.strip() for e in target_emails.split(",") if e.strip()]
                    success = send_engineering_notice(selected_engine, status, "\n".join(report_lines), recipients_list)
                    if success: st.success("Engineering Notice dispatched successfully to target recipients.")