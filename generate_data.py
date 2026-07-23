import pandas as pd
import numpy as np

# Mengatur seed agar hasil random noise-nya konsisten & rapi saat di-generate
np.random.seed(42)

# Jumlah flight cycles yang ingin dibuat
n_cycles = 100

# 1. Generate Tanggal (100 hari berurutan mulai dari 1 Januari 2026)
dates = pd.date_range(start="2026-01-01", periods=n_cycles, freq="D").strftime("%Y-%m-%d")

# 2. Kondisi Terbang Konstan (Cruise Target)
engine = ["LH"] * n_cycles
press_alt = [11000] * n_cycles
ioat = np.random.normal(loc=10.0, scale=0.5, size=n_cycles) # Suhu luar 10 C +- noise
ias = np.random.normal(loc=135.0, scale=1.0, size=n_cycles)
tq = [40.0] * n_cycles
np_rpm = [75.0] * n_cycles

# 3. SIMULASI DEGRADASI PARAMETER MESIN (T5, Ng, Wf)
# Baseline bersih: T5 = 625 C, Ng = 91.5 %, Wf = 290 PPH

t5_list = []
ng_list = []
wf_list = []

for i in range(n_cycles):
    # Phase 1: Cycle 0 - 49 (Mesin Normal & Sehat)
    if i < 50:
        t5 = 625.0 + np.random.normal(0, 0.8)
        ng = 91.5 + np.random.normal(0, 0.05)
        wf = 290.0 + np.random.normal(0, 0.5)
        
    # Phase 2: Cycle 50 - 79 (Degradasi Awal - Compressor Fouling mulai terjadi)
    elif i < 80:
        progress = (i - 50) / 30.0  # Bergerak dari 0.0 ke 1.0
        t5 = 625.0 + (8.0 * progress) + np.random.normal(0, 0.8)   # Naik perlahan +8 C
        ng = 91.5 - (0.6 * progress) + np.random.normal(0, 0.05)   # Turun perlahan -0.6 %
        wf = 290.0 + (6.0 * progress) + np.random.normal(0, 0.5)   # Naik perlahan +6 PPH
        
    # Phase 3: Cycle 80 - 99 (Degradasi Lanjut - Melewati batas toleransi abnormal)
    else:
        progress = (i - 80) / 20.0  # Bergerak dari 0.0 ke 1.0
        t5 = 633.0 + (12.0 * progress) + np.random.normal(0, 0.8)  # Melonjak sampai +20 C dari baseline
        ng = 90.9 - (0.8 * progress) + np.random.normal(0, 0.05)   # Drop sampai -1.4 % dari baseline
        wf = 296.0 + (10.0 * progress) + np.random.normal(0, 0.5)  # Melonjak sampai +16 PPH

    t5_list.append(round(t5, 1))
    ng_list.append(round(ng, 2))
    wf_list.append(round(wf, 1))

# 4. Parameter Oli
oil_temp = np.round(np.random.normal(loc=73.0, scale=0.8, size=n_cycles), 1)
oil_press = np.round(np.random.normal(loc=91.0, scale=0.5, size=n_cycles), 1)

# Menyusun menjadi DataFrame
df_100 = pd.DataFrame({
    'Date': dates,
    'Engine': engine,
    'Press_Alt': press_alt,
    'IOAT': np.round(ioat, 1),
    'IAS': np.round(ias, 1),
    'TQ': tq,
    'Np': np_rpm,
    'T5': t5_list,
    'Ng': ng_list,
    'Wf': wf_list,
    'Oil_Temp': oil_temp,
    'Oil_Press': oil_press
})

# Simpan ke folder data/
output_path = "data/logbook_100_cycles.csv"
df_100.to_csv(output_path, index=False)
print(f"✅ Berhasil! File '{output_path}' dengan {n_cycles} flight cycles siap digunakan.")