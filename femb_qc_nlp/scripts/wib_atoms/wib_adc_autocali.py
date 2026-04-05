"""
wib_adc_autocali.py — Execute one ADC auto-calibration pass.

Usage:
    python3 wib_adc_autocali.py 0 1

Must be run once after every coldata_reset.

Source: QC_runs.femb_rms() -> self.take_data(autocali=1)

Python 3.6 compatible (no f-strings with = specifier, no walrus operator).
"""
import sys
import copy
import time
from wib_cfgs import WIB_CFGS

fembs = [int(x) for x in sys.argv[1:]]
chk = WIB_CFGS()
chk.wib_fw()

# Enable autocali=1 for all 8 ADCs
for i in range(8):
    chk.adcs_paras[i][8] = 1

chk.set_fe_board(sts=0, snc=1, sg0=0, sg1=0, st0=1, st1=1, swdac=0, dac=0)

for femb_id in fembs:
    chk.fe_flg[femb_id] = True
    chk.femb_cfg(femb_id, 0)

time.sleep(0.5)

for femb_id in fembs:
    chk.femb_autocali_off(femb_id)

print("Done: adc_autocali fembs={}".format(fembs))
