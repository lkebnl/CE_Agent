# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : WIB-side atom script — Spy Buffer trigger, N-frame capture, and .bin file save
"""
wib_acquire.py — Trigger Spy Buffer acquisition and save raw data.

Usage:
    python3 wib_acquire.py {fembs} --samples 10 \
        --output RMS_SE_200mVBL_14_0mVfC_2_0us_0x00.bin

The output file is saved under /home/root/BNL_CE_WIB_SW_QC/QC/{output}.
Output format is compatible with QC_runs: pickle.dump([rawdata, [], fembs], f)

Source: QC_runs.take_data() -> spybuf_trig() + pickle.dump()

Python 3.6 compatible (no f-strings with = specifier, no walrus operator).
"""
import sys
import pickle
import os
import argparse
from wib_cfgs import WIB_CFGS

ap = argparse.ArgumentParser(description="Spy Buffer acquisition on WIB")
ap.add_argument("fembs",    type=int, nargs='+', help="FEMB slot numbers")
ap.add_argument("--samples",type=int, default=10, help="Number of spy-buffer samples")
ap.add_argument("--output", type=str, default="rms_raw.bin", help="Output file name")
ap.add_argument("--trig",   type=int, default=0, help="Trigger mode: 0=SW, 1=HW")
args = ap.parse_args()

fembs = args.fembs
chk = WIB_CFGS()
chk.wib_fw()

rawdata = chk.spybuf_trig(
    fembs=fembs,
    num_samples=args.samples,
    trig_cmd=args.trig,
    fastchk=True,
)

if rawdata is False:
    print("ERROR: data sync failed")
    sys.exit(1)

outpath = "/home/root/BNL_CE_WIB_SW_QC/QC/" + args.output
os.makedirs(os.path.dirname(outpath), exist_ok=True)

with open(outpath, 'wb') as f:
    # Compatible with QC_runs format: [rawdata, cfg_paras_rec, fembs]
    pickle.dump([rawdata, [], fembs], f)

print("Done: acquired {} samples => {}".format(args.samples, outpath))
