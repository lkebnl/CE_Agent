"""
wib_fe_configure.py — Configure LArASIC registers (baseline / gain / peaking).

Usage:
    python3 wib_fe_configure.py {fembs} --snc 1 --sg0 0 --sg1 0 \
        --st0 1 --st1 1 [--sdd 0] [--sdf 0]

Parameter notes:
    fembs : space-separated slot numbers, e.g. 0 1
    --snc : 0 = 900 mV baseline, 1 = 200 mV baseline
    --sg0 / --sg1 : gain encoding (see constants table)
    --st0 / --st1 : peaking-time encoding (see constants table — counter-intuitive)
    --sdd : 0 = SE mode (default), 1 = DIFF mode
    --sdf : 0 = SE buffer off (default), 1 = SE buffer on
    --autocali : 1 = enable ADC auto-calibration (default)

Source: QC_runs.take_data() -> set_fe_board() + femb_cfg()

Python 3.6 compatible (no f-strings with = specifier, no walrus operator).
NOTE: femb_cfg() is intentionally called TWICE per FEMB to match QC_runs.py.
NOTE: time.sleep(10) is required for LArASIC register stabilisation — do NOT remove.
"""
import sys
import copy
import time
import argparse
from wib_cfgs import WIB_CFGS

ap = argparse.ArgumentParser(description="Configure LArASIC on WIB FEMBs")
ap.add_argument("fembs",     type=int, nargs='+', help="FEMB slot numbers")
ap.add_argument("--snc",     type=int, default=1, help="Baseline: 0=900mV, 1=200mV")
ap.add_argument("--sg0",     type=int, default=0, help="Gain bit 0")
ap.add_argument("--sg1",     type=int, default=0, help="Gain bit 1")
ap.add_argument("--st0",     type=int, default=1, help="Peaking time bit 0")
ap.add_argument("--st1",     type=int, default=1, help="Peaking time bit 1")
ap.add_argument("--sdd",     type=int, default=0, help="0=SE, 1=DIFF")
ap.add_argument("--sdf",     type=int, default=0, help="SE buffer enable")
ap.add_argument("--autocali",type=int, default=1, help="ADC auto-calibration enable")
args = ap.parse_args()

fembs = args.fembs
chk = WIB_CFGS()
chk.wib_fw()

# Configure ColdADC parameters for each of the 8 ADCs per FEMB
chk.adcs_paras = [
    [c_id, 0x08, 0 if args.sdd == 0 else 1, 0,
     0xDF, 0x33, 0x89, 0x67, args.autocali]
    for c_id in [0x4, 0x5, 0x6, 0x7, 0x8, 0x9, 0xA, 0xB]
]

# Configure LArASIC front-end registers
chk.set_fe_board(
    sts=0,
    snc=args.snc,
    sg0=args.sg0,
    sg1=args.sg1,
    st0=args.st0,
    st1=args.st1,
    swdac=0,
    dac=0x00,
    sdd=args.sdd,
    sdf=args.sdf,
)

cfg_paras_rec = []
for femb_id in fembs:
    chk.fe_flg[femb_id] = True
    if args.sdd:
        chk.adc_flg[femb_id] = True
    cfg_paras_rec.append(
        (femb_id,
         copy.deepcopy(chk.adcs_paras),
         copy.deepcopy(chk.regs_int8),
         0)
    )
    # Write configuration registers TWICE — matches QC_runs.take_data() behaviour
    chk.femb_cfg(femb_id, 0)
    chk.femb_cfg(femb_id, 0)

# Wait for LArASIC registers to stabilise — DO NOT shorten or remove this sleep
time.sleep(10)

print("Done: fe_configure fembs={} snc={} sg=({},{}) st=({},{})".format(
    fembs, args.snc, args.sg0, args.sg1, args.st0, args.st1))
