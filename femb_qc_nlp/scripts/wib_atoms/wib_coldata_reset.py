# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : WIB-side atom script — COLDATA reset for specified FEMB slots (runs on WIB via SSH)
"""
wib_coldata_reset.py — Execute COLDATA reset on specified FEMB slots.

Usage:
    python3 wib_coldata_reset.py 0 1 2 3

Source: QC_runs.femb_rms() -> self.chk.femb_cd_rst()

Python 3.6 compatible (no f-strings with = specifier, no walrus operator).
"""
import sys
from wib_cfgs import WIB_CFGS

fembs = [int(x) for x in sys.argv[1:]]
chk = WIB_CFGS()
chk.wib_fw()
chk.femb_cd_rst()
print("Done: coldata_reset fembs={}".format(fembs))
