"""
LLP integration layer for the AIRFAST DHC-6-400 ECTM dashboard.

Design rule:
- LLP is a parallel maintenance-planning data layer.
- It MUST NOT modify ECTM health classification, confidence, baseline, RUL, or FIM logic.
- Missing/invalid LLP source is fail-safe: the dashboard continues without LLP.
"""
from pathlib import Path
from typing import Dict, Tuple
import re
import pandas as pd

LLP_DEFAULT_FILENAME = "Engine Life Limited Part DHC6-400.xlsx"

def _norm_registration(value) -> str:
    s = "" if value is None else str(value).strip().upper()
    m = re.search(r"(PK-[A-Z]{3})", s)
    return m.group(1) if m else s

def _norm_position(value) -> str:
    s = "" if value is None else str(value).strip().upper()
    if "L/H" in s or "LH" in s or "LEFT" in s:
        return "LH"
    if "R/H" in s or "RH" in s or "RIGHT" in s:
        return "RH"
    return ""

def _sheet_engine_key(sheet_name: str) -> Tuple[str, str]:
    reg = _norm_registration(sheet_name)
    m = re.search(r"ENGINE\s*#?(\d+)", sheet_name.upper())
    pos = {"1": "LH", "2": "RH"}.get(m.group(1), "") if m else ""
    return reg, pos

def _parse_date(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NaT
    return pd.to_datetime(value, errors="coerce")

def _parse_sheet(ws, sheet_name: str):
    rows = list(ws.values)
    if not rows:
        return pd.DataFrame(), {}

    # Metadata
    meta = {
        "sheet_name": sheet_name,
        "registration": _norm_registration(sheet_name),
        "position": _sheet_engine_key(sheet_name)[1],
        "esn": "",
        "installed_at": "",
        "profile": "",
        "report_date": pd.NaT,
        "last_utilization_date": pd.NaT,
        "engine_tsn": None,
        "engine_csn": None,
        "engine_tso": None,
        "engine_cso": None,
    }

    def _compact(row):
        # LLP workbook uses merged cells extensively. Collapse empty cells while
        # preserving left-to-right semantic order.
        return [v for v in list(row) if v is not None and not (isinstance(v, float) and pd.isna(v))]

    compact_rows = [_compact(r) for r in rows]

    for vals in compact_rows:
        if not vals:
            continue
        for j, v in enumerate(vals):
            if not isinstance(v, str):
                continue
            key = v.strip().lower()
            nxt = vals[j+1] if j+1 < len(vals) else None
            if key == "report date:":
                meta["report_date"] = _parse_date(nxt)
            elif key == "esn:":
                meta["esn"] = "" if nxt is None else str(nxt).strip()
            elif key == "installed at:":
                meta["installed_at"] = _norm_registration(nxt)
            elif key == "position:":
                meta["position_source"] = str(nxt).strip() if nxt is not None else ""
            elif key == "current profile:":
                meta["profile"] = str(nxt).strip() if nxt is not None else ""
            elif key == "last utilization date:":
                meta["last_utilization_date"] = _parse_date(nxt)

    # Actual LLP table begins at a compact row containing '#',
    # 'Component Desc.' and 'Remaining'. Each component is followed by a
    # compact detail row containing P/N, S/N, work description and basis.
    records = []
    for i, vals in enumerate(compact_rows):
        if len(vals) < 10 or vals[0] != "#":
            continue
        header = [str(x).strip() if x is not None else "" for x in vals[:10]]
        if header[1] != "Component Desc." or header[8] != "Remaining":
            continue

        j = i + 2
        while j < len(compact_rows):
            r = compact_rows[j]
            if len(r) >= 10 and isinstance(r[0], (int, float)) and not pd.isna(r[0]):
                comp_no = int(r[0])
                detail = compact_rows[j+1] if j+1 < len(compact_rows) else []
                rec = {
                    "Registration": meta["registration"],
                    "Position": meta["position"],
                    "Engine Key": f"{meta['registration']} | {meta['position']}",
                    "Sheet": sheet_name,
                    "ESN": meta["esn"],
                    "Component #": comp_no,
                    "Component": r[1],
                    "Work Reference": r[2],
                    "Status": r[3],
                    "Interval": r[4],
                    "Last Accomplishment": _parse_date(r[5]),
                    "Accumulated": pd.to_numeric(r[6], errors="coerce"),
                    "Expiration": pd.to_numeric(r[7], errors="coerce"),
                    "Remaining": pd.to_numeric(r[8], errors="coerce"),
                    "Estimated Due Date": _parse_date(r[9]),
                    "P/N": detail[0] if len(detail) > 0 else "",
                    "S/N": detail[1] if len(detail) > 1 else "",
                    "Work Description": detail[2] if len(detail) > 2 else "",
                    "Basis": str(detail[3]).strip().upper() if len(detail) > 3 else "",
                    "Report Date": meta["report_date"],
                    "Installed At": meta["installed_at"],
                    "Position Source": meta.get("position_source", ""),
                    "Current Profile": meta["profile"],
                    "Last Utilization Date": meta["last_utilization_date"],
                    "Engine TSN": meta["engine_tsn"],
                    "Engine CSN": meta["engine_csn"],
                    "Engine TSO": meta["engine_tso"],
                    "Engine CSO": meta["engine_cso"],
                }
                rem = rec["Remaining"]
                rec["Life Status"] = "OVERDUE" if pd.notna(rem) and rem <= 0 else "LIFE AVAILABLE"
                records.append(rec)
                j += 2
                continue
            if r and r[0] == "Page:":
                break
            j += 1

    return pd.DataFrame(records), meta

def load_llp_workbook(path: str):
    """Return normalized LLP component data, metadata, and source issues."""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(), {"available": False}, [
            f"LLP source workbook not found: {p.name}"
        ]

    try:
        import openpyxl
        wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
    except Exception as exc:
        return pd.DataFrame(), {"available": False}, [
            f"LLP workbook could not be opened: {exc}"
        ]

    frames = []
    metas = []
    issues = []

    for ws in wb.worksheets:
        df, meta = _parse_sheet(ws, ws.title)
        if not df.empty:
            frames.append(df)
        metas.append(meta)

    data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    if not data.empty:
        # Detect source metadata mismatches without silently correcting them.
        for meta in metas:
            reg = meta.get("registration", "")
            pos = meta.get("position", "")
            installed = meta.get("installed_at", "")
            profile = meta.get("profile", "")
            if installed and reg and installed != reg:
                issues.append(
                    f"{reg} {pos}: workbook 'Installed at' is {installed}, "
                    f"not {reg}."
                )
            if profile and "DHC-6 SERIES 400" not in profile.upper():
                issues.append(
                    f"{reg} {pos}: workbook Current Profile is '{profile}'."
                )

        missing = sorted(set(data["Engine Key"]) - set())
        # Data-quality checks at component level.
        invalid_basis = sorted(
            set(data.loc[
                ~data["Basis"].isin(["FH", "FC", ""]),
                "Basis"
            ].dropna().astype(str))
        )
        if invalid_basis:
            issues.append("Unrecognized LLP life basis: " + ", ".join(invalid_basis))

    report_dates = (
        data["Report Date"].dropna().dt.strftime("%Y-%m-%d").unique().tolist()
        if not data.empty else []
    )
    metadata = {
        "available": True,
        "source_file": p.name,
        "source_mtime": p.stat().st_mtime,
        "sheet_count": len(wb.sheetnames),
        "engine_count": len(data["Engine Key"].drop_duplicates()) if not data.empty else 0,
        "component_count": len(data),
        "report_dates": report_dates,
    }
    return data, metadata, issues

def engine_llp_view(data: pd.DataFrame, selected_engine: str):
    """Return LLP rows for dashboard engine key, without altering source values."""
    if data.empty or "Engine Key" not in data.columns:
        return pd.DataFrame()
    return data[data["Engine Key"].astype(str).str.upper() == str(selected_engine).upper()].copy()

def source_summary(data: pd.DataFrame, selected_engine: str):
    view = engine_llp_view(data, selected_engine)
    if view.empty:
        return {
            "component_count": 0,
            "overdue_count": 0,
            "report_date": None,
            "metadata_mismatch": False,
        }
    return {
        "component_count": len(view),
        "overdue_count": int((view["Life Status"] == "OVERDUE").sum()),
        "report_date": view["Report Date"].dropna().max() if view["Report Date"].notna().any() else None,
        "metadata_mismatch": bool(
            view["Installed At"].astype(str).str.len().gt(0).any() and
            (view["Installed At"].astype(str).str.upper() != view["Registration"].astype(str).str.upper()).any()
        ),
    }
