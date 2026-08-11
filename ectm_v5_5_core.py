
from dataclasses import dataclass
from typing import Tuple
import numpy as np
import pandas as pd

# Validation-derived candidate sizes from rolling-origin testing.
# These are calibration candidates for the supplied AIRFAST history,
# not OEM/FIM limits.
VALIDATED_BASELINES_CRUISE = {
    "PK-OAM | LH": 20,
    "PK-OAM | RH": 15,
    "PK-OCF | LH": 100,
    "PK-OCF | RH": 50,
    "PK-OCG | LH": 30,
    "PK-OCG | RH": 65,
    "PK-OCH | RH": 65,
    "PK-OCI | LH": 40,
    "PK-OCI | RH": 80,
}

@dataclass(frozen=True)
class ECTMConfigV54:
    baseline_min: int = 15
    baseline_target_default: int = 30
    trend_window: int = 10
    control_sigma: float = 2.5
    t5_wash_c: float = 10.0
    t5_borescope_c: float = 15.0
    ng_borescope_low_pct: float = -1.0
    predictors: Tuple[str,...] = ("IOAT","Press_Alt","TQ","Np")
    targets: Tuple[str,...] = ("T5","Ng","Wf")
    min_domain_coverage: float = 80.0
    min_baseline_for_high_confidence: int = 15

CFG54=ECTMConfigV54()

def quality_gate(d):
    q=pd.Series(True,index=d.index)
    reasons=pd.DataFrame(index=d.index)
    if "Press_Alt" in d:
        bad=d["Press_Alt"].abs()>25000
        q &= ~bad; reasons["DQ_Extreme_Altitude"]=bad
    if "T5" in d:
        bad=(d["T5"]>800)|(d["T5"]<400)
        q &= ~bad; reasons["DQ_Extreme_T5"]=bad
    if "Ng" in d:
        bad=(d["Ng"]<70)|(d["Ng"]>100)
        q &= ~bad; reasons["DQ_Extreme_Ng"]=bad
    if "Np" in d:
        bad=(d["Np"]<70)|(d["Np"]>100)
        q &= ~bad; reasons["DQ_Extreme_Np"]=bad
    return q,reasons

def _fit(baseline,target,predictors):
    cols=[p for p in predictors if p in baseline.columns]
    w=baseline.dropna(subset=cols+[target]).copy()
    if len(w)<max(15,len(cols)+3):
        return {"mode":"mean","reason":"insufficient_baseline","n":len(w),
                "predictors":[],"coef":np.array([w[target].mean() if len(w) else np.nan])}
    usable=[p for p in cols if w[p].std(ddof=0)>1e-9]
    if len(usable)==0:
        return {"mode":"mean","reason":"constant_predictors","n":len(w),
                "predictors":[],"coef":np.array([w[target].mean()])}
    X=w[usable].astype(float).to_numpy()
    mu=X.mean(axis=0); sd=X.std(axis=0); sd[sd<1e-9]=1
    Z=(X-mu)/sd
    X1=np.column_stack([np.ones(len(Z)),Z])
    y=w[target].astype(float).to_numpy()
    coef,*_=np.linalg.lstsq(X1,y,rcond=None)
    pred=X1@coef
    ss_res=np.sum((y-pred)**2); ss_tot=np.sum((y-y.mean())**2)
    r2=1-ss_res/ss_tot if ss_tot>1e-12 else np.nan
    cond=np.linalg.cond(X1) if len(X1) else np.inf
    return {"mode":"regression","reason":"ok","n":len(w),"predictors":usable,
            "coef":coef,"mu":dict(zip(usable,mu)),"sd":dict(zip(usable,sd)),
            "r2":r2,"condition_number":cond,
            "baseline_min":w[usable].min().to_dict(),
            "baseline_max":w[usable].max().to_dict()}

def _predict(m,d):
    if m["mode"]!="regression":
        return np.full(len(d),m["coef"][0],dtype=float)
    X=d[m["predictors"]].astype(float).to_numpy()
    mu=np.array([m["mu"][p] for p in m["predictors"]])
    sd=np.array([m["sd"][p] for p in m["predictors"]])
    return m["coef"][0]+((X-mu)/sd)@m["coef"][1:]

def _domain(m,d):
    if m["mode"]!="regression": return np.ones(len(d),dtype=bool)
    mask=np.ones(len(d),dtype=bool)
    for p in m["predictors"]:
        x=d[p]
        mask &= x.notna().to_numpy()
        mask &= x.ge(m["baseline_min"][p]).fillna(False).to_numpy()
        mask &= x.le(m["baseline_max"][p]).fillna(False).to_numpy()
    return mask

def _choose_target(engine,event,n_valid):
    if event=="Cruise Trend" and engine in VALIDATED_BASELINES_CRUISE:
        return VALIDATED_BASELINES_CRUISE[engine],"VALIDATED_CRUISE_CALIBRATION"
    return min(CFG54.baseline_target_default,n_valid),"DEFAULT_UNVALIDATED_REGIME"

def compute_v54(df_engine, registration, position, cfg=CFG54):
    """ECTM v5.5: separate reference-model quality from current-flight applicability."""
    d=df_engine.sort_values("Date").reset_index(drop=True).copy()
    for c in cfg.predictors:
        if c in d.columns:
            d[c]=pd.to_numeric(d[c],errors="coerce")
    for c in cfg.targets:
        d[c]=pd.to_numeric(d[c],errors="coerce")

    q,qf=quality_gate(d)
    d["DQ_VALID"]=q
    for c in qf.columns:
        d[c]=qf[c]

    event=d["Event_Name"].iloc[-1] if len(d) and "Event_Name" in d else "UNKNOWN"
    d["Event_Match"]=d["Event_Name"].eq(event) if "Event_Name" in d else True

    # Preserve Engine_State segmentation when the source provides it.
    # Legacy AIRFAST extracts may not contain Engine_State at all; in that case
    # the model uses the supplied engine history without inventing a state.
    # If the column exists but the latest state is missing, confidence is
    # downgraded because we cannot safely identify the reference population.
    state="NOT_PROVIDED"
    state_available=True
    state_quality="NOT_PROVIDED"
    if "Engine_State" in d:
        state_available=False
        state_quality="MISSING_LATEST_STATE"
        if len(d):
            latest_state=d["Engine_State"].iloc[-1]
            if pd.notna(latest_state) and str(latest_state).strip():
                state=str(latest_state).strip()
                state_available=True
                state_quality="SEGMENTED"

    if "Engine_State" not in d:
        state_df=d.loc[d["Event_Match"] & d["DQ_VALID"]].copy()
    elif state_available:
        state_mask=d["Engine_State"].astype(str).eq(state)
        state_df=d.loc[state_mask & d["Event_Match"] & d["DQ_VALID"]].copy()
    else:
        state_df=pd.DataFrame(columns=d.columns)

    cols=list(cfg.predictors)+list(cfg.targets)
    state_df=state_df.dropna(subset=[c for c in cols if c in state_df.columns])

    target_n,policy=_choose_target(f"{registration} | {position}",event,len(state_df))
    baseline=state_df.iloc[:min(target_n,len(state_df))].copy()

    d.attrs["baseline_n"]=len(baseline)
    d.attrs["baseline_target"]=target_n
    d.attrs["baseline_policy"]=policy
    d.attrs["baseline_event"]=event
    d.attrs["engine_state"]=state
    d.attrs["engine_state_available"]=state_available
    baseline_frozen=(len(baseline)>=target_n and target_n>0)
    d.attrs["baseline_frozen"]=baseline_frozen
    d["Baseline_Frozen"]=baseline_frozen
    d["Baseline_Policy"]=policy
    d["Engine_State_Reference"]=state
    d["Engine_State_Available"]=state_available
    d["Engine_State_Quality"]=state_quality

    models={}
    applicable_all=np.ones(len(d),dtype=bool)
    domain_coverages={}
    noise={}

    for t in cfg.targets:
        m=_fit(baseline,t,list(cfg.predictors))
        models[t]=m
        pred=_predict(m,d)
        dom=_domain(m,d)
        d[f"Domain_Applicable_{t}"]=dom

        app=dom & d["DQ_VALID"].to_numpy() & d["Event_Match"].to_numpy()
        d[f"{t}_pred"]=pred
        d[f"Delta_{t}"]=np.where(app,d[t].to_numpy(float)-pred,np.nan)

        hist_mask=d["DQ_VALID"].to_numpy() & d["Event_Match"].to_numpy()
        domain_coverages[t]=(float(100*np.mean(dom[hist_mask])) if np.any(hist_mask) else 0.0)

        br=baseline[t].astype(float).to_numpy()-_predict(m,baseline)
        br=br[np.isfinite(br)]
        mad=np.median(np.abs(br-np.median(br))) if len(br) else np.nan
        sigma=1.4826*mad if np.isfinite(mad) and mad>1e-9 else (np.std(br) if len(br) else np.nan)
        noise[t]=float(max(sigma,1e-6)) if np.isfinite(sigma) else np.nan
        d[f"Control_Limit_{t}"]=cfg.control_sigma*noise[t]
        applicable_all &= app

    # Reference-model quality is independent of the latest flight.
    all_regression=all(models[t].get("mode")=="regression" for t in cfg.targets)
    reference_quality=(
        state_available
        and baseline_frozen
        and policy=="VALIDATED_CRUISE_CALIBRATION"
        and len(baseline)>=cfg.min_baseline_for_high_confidence
        and all_regression
    )
    reference_quality_label="HIGH" if reference_quality else "LOW"

    # Current applicability is evaluated row-by-row.
    applicable_count=np.zeros(len(d),dtype=int)
    for t in cfg.targets:
        applicable_count += d[f"Domain_Applicable_{t}"].astype(bool).to_numpy()
    d["Current_Domain_Coverage_pct"]=100.0*applicable_count/len(cfg.targets) if cfg.targets else 0.0
    d["Current_Applicability"]=(
        d["DQ_VALID"].to_numpy()
        & d["Event_Match"].to_numpy()
        & applicable_all
    )

    historical_min=min(domain_coverages.values()) if domain_coverages else 0.0
    d["Domain_Coverage_Min_pct"]=historical_min
    d["Historical_Domain_Coverage_Min_pct"]=historical_min
    d["Reference_Model_Quality"]=reference_quality_label
    d["Reference_Model_Quality_Reason"]=(
        "Validated baseline, frozen reference, sufficient baseline size, and regression model available for all targets."
        if reference_quality else
        "Reference model quality gate not satisfied; verify Engine_State, validated baseline regime, baseline size, and target-model fit."
    )

    # Historical coverage is diagnostic only; it no longer globally downgrades
    # a current flight that is otherwise applicable.
    high=reference_quality & d["Current_Applicability"].to_numpy()
    d["Model_Applicable"]=d["Current_Applicability"]
    d["Model_Confidence"]=np.where(
        high,"HIGH",
        np.where(d["DQ_VALID"].to_numpy() & d["Event_Match"].to_numpy(),"LOW","INVALID")
    )

    reasons=np.full(len(d),"INVALID_DATA_OR_EVENT_MISMATCH",dtype=object)
    valid_event=d["DQ_VALID"].to_numpy() & d["Event_Match"].to_numpy()
    reasons[valid_event]="CURRENT_FLIGHT_OUTSIDE_REFERENCE_DOMAIN"
    if not reference_quality:
        reasons[valid_event]="REFERENCE_MODEL_QUALITY_LOW"
    reasons[high]="HIGH_REFERENCE_QUALITY_AND_CURRENT_APPLICABILITY"
    d["Confidence_Reason"]=reasons

    d.attrs["models"]=models
    d.attrs["noise"]=noise
    d.attrs["domain_coverages"]=domain_coverages
    d.attrs["reference_model_quality"]=reference_quality_label
    d.attrs["historical_domain_coverage_min_pct"]=historical_min
    return d

def classify_v54(d,cfg=CFG54,critical_persistence=3):
    out=d.copy()
    out["ECTM_Row_Status"]="UNAVAILABLE"
    out["ECTM_Signal"]=""
    for i in out.index:
        if out.at[i,"Model_Confidence"]!="HIGH" or not bool(out.at[i,"Model_Applicable"]):
            continue
        hist=out.loc[:i]
        hv=hist[hist["Model_Confidence"].eq("HIGH") & hist["Model_Applicable"]]
        t5=hv["Delta_T5"]; ng=hv["Delta_Ng"]
        t5_up=(t5>=cfg.t5_borescope_c).tail(critical_persistence).all() if len(t5)>=critical_persistence else False
        ng_down=(ng<=cfg.ng_borescope_low_pct).tail(critical_persistence).all() if len(ng)>=critical_persistence else False
        stat=any(
            np.isfinite(out.at[i,f"Delta_{t}"]) and
            np.isfinite(out.at[i,f"Control_Limit_{t}"]) and
            abs(out.at[i,f"Delta_{t}"])>out.at[i,f"Control_Limit_{t}"]
            for t in cfg.targets
        )
        single=(out.at[i,"Delta_T5"]>=cfg.t5_borescope_c or out.at[i,"Delta_Ng"]<=cfg.ng_borescope_low_pct)
        if t5_up or ng_down:
            out.at[i,"ECTM_Row_Status"]="CRITICAL"
            out.at[i,"ECTM_Signal"]="PERSISTENT_FIM_LEVEL_DEVIATION"
        elif single:
            out.at[i,"ECTM_Row_Status"]="ADVISORY"
            out.at[i,"ECTM_Signal"]="SINGLE_POINT_FIM_THRESHOLD_REACHED; VERIFY_INDICATION_AND_PERSISTENCE"
        elif stat:
            out.at[i,"ECTM_Row_Status"]="ADVISORY"
            out.at[i,"ECTM_Signal"]="STATISTICAL_EARLY_WARNING"
        else:
            out.at[i,"ECTM_Row_Status"]="NORMAL"
    return out
