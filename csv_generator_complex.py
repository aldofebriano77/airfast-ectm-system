"""
========================================================================================
 ADVANCED ECTM STRESS-TEST DATASET GENERATOR (v4.0)
 PT. AIRFAST INDONESIA | DHC-6 TWIN OTTER / P&WC PT6A-34 FLEET
========================================================================================
 Target Output : AIRFAST_ECTM_StressTest_V4.csv (600 Flight Cycles)
 Designed to Test:
 1. Automated Pre-Flight Data Quality Audit (Sensor Freezes & Atmospheric Outliers)
 2. Robust Regex Registration Parsing across weird/non-standard naming conventions
 3. P&WC PT6A-34 FIM Rev 75.0 Multi-Mode Degradation Signatures
 4. Expanding Standard Deviation (Adaptive Noise Banding) under heavy drift
 5. Predictive RUL Depletion & Emergency MCC Notice Triggers
========================================================================================
"""

import numpy as np
import pandas as pd

def generate_stress_test_csv():
    rng = np.random.default_rng(2026)
    total_cycles = 100
    start_date = pd.Timestamp("2026-01-01")
    
    # 6 Profil Mesin dengan variasi penamaan ekstrem untuk menguji Regex Parser
    fleet_profiles = [
        # Engine ID | Base T5 | Base Ng | Base Wf | Scenario Description
        ("PK-OAM | LH (SN: PC-E101)", 624.0, 91.50, 288.0, "COMPRESSOR_DEGRADATION_WASH"),
        ("PK-OAM | RH (SN: PC-E102)", 625.5, 91.60, 290.5, "CRITICAL_BORESCOPE_BREACH"),
        ("PK-OCH/LH #PC-E103 [BASE: TIM]", 623.0, 91.45, 289.0, "ISOLATED_TRANSMITTER_SPIKE"),
        ("PK-OCH - RH (SN PC-E104) HANGAR-1", 626.0, 91.55, 291.0, "PNEUMATIC_SENSING_LEAK"),
        ("PK-OCG | LH (SN: PC-E105)", 624.5, 91.50, 289.5, "ADVISORY_STATISTICAL_DRIFT"),
        ("PK-OCG/RH [SN: PC-E106] PERINTIS", 622.0, 91.70, 287.5, "SENSOR_FREEZE_AND_OUTLIER"),
    ]
    
    all_rows = []
    
    for eng_id, b_t5, b_ng, b_wf, scenario in fleet_profiles:
        for i in range(total_cycles):
            current_date = start_date + pd.Timedelta(days=i)
            
            # 1. Variasi Parameter Penerbangan & Atmosfer Nyata (Rute Perintis Papua/Banten)
            alt = rng.uniform(1500, 11500) if i % 2 == 0 else rng.uniform(8000, 12000)
            ioat = 15.0 - (alt / 1000.0) * 1.98 + rng.normal(0, 1.2)  # Lapse rate standar
            ias = rng.uniform(128.0, 142.0)
            tq = rng.uniform(41.0, 44.5)
            np_rpm = 75.0
            
            # 2. Termodinamika Fisik Dasar (Sebelum Degradasi)
            # T5 naik seiring tingginya IOAT & TQ, Ng turun sedikit di IOAT tinggi
            t5 = b_t5 + 0.45 * (ioat - 15.0) + 1.8 * (tq - 42.5) + rng.normal(0, 0.3)
            ng = b_ng - 0.012 * (ioat - 15.0) + 0.15 * (tq - 42.5) + rng.normal(0, 0.04)
            wf = b_wf + 0.85 * (ioat - 15.0) + 3.2 * (tq - 42.5) + rng.normal(0, 0.5)
            oil_temp = 71.0 + 0.02 * i + rng.normal(0, 0.4)
            oil_press = 92.0 - 0.01 * i + rng.normal(0, 0.3)
            
            # 3. Penanaman Skenario Anomali & Ranjau (Dimulai setelah 10 siklus baseline bersih)
            if i >= 10:
                if scenario == "COMPRESSOR_DEGRADATION_WASH":
                    # Siklus 10-70: Kotoran kompresor menumpuk cepat (T5 naik, Ng turun, Wf boros)
                    if i <= 70:
                        drift = (i - 10) / 60.0
                        t5 += 12.5 * drift      # Menembus batas Wash Limit (+10°C) di siklus ~58
                        ng -= 0.85 * drift
                        wf += 14.0 * drift
                    else:
                        # Siklus 71+: Pasca-Wash di hangar, performa pulih seketika
                        t5 += 1.2
                        ng -= 0.08
                        wf += 1.5
                        
                elif scenario == "CRITICAL_BORESCOPE_BREACH":
                    # Erosi ekstrem pada vane CT (Compressor Turbine)
                    drift = ((i - 10) / 90.0) ** 1.4
                    t5 += 17.5 * drift          # Menembus batas Borescope (+15°C) di siklus ~82
                    ng -= 1.60 * drift          # Menembus batas Ng Borescope (-1.5%)
                    wf += 18.0 * drift
                    oil_temp += 4.5 * drift     # Panas berlebih merembes ke oli
                    
                elif scenario == "ISOLATED_TRANSMITTER_SPIKE":
                    # Siklus 45: Glitch sensor elektrik/transmitter di cockpit
                    if i == 45:
                        t5 += 19.5              # Lonjakan acak tanpa perubahan Ng yang sesuai
                        wf += 12.0
                        
                elif scenario == "PNEUMATIC_SENSING_LEAK":
                    # Kebocoran perlahan pada pipa P3/Py ke FCU (Semua parameter turun serentak)
                    drift = (i - 10) / 90.0
                    t5 -= 6.5 * drift
                    ng -= 1.2 * drift
                    wf -= 4.5 * drift
                    
                elif scenario == "ADVISORY_STATISTICAL_DRIFT":
                    # Degradasi ringan di batas 2.5-sigma tapi belum melanggar batas mutlak OEM
                    drift = (i - 10) / 90.0
                    t5 += 6.8 * drift
                    ng -= 0.35 * drift
                    wf += 5.0 * drift
                    
                elif scenario == "SENSOR_FREEZE_AND_OUTLIER":
                    # Siklus 30-34: SENSOR FREEZE (Ng macet persis di angka sama selama 5 hari)
                    if 30 <= i <= 34:
                        ng = 91.33
                    # Siklus 60: PHYSICAL OUTLIER (IOAT meledak karena sensor penjemuran tarmac/error)
                    if i == 60:
                        ioat = 59.5
                    # Siklus 85: SENSOR MATI (Thermocouple T5 putus/korslet)
                    if i == 85:
                        t5 = -2.5

            all_rows.append({
                "Date": current_date.strftime("%Y-%m-%d"),
                "Engine": eng_id,
                "Press_Alt": round(alt, 0),
                "IOAT": round(ioat, 1),
                "IAS": round(ias, 1),
                "TQ": round(tq, 1),
                "Np": round(np_rpm, 1),
                "T5": round(t5, 1),
                "Ng": round(ng, 2),
                "Wf": round(wf, 1),
                "Oil_Temp": round(oil_temp, 1),
                "Oil_Press": round(oil_press, 1)
            })
            
    df_out = pd.DataFrame(all_rows)
    output_filename = "AIRFAST_ECTM_StressTest_V4.csv"
    df_out.to_csv(output_filename, index=False)
    print(f"[SUCCESS] Dataset stress-test '{output_filename}' berhasil disintesis ({len(df_out)} baris data).")

if __name__ == "__main__":
    generate_stress_test_csv()