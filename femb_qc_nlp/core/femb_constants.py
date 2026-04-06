# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : Hardware constants — WIB address, LArASIC config maps, channel/chip mapping
"""
femb_constants.py — All constants for the FEMB QC NLP system.
No business logic here — pure data definitions.
"""

# ── WIB Connection ─────────────────────────────────────────────────────────────
WIB_HOST      = "root@192.168.121.123"
WIB_WORKDIR   = "/home/root/BNL_CE_WIB_SW_QC"
WIB_QC_DIR    = "/home/root/BNL_CE_WIB_SW_QC/QC"
WIB_ATOMS_DIR = "/home/root/BNL_CE_WIB_SW_QC/atoms"  # atom scripts directory

# ── Ollama ─────────────────────────────────────────────────────────────────────
OLLAMA_HOST  = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:8b"

# ── Chip-Channel Mapping ───────────────────────────────────────────────────────
# chip_id: (silkscreen, ch_start, ch_end)  — ch_end is inclusive
CHIP_CHANNEL_MAP = {
    0: ("U07",   0,  15),
    1: ("U17",  16,  31),
    2: ("U11",  32,  47),
    3: ("U03",  48,  63),
    4: ("U19",  64,  79),
    5: ("U23",  80,  95),
    6: ("U25",  96, 111),
    7: ("U21", 112, 127),
}
SILKSCREEN_TO_CHIP = {v[0]: k for k, v in CHIP_CHANNEL_MAP.items()}

# ── LArASIC Configuration Encoding ────────────────────────────────────────────
# From Datasheet Table 6

# Gain  SG(0,1):  sg0=0,sg1=0→14mV/fC  sg0=1,sg1=0→25mV/fC
#                  sg0=0,sg1=1→7.8mV/fC  sg0=1,sg1=1→4.7mV/fC
GAIN_MAP = {
    "14mV/fC":   (0, 0),
    "14.0mV/fC": (0, 0),
    "25mV/fC":   (1, 0),
    "25.0mV/fC": (1, 0),
    "7.8mV/fC":  (0, 1),
    "4.7mV/fC":  (1, 1),
}

# Peaking time ST(0,1): COUNTER-INTUITIVE encoding — strictly from datasheet
#   st0=0, st1=0 → 1.0 us
#   st0=1, st1=0 → 0.5 us
#   st0=0, st1=1 → 3.0 us
#   st0=1, st1=1 → 2.0 us
PEAKING_MAP = {
    "0.5us": (1, 0),   # st0=1, st1=0
    "0.5μs": (1, 0),
    "1us":   (0, 0),   # st0=0, st1=0  ← NOT (1,0) — counter-intuitive
    "1.0us": (0, 0),
    "1μs":   (0, 0),
    "1.0μs": (0, 0),
    "2us":   (1, 1),   # st0=1, st1=1
    "2.0us": (1, 1),
    "2μs":   (1, 1),
    "2.0μs": (1, 1),
    "3us":   (0, 1),   # st0=0, st1=1
    "3.0us": (0, 1),
    "3μs":   (0, 1),
    "3.0μs": (0, 1),
}

# Baseline SNC:  snc=0 → 900mV (induction),  snc=1 → 200mV (collection)
BASELINE_MAP = {
    "200mV": 1,
    "900mV": 0,
}

# ── File Name Tags (compatible with QC_runs.py naming) ────────────────────────
GAIN_TAG = {
    (0, 0): "14_0mVfC",
    (1, 0): "25_0mVfC",
    (0, 1): "7_8mVfC",
    (1, 1): "4_7mVfC",
}
PEAKING_TAG = {
    (1, 0): "0_5us",
    (0, 0): "1_0us",
    (1, 1): "2_0us",
    (0, 1): "3_0us",
}
BASELINE_TAG = {
    1: "200mVBL",
    0: "900mVBL",
}

# ── QC Item → Function Mapping ─────────────────────────────────────────────────
QC_ITEM_MAP = {
    1:  "pwr_consumption",
    2:  "pwr_cycle",
    3:  "femb_leakage_cur",
    4:  "femb_chk_pulse",
    5:  "femb_rms",           # ← current focus
    6:  "femb_CALI_1",
    7:  "femb_CALI_2",
    8:  "femb_CALI_3",
    9:  "femb_CALI_4",
    10: "femb_MON_1",
    11: "femb_MON_2",
    12: "femb_MON_3",
    13: "femb_CALI_5",
    14: "femb_CALI_6",
    15: "femb_adc_sync_pat",
    16: "femb_test_pattern_pll",
}

# ── Current Thresholds ────────────────────────────────────────────────────────
BIAS_I_LIM = 0.05
FE_I_LOW   = 0.30
CD_I_HIGH  = 0.30

# ── PC Local Data Root ─────────────────────────────────────────────────────────
PC_DATA_ROOT = "./data"
