# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : WIB-side atom script — WIB-FEMB data link alignment before acquisition
"""
wib_data_align.py — Execute data link alignment for specified FEMB slots.

Usage:
    python3 wib_data_align.py 0 1

Source: QC_runs.take_data() -> self.chk.data_align()

Python 3.6 compatible (no f-strings with = specifier, no walrus operator).
"""
import sys
from wib_cfgs import WIB_CFGS

fembs = [int(x) for x in sys.argv[1:]]
chk = WIB_CFGS()
chk.wib_fw()
chk.data_align(fembs)
chk.align_flg = False
print("Done: data_align fembs={}".format(fembs))
