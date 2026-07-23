"""
========================================================================================
 ENTERPRISE ECTM & FLEET MAINTENANCE CONTROL SYSTEM
 PT. AIRFAST INDONESIA | DHC-6 TWIN OTTER / P&WC PT6A-34 FLEET
========================================================================================
 Architecture : Standalone Enterprise SaaS (Streamlit / Plotly / Multi-Linear Regression)
 Compliance   : P&WC PT6A-34 Fault Isolation Manual (P/N 3021242, Rev 75.0)
 Integration  : Engine Thermodynamic Residuals + Real-World Airframe Utilization Tracking
                + Pilot & Maintenance Defect Logbook Correlator (PIREP/MAREP/ATA Mapping).
========================================================================================
"""

import io
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ======================================================================================
# 1. PAGE CONFIGURATION & SYSTEM INITIALIZATION
# ======================================================================================
st.set_page_config(
    page_title="AIRFAST ECTM | Maintenance Control System",
    page_icon="▪️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ======================================================================================
# 2. OEM CONSTANTS & FIM THRESHOLD MATRIX
# Source: PT6A-34 Fault Isolation Manual, P/N 3021242, Rev 75.0
# ======================================================================================
SHIFT_T5_C = 5.0        
SHIFT_NG_PCT = 0.5      
SHIFT_WF_PCT = 2.0      

T5_WASH_C = 10.0                # +10.0 °C ITT shift -> Compressor Performance Wash
T5_BORESCOPE_C = 15.0           # +15.0 °C ITT shift -> Mandatory Hot-Section Borescope
NG_BORESCOPE_LOW_PCT = -1.0     # -1.0% Ng drop      -> Borescope Advisory Trigger
NG_BORESCOPE_HIGH_PCT = -1.5    # -1.5% Ng drop      -> Mandatory Compressor Borescope

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
    [data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display: none !important; }
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
# 4. SESSION STATE MANAGEMENT (DECOUPLED PERSISTENT STORAGE)
# ======================================================================================
if "active_menu" not in st.session_state:
    st.session_state["active_menu"] = "Home (Fleet Matrix)"
if "target_use_correction" not in st.session_state:
    st.session_state["target_use_correction"] = True
if "target_baseline_n" not in st.session_state:
    st.session_state["target_baseline_n"] = 3
if "target_engine" not in st.session_state:
    st.session_state["target_engine"] = None

# ======================================================================================
# 5. DATA INGESTION & SYNTHESIS MODULE
# ======================================================================================
def init_all_datasets():
    rng = np.random.default_rng(42)
    rows = []
    fleet_ectm = [
        ("PK-OAM | LH (SN: PC-E101)", 0.42, -0.015, 624.0, 91.50, 288.0), # Critical T5 drift -> Wash Alarm
        ("PK-OAM | RH (SN: PC-E102)", 0.04, -0.002, 625.5, 91.60, 290.5), # Stable
        ("PK-OCH | LH (SN: PC-E103)", -0.02, 0.001, 623.0, 91.45, 289.0), # Stable
        ("PK-OCH | RH (SN: PC-E104)", 0.12, -0.005, 626.0, 91.55, 291.0), # Advisory Watch (Statistical Breach)
        ("PK-OCG | LH (SN: PC-E105)", 0.05, 0.000, 624.5, 91.50, 289.5), # Advisory Watch (Statistical Breach)
    ]
    for eng_id, t5_drift, ng_drift, base_t5, base_ng, base_wf in fleet_ectm:
        for i in range(35):
            ioat = 12.0 + rng.normal(0, 1.2)
            alt = 11000 + rng.normal(0, 200)
            tq = 42.0 + rng.normal(0, 0.6)
            t5 = base_t5 + (t5_drift * i) + 0.38 * (ioat - 12.0) + rng.normal(0, 0.5)
            ng = base_ng + (ng_drift * i) - 0.012 * (ioat - 12.0) + rng.normal(0, 0.06)
            wf = base_wf + 0.85 * (ioat - 12.0) + (0.18 * i if "PC-E101" in eng_id else 0.02 * i) + rng.normal(0, 0.7)
            rows.append(dict(
                Date=pd.Timestamp("2026-06-01") + pd.Timedelta(days=i),
                Engine=eng_id, Press_Alt=round(alt, 0), IOAT=round(ioat, 1),
                IAS=round(135.0 + rng.normal(0, 1.2), 1), TQ=round(tq, 1), Np=75,
                T5=round(t5, 1), Ng=round(ng, 2), Wf=round(wf, 1),
                Oil_Temp=round(72.5 + rng.normal(0, 0.6), 1), Oil_Press=round(91.0 + rng.normal(0, 0.5), 1),
            ))
    df_ectm = pd.DataFrame(rows)

    util_file = "Flight Utulization DHC6-400.xlsx"
    if os.path.exists(util_file):
        try:
            df_util = pd.read_excel(util_file)
            df_util['Work (Date)'] = pd.to_datetime(df_util['Work (Date)'], errors='coerce')
            df_util = df_util.dropna(subset=['Registration', 'Work (Date)']).sort_values('Work (Date)')
        except Exception:
            df_util = pd.DataFrame(columns=['Work (Date)', 'Registration', 'FH', 'FC', 'Block Hours', 'From', 'To'])
    else:
        df_util = pd.DataFrame(columns=['Work (Date)', 'Registration', 'FH', 'FC', 'Block Hours', 'From', 'To'])

    rep_file = "Pilot & Maintenance Report DHC6-400.xlsx"
    if os.path.exists(rep_file):
        try:
            df_rep = pd.read_excel(rep_file)
            df_rep['Date'] = pd.to_datetime(df_rep['Date'], errors='coerce')
            df_rep = df_rep.dropna(subset=['Note / Report', 'Date']).sort_values('Date', ascending=False)
            
            def ext_reg(val):
                if not isinstance(val, str): return "UNKNOWN"
                p = val.split('-')[0]
                if p in ['OAM', 'OCH', 'OCI', 'OCG', 'OCF']: return f"PK-{p}"
                return p
            df_rep['Registration'] = df_rep['AML No'].apply(ext_reg)
            
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
            df_rep['ATA_Desc'] = df_rep['ATA'].map(lambda x: ata_map.get(int(x) if pd.notnull(x) and str(x).isdigit() else x, f"ATA {x} - General"))
        except Exception:
            df_rep = pd.DataFrame(columns=['AML No', 'Date', 'Registration', 'ATA', 'ATA_Desc', 'Note / Report', 'Corrective Action', 'Position', 'P/N Off', 'P/N On'])
    else:
        df_rep = pd.DataFrame(columns=['AML No', 'Date', 'Registration', 'ATA', 'ATA_Desc', 'Note / Report', 'Corrective Action', 'Position', 'P/N Off', 'P/N On'])

    return df_ectm, df_util, df_rep

if "df_data" not in st.session_state or "df_util" not in st.session_state or "df_rep" not in st.session_state:
    e_df, u_df, r_df = init_all_datasets()
    st.session_state["df_data"] = e_df
    st.session_state["df_util"] = u_df
    st.session_state["df_rep"] = r_df

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
# 6. THERMODYNAMIC LEAST-SQUARES REGRESSION & NORMALIZATION
# ======================================================================================
def fit_correction_model(df_baseline: pd.DataFrame, predictors: list, target: str):
    usable = [p for p in predictors if df_baseline[p].std(ddof=0) > 1e-6]
    if len(usable) == 0 or len(df_baseline) < len(usable) + 2:
        mean_val = df_baseline[target].mean()
        return {"mode": "mean", "predictors": [], "coef": np.array([mean_val])}
    X = df_baseline[usable].astype(float).values
    X = np.column_stack([np.ones(len(X)), X])
    y = df_baseline[target].astype(float).values
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {"mode": "regression", "predictors": usable, "coef": coef}

def apply_correction_model(model: dict, df: pd.DataFrame) -> np.ndarray:
    if model["mode"] == "mean":
        return np.full(len(df), model["coef"][0])
    X = df[model["predictors"]].astype(float).values
    X = np.column_stack([np.ones(len(X)), X])
    return X @ model["coef"]

def compute_engine_trend(df_engine: pd.DataFrame, baseline_n: int, use_correction: bool):
    df_engine = df_engine.sort_values("Date").reset_index(drop=True)
    n = max(2, min(baseline_n, len(df_engine)))
    df_baseline = df_engine.iloc[:n]
    predictors = [c for c in CORRECTION_CANDIDATES if c in df_engine.columns] if use_correction else []
    models = {}
    for target in ["T5", "Ng", "Wf"]:
        models[target] = fit_correction_model(df_baseline, predictors, target)
        df_engine[f"{target}_pred"] = apply_correction_model(models[target], df_engine)
        df_engine[f"Delta_{target}"] = df_engine[target] - df_engine[f"{target}_pred"]
    df_engine["Delta_Ng_pct"] = df_engine["Delta_Ng"]
    baseline_wf_mean = df_baseline["Wf"].mean()
    df_engine["Delta_Wf_pct"] = 100 * df_engine["Delta_Wf"] / baseline_wf_mean
    noise = {t: max(df_engine.loc[: n - 1, f"Delta_{t}"].std(ddof=0), 1e-6) for t in ["T5", "Ng", "Wf"]}
    df_engine.attrs["models"] = models
    df_engine.attrs["noise"] = noise
    df_engine.attrs["baseline_n"] = n
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

# ======================================================================================
# 7. PREDICTIVE EXTRAPOLATION & UTILIZATION CORRELATION (RUL ENGINE)
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
# 8. DIAGNOSTIC CLASSIFICATION & FIM DIRECTIVE GENERATION
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
    
    noise = df_engine.attrs.get("noise", {"T5": 1, "Ng": 1, "Wf": 1})
    control_breach = (abs(d_t5) > CONTROL_SIGMA * noise["T5"] or abs(d_ng) > CONTROL_SIGMA * noise["Ng"] or abs(d_wf) > CONTROL_SIGMA * noise["Wf"])
    
    # HARDENING FIX: is_abnormal ONLY activates upon Hard OEM Limit breach or confirmed sustained shift!
    is_abnormal = alarm_wash or alarm_borescope_t5 or alarm_borescope_ng or sustained_t5 or sustained_ng
    
    slope_t5 = rolling_slope(df_engine["Delta_T5"], TREND_WINDOW)
    slope_ng = rolling_slope(df_engine["Delta_Ng"], TREND_WINDOW)
    
    rul_t5_borescope = calculate_rul(d_t5, slope_t5, T5_BORESCOPE_C, "UP")
    rul_ng_borescope = calculate_rul(d_ng, slope_ng, NG_BORESCOPE_LOW_PCT, "DOWN")
    rul_cycles = min(rul_t5_borescope, rul_ng_borescope)
    
    reg_prefix = str(latest["Engine"]).split("|")[0].strip()
    fc_per_day = get_aircraft_utilization_rate(reg_prefix, df_util)
    
    # HARDENING FIX: Cap days_left to prevent OverflowError in calendar datetime calculation
    days_left = int(rul_cycles / fc_per_day) if fc_per_day > 0 else 999
    days_left = min(days_left, 3650) # Cap projection at 10 years maximum
    proj_date = (datetime.now() + timedelta(days=days_left)).strftime("%Y-%m-%d") if rul_cycles < 999 else "Stable"
    
    return dict(
        latest=latest, d_t5=d_t5, d_ng=d_ng, d_wf=d_wf,
        shift_t5=shift_t5, shift_ng=shift_ng, shift_wf=shift_wf,
        alarm_wash=alarm_wash, alarm_borescope_t5=alarm_borescope_t5,
        alarm_borescope_ng=alarm_borescope_ng,
        sustained_t5=sustained_t5, isolated_t5=isolated_t5,
        sustained_ng=sustained_ng, isolated_ng=isolated_ng,
        control_breach=control_breach, is_abnormal=is_abnormal,
        slope_t5=slope_t5, slope_ng=slope_ng,
        rul_cycles=rul_cycles, proj_date=proj_date, fc_per_day=fc_per_day
    )

def generate_recommendations(df_engine: pd.DataFrame, status: dict) -> list:
    recs = []
    latest = status["latest"]
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
    
    # HARDENING FIX: Explicit handling for Statistical Advisory Watch vs. Green Normal Condition
    if not recs:
        if status["control_breach"] and not status["is_abnormal"]:
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
# 9. PLOTLY VISUALIZATION ENGINE
# ======================================================================================
def make_trend_figure(df_engine: pd.DataFrame, engine_name: str) -> go.Figure:
    fig = go.Figure()
    ioat_col = df_engine["IOAT"] if "IOAT" in df_engine.columns else np.zeros(len(df_engine))
    alt_col = df_engine["Press_Alt"] if "Press_Alt" in df_engine.columns else np.zeros(len(df_engine))
    tq_col = df_engine["TQ"] if "TQ" in df_engine.columns else np.zeros(len(df_engine))
    custom_data = np.stack((ioat_col, alt_col, tq_col), axis=-1)

    specs = [("Delta_T5", "\u0394 T5 (ITT) [\u00b0C]", "#B42318"), ("Delta_Ng", "\u0394 Ng [%]", "#003B6F"), ("Delta_Wf", "\u0394 Wf [PPH]", "#B54708")]
    for col, label, color in specs:
        fig.add_trace(go.Scatter(x=df_engine["Date"], y=df_engine[col], mode="lines+markers", name=label, line=dict(color=color, width=2), marker=dict(size=5, color=color), customdata=custom_data,
            hovertemplate=(f"<b>{label}</b><br>Date: %{{x|%Y-%m-%d}}<br>Residual Deviation: <b>%{{y:+.2f}}</b><br>------------------------------<br><b>Flight Parameters:</b><br>• IOAT (OAT)     : %{{customdata[0]:.1f}} °C<br>• Press Altitude : %{{customdata[1]:,.0f}} ft<br>• Engine Torque  : %{{customdata[2]:.1f}} PSI<br><extra></extra>")))
        ma = df_engine[col].rolling(3, min_periods=1).mean()
        fig.add_trace(go.Scatter(x=df_engine["Date"], y=ma, mode="lines", name=f"{label} (3-cyc MA)", line=dict(color=color, width=1, dash="dot"), opacity=0.4, showlegend=False, hoverinfo="skip"))

    noise = df_engine.attrs.get("noise", {})
    if "T5" in noise:
        band = CONTROL_SIGMA * noise["T5"]
        fig.add_hrect(y0=-band, y1=band, fillcolor="rgba(0, 59, 111, 0.04)", line_width=0)

    fig.add_hline(y=T5_WASH_C, line_dash="dash", line_color="#B54708", line_width=1, annotation_text="ITT +10°C (Wash Limit)", annotation_font=dict(size=10, color="#B54708"))
    fig.add_hline(y=T5_BORESCOPE_C, line_dash="dash", line_color="#B42318", line_width=1, annotation_text="ITT +15°C (Borescope Limit)", annotation_font=dict(size=10, color="#B42318"))

    fig.update_layout(title=dict(text=f"<b>Condition-Corrected Parameter Shift | Powerplant {engine_name}</b> ({len(df_engine)} Cycles Recorded)", font=dict(color=NAVY, size=14)),
        xaxis_title="Flight Date / Cycle", yaxis_title="Residual Delta from Baseline", hovermode="x unified", template="plotly_white", height=440,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(248,250,252,1)", margin=dict(l=40, r=20, t=60, b=40),
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=11, color="#475569")), yaxis=dict(showgrid=True, gridcolor="#F1F5F9", zeroline=True, zerolinecolor="#94A3B8", zerolinewidth=1, tickfont=dict(size=11, color="#475569")))
    return fig

def make_raw_vs_predicted(df_engine: pd.DataFrame, param: str, unit: str, color: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_engine["Date"], y=df_engine[param], mode="lines+markers", name=f"Actual {param}", line=dict(color=color, width=1.8), marker=dict(size=4)))
    fig.add_trace(go.Scatter(x=df_engine["Date"], y=df_engine[f"{param}_pred"], mode="lines", name="Predicted Baseline", line=dict(color="#64748B", width=1.5, dash="dash")))
    fig.update_layout(title=dict(text=f"<b>{param} | Actual vs. Condition Baseline ({unit})</b>", font=dict(color=NAVY, size=12)), template="plotly_white", height=280, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(248,250,252,1)", margin=dict(l=40, r=20, t=50, b=30),
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=10)), yaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=10)))
    return fig

# ======================================================================================
# 10. AUTOMATED EMAIL DISPATCH PROTOCOL & EWO GENERATOR
# ======================================================================================
def send_engineering_notice(engine_id: str, status_label: str, report_body: str, recipients: list):
    try:
        sender_email = st.secrets["email"]["sender_address"]
        sender_password = st.secrets["email"]["app_password"]
        smtp_server = st.secrets["email"].get("smtp_server", "smtp.gmail.com")
        smtp_port = int(st.secrets["email"].get("smtp_port", 465))
        live_mode = True
    except Exception:
        live_mode = False

    if not live_mode:
        st.info(f"**[SYSTEM SIMULATION MODE]** SMTP secrets not unconfigured in `.streamlit/secrets.toml`. "
                f"In production, notice for **{engine_id} ({status_label})** is dispatched to: `{', '.join(recipients)}`.")
        return True

    msg = MIMEMultipart()
    msg['From'] = f"AIRFAST ECTM Automated System <{sender_email}>"
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = f"[URGENT - {status_label}] ECTM Alert: Powerplant {engine_id} Requires Intervention"
    
    email_content = f"EXECUTIVE ENGINEERING NOTICE | PT. AIRFAST INDONESIA\n====================================================================\nPowerplant Serial / Position : {engine_id}\nSystem Status Classification : {status_label}\nDate Evaluated               : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n====================================================================\n\nAn abnormal thermodynamic parameter shift has been confirmed on Powerplant {engine_id}.\nPlease review the computed residuals and OEM-referenced maintenance directives below:\n\n{report_body}\n\n--------------------------------------------------------------------\nAutomated transmission from AIRFAST ECTM Technical Services System.\nDo not reply directly to this automated service address."
    msg.attach(MIMEText(email_content, 'plain'))
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"SMTP Transmission Failure: {str(e)}")
        return False

def generate_ewo_html(engine_id: str, status_label: str, status_dict: dict, recs: list) -> str:
    date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    latest_date = status_dict['latest']['Date'].strftime('%Y-%m-%d')
    rows_html = ""
    for r in recs:
        rows_html += f'<div style="border: 1px solid #CBD5E1; padding: 12px; margin-bottom: 10px; border-radius: 4px;"><b style="color: #003B6F; font-size: 14px;">[{r["fim_ref"]}] {r["title"]}</b><p style="font-size: 12px; color: #334155; margin-top: 6px; white-space: pre-line;">{r["body"]}</p><div style="margin-top: 10px; font-size: 11px; color: #64748B;">[ &nbsp; ] Action Completed &nbsp;&nbsp;&nbsp;&nbsp; Mech Sign: __________________ &nbsp;&nbsp;&nbsp;&nbsp; Date: ______________</div></div>'
    return f'<!DOCTYPE html><html><head><title>Engineering Work Order - {engine_id}</title><style>body {{ font-family: Arial, sans-serif; color: #0F172A; margin: 40px; }} .header {{ border-bottom: 3px solid #003B6F; padding-bottom: 10px; margin-bottom: 20px; }} .title {{ font-size: 20px; font-weight: bold; color: #003B6F; }} .subtitle {{ font-size: 12px; color: #64748B; font-weight: bold; letter-spacing: 1px; }} .meta-table {{ width: 100%; margin-bottom: 20px; border-collapse: collapse; }} .meta-table td, .meta-table th {{ padding: 6px; border: 1px solid #E2E8F0; font-size: 12px; }} .meta-table th {{ background: #F8FAFC; text-align: left; color: #475569; }} .section-title {{ font-size: 14px; font-weight: bold; color: #003B6F; margin-top: 20px; margin-bottom: 10px; text-transform: uppercase; }} .footer {{ margin-top: 40px; border-top: 1px solid #CBD5E1; padding-top: 15px; font-size: 11px; color: #64748B; display: flex; justify-content: space-between; }} .sign-box {{ width: 200px; border-top: 1px solid #000; text-align: center; margin-top: 40px; font-size: 11px; padding-top: 5px; }}</style></head><body><div class="header"><div class="title">PT. AIRFAST INDONESIA</div><div class="subtitle">TECHNICAL SERVICES DIVISION | ENGINEERING WORK ORDER (EWO)</div></div><table class="meta-table"><tr><th>Powerplant Serial / Position</th><td><b>{engine_id}</b></td><th>Document Type</th><td>ECTM Directive Order</td></tr><tr><th>Evaluation Timestamp</th><td>{date_str}</td><th>Latest Logbook Date</th><td>{latest_date}</td></tr><tr><th>System Status Classification</th><td colspan="3"><b style="color: {"#B42318" if "ABNORMAL" in status_label else "#003B6F"};">{status_label}</b></td></tr><tr><th>Thermodynamic Residuals</th><td colspan="3">Δ T5: <b>{status_dict["d_t5"]:+.1f} °C</b> (Slope: {status_dict["slope_t5"]:+.2f}) | Δ Ng: <b>{status_dict["d_ng"]:+.2f} %</b> | Δ Wf: <b>{status_dict["d_wf"]:+.1f} PPH</b></td></tr></table><div class="section-title">OEM Maintenance Directives & Action Checklist</div>{rows_html}<div style="display: flex; justify-content: space-between; margin-top: 30px;"><div class="sign-box">Licensed Aircraft Engineer (LAE)</div><div class="sign-box">Chief Inspector / Quality Control</div></div><div class="footer"><div>PT. AIRFAST Indonesia | DHC-6 / PT6A-34 Fleet Maintenance Program</div><div>Generated by Enterprise ECTM System</div></div></body></html>'

# ======================================================================================
# 11. CLEAN EXECUTIVE SIDEBAR
# ======================================================================================
logo_path = "images.png"  
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, use_container_width=True)
else:
    st.sidebar.markdown("<h2 style='font-size:1.5rem; font-weight:800; margin-bottom:0px; color:#FFFFFF; letter-spacing:0.05em;'>AIRFAST</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("<p style='font-weight:700; font-size:0.75rem; letter-spacing:0.15em; margin-top:0px; color:#f0b73d;'>INDONESIA</p>", unsafe_allow_html=True)

st.sidebar.markdown("---")

menu_selection = st.sidebar.radio(
    "Navigation Menu",
    ["Home (Fleet Matrix)", "Data Collection & Setup", "Trend Analysis & RUL", "Logbook & Defect Correlator", "Recommendations & Dispatch"],
    key="active_menu",
    label_visibility="collapsed",
)

st.sidebar.markdown("<br>" * 6, unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.markdown("<div style='font-size:0.75rem; line-height:1.5; color:#94A3B8; font-weight:400;'><b style='color:#FFFFFF; font-weight:600;'>PT. AIRFAST Indonesia</b><br>Jl. Marsekal Suryadarma No.8<br>Neglasari, Tangerang, Banten 15129<br><span style='font-size:0.7rem; color:#64748B;'>Engineering & Maintenance Division</span></div>", unsafe_allow_html=True)

# ======================================================================================
# 12. GLOBAL DATA PROCESSING & PERSISTENT STATE SYNC
# ======================================================================================
df_raw = st.session_state["df_data"].copy()
df_util_current = st.session_state["df_util"].copy()
df_rep_current = st.session_state["df_rep"].copy()

missing_required, available_correction = validate_columns(df_raw)
if missing_required:
    st.error(f"Ingestion Error: Mandatory schema columns missing: {', '.join(missing_required)}. Rectify within Data Collection.")
    st.stop()

# HARDENING FIX: Coerce all numeric columns to prevent regression crashes from text strings
for col in REQUIRED_COLUMNS[2:] + [c for c in OPTIONAL_COLUMNS if c in df_raw.columns]:
    df_raw[col] = pd.to_numeric(df_raw[col], errors="coerce")

df_raw["Date"] = pd.to_datetime(df_raw["Date"], errors="coerce")
df_raw = df_raw.dropna(subset=REQUIRED_COLUMNS).sort_values("Date")

engines_available = sorted(df_raw["Engine"].dropna().unique().tolist())
if not engines_available:
    st.error("Data Processing Error: No valid powerplant identifiers ('Engine') located within dataset.")
    st.stop()

# IMMUTABLE PERSISTENT FALLBACK: Guard against Streamlit widget cleanup
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
# 13. PAGE 1: HOME (FLEET MATRIX & UTILIZATION INTEGRATION)
# ======================================================================================
if menu_selection == "Home (Fleet Matrix)":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Engine Condition Trend Monitoring Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='color:#475569; font-size:1.05rem; font-weight:500; margin-top:0px;'>Technical Services & Fleet Maintenance | DHC-6 Twin Otter / PT6A-34</h3>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    st.markdown("<h3 style='color:#003B6F; margin-bottom:8px;'>Active Fleet Health & RUL Projections</h3>", unsafe_allow_html=True)
    
    fleet_summary_data = []
    for eng in engines_available:
        df_sub = df_raw[df_raw["Engine"] == eng].copy()
        if len(df_sub) >= 2:
            df_sub_proc = compute_engine_trend(df_sub, int(baseline_n_input), use_correction)
            st_sub = build_status(df_sub_proc, df_util_current)
            stat_lbl = "CRITICAL" if st_sub["is_abnormal"] else ("ADVISORY" if st_sub["control_breach"] else "NORMAL")
            rul_val = st_sub["rul_cycles"]
            rul_str = "Stable (>100 Cycles)" if rul_val >= 999 else f"{rul_val} Cycles ({st_sub['proj_date']})"
            
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

# ======================================================================================
# 14. PAGE 2: DATA COLLECTION & CONFIGURATION
# ======================================================================================
elif menu_selection == "Data Collection & Setup":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Data Ingestion & System Setup</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>Manage ECTM logbooks, airframe utilization files, and pilot/maintenance defect reports.</p>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    tab_ectm, tab_util, tab_rep = st.tabs(["1. ECTM Logbook (.csv)", "2. Flight Utilization (.xlsx)", "3. Maintenance Reports (.xlsx)"])
    
    with tab_ectm:
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
        st.data_editor(st.session_state["df_data"], num_rows="dynamic", use_container_width=True, key="ed_ectm_ui")

    with tab_util:
        st.caption("Upload Flight Utilization Excel file (e.g., `Flight Utulization DHC6-400.xlsx`) to synchronize RUL calendar projections.")
        up_util = st.file_uploader("Upload Utilization File (.xlsx)", type=["xlsx"], key="up_util_file")
        if up_util is not None:
            df_u_new = pd.read_excel(up_util)
            df_u_new['Work (Date)'] = pd.to_datetime(df_u_new['Work (Date)'], errors='coerce')
            st.session_state["df_util"] = df_u_new.dropna(subset=['Registration', 'Work (Date)'])
            st.success("Flight Utilization dataset synchronized!")
            st.rerun()
        st.dataframe(st.session_state["df_util"].head(100), use_container_width=True)

    with tab_rep:
        st.caption("Upload Pilot & Maintenance Report Excel file (e.g., `Pilot & Maintenance Report DHC6-400.xlsx`) to power the Defect Correlator.")
        up_rep = st.file_uploader("Upload Maintenance Report File (.xlsx)", type=["xlsx"], key="up_rep_file")
        if up_rep is not None:
            df_r_new = pd.read_excel(up_rep)
            df_r_new['Date'] = pd.to_datetime(df_r_new['Date'], errors='coerce')
            st.session_state["df_rep"] = df_r_new.dropna(subset=['Note / Report', 'Date'])
            st.success("Maintenance Reports synchronized!")
            st.rerun()
        st.dataframe(st.session_state["df_rep"].head(100), use_container_width=True)

    st.markdown("---")
    st.markdown("<h3 style='color:#003B6F; margin-bottom:4px;'>Analysis Configuration & Powerplant Selection</h3>", unsafe_allow_html=True)
    with st.container(border=True):
        col_set1, col_set2, col_set3 = st.columns([1.2, 1, 1.2])
        
        # CALLBACK SYNC: Persists selection across menu transitions
        def sync_config():
            if "ui_sel_eng" in st.session_state:
                st.session_state["target_engine"] = st.session_state["ui_sel_eng"]
            if "ui_sel_base" in st.session_state:
                st.session_state["target_baseline_n"] = st.session_state["ui_sel_base"]
            if "ui_sel_corr" in st.session_state:
                st.session_state["target_use_correction"] = st.session_state["ui_sel_corr"]

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
        st.button("Execute ECTM Analysis & View Trends", type="primary", use_container_width=True, on_click=lambda: st.session_state.update(active_menu="Trend Analysis & RUL"))

# ======================================================================================
# 15. PAGE 3: TREND ANALYSIS & PREDICTIVE RUL
# ======================================================================================
elif menu_selection == "Trend Analysis & RUL":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Thermodynamic Trend Analysis</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>Active Powerplant: <b style='color:#003B6F; background:#EFF4FA; padding:2px 8px; border-radius:4px; border:1px solid #CBD5E1;'>{selected_engine}</b> | Condition-Corrected Residual Shifts</p>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

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
        if status["is_abnormal"]: st.markdown("<span class='badge-red'>CRITICAL / ABNORMAL</span>", unsafe_allow_html=True)
        elif status["control_breach"]: st.markdown("<span class='badge-amber'>ADVISORY / WATCH</span>", unsafe_allow_html=True)
        else: st.markdown("<span class='badge-green'>NORMAL TREND</span>", unsafe_allow_html=True)

        st.write("")
        st.metric("Latest \u0394 T5 Residual", f"{status['d_t5']:+.1f} \u00b0C", delta=f"{status['slope_t5']:+.2f} °C/cyc", delta_color="inverse")
        st.metric("Latest \u0394 Ng Residual", f"{status['d_ng']:+.2f} %", delta=f"{status['slope_ng']:+.3f} %/cyc")
        st.metric("Latest \u0394 Wf Residual", f"{status['d_wf']:+.1f} PPH", delta=f"{status['latest']['Delta_Wf_pct']:+.1f}% shift", delta_color="inverse")

        rul_val = status["rul_cycles"]
        rul_display = "Stable (>100 Cycles)" if rul_val >= 999 else f"{rul_val} Flight Cycles"
        date_display = f"Projected Date: {status['proj_date']} ({status['fc_per_day']} cyc/day)" if rul_val < 999 else "No Intervention Scheduled"
        
        st.markdown(f"""
        <div class="rul-box">
            <div class="rul-title">Predictive RUL (Borescope Limit)</div>
            <div class="rul-val">{rul_display}</div>
            <div class="rul-sub">{date_display}</div>
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
    show_cols = [c for c in ["Date", "Engine", "T5", "Delta_T5", "Ng", "Delta_Ng", "Wf", "Delta_Wf_pct"] if c in df_engine.columns]
    st.dataframe(df_engine[show_cols].sort_values("Date", ascending=False), use_container_width=True, height=240)

# ======================================================================================
# 16. PAGE 4: LOGBOOK & DEFECT CORRELATOR
# ======================================================================================
elif menu_selection == "Logbook & Defect Correlator":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Maintenance Logbook & Defect Correlator</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>Cross-reference PIREP / MAREP defect notes and component replacement history against ECTM trends.</p>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    if df_rep_current.empty:
        st.warning("No Pilot & Maintenance Report dataset loaded. Please upload `Pilot & Maintenance Report DHC6-400.xlsx` in Data Collection.")
        st.stop()

    target_reg = selected_engine.split("|")[0].strip()
    
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
# 17. PAGE 5: RECOMMENDATIONS, EWO EXPORT & DISPATCH
# ======================================================================================
elif menu_selection == "Recommendations & Dispatch":
    st.markdown("<h1 style='color:#003B6F; margin-bottom:2px;'>Maintenance Recommendations & Dispatch</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#475569; font-size:0.95rem; font-weight:500; margin-top:0px;'>Active Powerplant: <b style='color:#003B6F; background:#EFF4FA; padding:2px 8px; border-radius:4px; border:1px solid #CBD5E1;'>{selected_engine}</b> | P&WC PT6A-34 FIM (Rev 75.0)</p>", unsafe_allow_html=True)
    st.markdown("<div class='gold-bar'></div>", unsafe_allow_html=True)

    overall_status_label = "CRITICAL / ABNORMAL" if status["is_abnormal"] else ("ADVISORY / WATCH" if status["control_breach"] else "NORMAL")
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
        "-------------------------------------------------------------------------",
        "MAINTENANCE DIRECTIVES & RECOMMENDATIONS:",
    ]
    for rec in recommendations: report_lines += [f"[{rec['fim_ref']}] {rec['title']}", rec["body"], ""]
    
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        st.download_button("Download Technical Analysis Report (.txt)", data="\n".join(report_lines).encode("utf-8"), file_name=f"ECTM_Report_{selected_engine.split('|')[0].strip()}_{datetime.now().strftime('%Y%m%d')}.txt", mime="text/plain", use_container_width=True)
    with col_exp2:
        ewo_html_data = generate_ewo_html(selected_engine, overall_status_label, status, recommendations)
        st.download_button("Download Print-Ready Work Order (.html / PDF)", data=ewo_html_data.encode("utf-8"), file_name=f"AIRFAST_EWO_{selected_engine.split('|')[0].strip()}_{datetime.now().strftime('%Y%m%d')}.html", mime="text/html", use_container_width=True, help="Open downloaded HTML in browser and press Ctrl+P (Print to PDF) for formal signed documentation.")

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
                    success = send_engineering_notice(selected_engine, overall_status_label, "\n".join(report_lines), recipients_list)
                    if success: st.success("Engineering Notice dispatched successfully to target recipients.")