#!/usr/bin/env python3
# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : CE regulator output voltage/current monitoring
"""
Regulator Output Monitoring QC Test
=====================================
Sweeps 4 Vin × 3 ASIC configurations = 12 sets of power rail voltage
measurements via wib_vol_mon().

Vin values : 2.6 V, 3.0 V, 3.5 V, 4.0 V
ASIC configs:
  0 – FE: SE off  | ADC: SE off,  DIFF off  (baseline, no buffers)
  1 – FE: SE on   | ADC: SE on,   DIFF off  (CMOS ref 0x62, ibuff 200 uA)
  2 – FE: SDD on  | ADC: SE off,  DIFF on   (CMOS ref 0x62, ibuff 200 uA)

Register notes (ColdADC, reg page 1):
  0x80 = 0x62  → SDC/CMOS input reference + buffer on (DIFF or SE+buf mode)
  0x9d = 0x27  → ibuff0 current = 200 uA when input buffers are enabled
  0x9e = 0x27  → ibuff1 current = 200 uA when input buffers are enabled

Usage:
  python3 CE_regulator_output_monitor.py <femb_id> [femb_id ...] [save]
  e.g.  python3 CE_regulator_output_monitor.py 0 1
        python3 CE_regulator_output_monitor.py 0 1 save
"""

import time
import sys
import copy
import pickle
from wib_cfgs import WIB_CFGS
from QC_components.qc_a_function import monitor_power_rail_analysis
import QC_components.qc_log as log

# ---------------------------------------------------------------------------
# Parse command-line arguments
# ---------------------------------------------------------------------------
if len(sys.argv) < 2:
    print('Please specify at least one FEMB slot to test.')
    print('e.g. python3 CE_regulator_output_monitor.py 0 1')
    exit()

save = 'save' in sys.argv
fembs = [int(a) for a in sys.argv[1:] if a.isdigit()]

if len(fembs) == 0:
    print('No valid FEMB slot numbers found.')
    exit()

fembNo = {'femb{}'.format(i): '{}'.format(i) for i in fembs}
print(f"Testing FEMB slots: {fembs}")

# ---------------------------------------------------------------------------
# Test parameters
# ---------------------------------------------------------------------------
VIN_LIST = [2.6, 3.0, 3.5, 4.0]   # Input voltages to regulator (V)

# Each dict describes one ASIC configuration:
#   name        – short tag used in filenames / dictionary keys
#   label       – human-readable description printed to console
#   fe_sts      – FE ASIC SE stimulation enable  (sts arg to set_fe_board)
#   fe_sdd      – FE ASIC differential mode      (sdd arg to set_fe_board)
#   adc_sha_cs  – ADC SHA mode: 0 = SE, 1 = DIFF  (adcs_paras[i][2])
#   adc_ibuf_cs – ADC input buffer:  0 = off, 1 = SDC/CMOS buf  (adcs_paras[i][3])
#   cmos_extra  – if True, write reg 0x80=0x62 after femb_cfg (needed when
#                 femb_adc_cfg goes through the SE path but we still want the
#                 CMOS reference with buffer enabled)
ASIC_CONFIGS = [
    {
        'name':       'FEseo_ADCseo_DIFFo',
        'label':      'FE: SE off  | ADC: SE off, DIFF off',
        'fe_sts':     0,  'fe_sdd':      0,
        'adc_sha_cs': 0,  'adc_ibuf_cs': 0,
        'cmos_extra': False,
    },
    {
        'name':       'FEsen_ADCsen_DIFFo',
        'label':      'FE: SE on   | ADC: SE on,  DIFF off',
        'fe_sts':     1,  'fe_sdd':      0,
        'adc_sha_cs': 0,  'adc_ibuf_cs': 1,
        # femb_adc_cfg writes reg 0x80=0x03 (SE path) then reg 0x9d/0x9e=0x27
        # (ibuf_cs>0 path).  cmos_extra=True overwrites reg 0x80 → 0x62 so
        # the CMOS/SDC reference is selected.
        'cmos_extra': True,
    },
    {
        'name':       'FEsddn_ADCseo_DIFFn',
        'label':      'FE: SDD on  | ADC: SE off, DIFF on',
        'fe_sts':     0,  'fe_sdd':      1,
        'adc_sha_cs': 1,  'adc_ibuf_cs': 1,
        # femb_adc_cfg already writes reg 0x80=0x62 and reg 0x9d/0x9e=0x27
        # through the DIFF + ibuf_cs>0 code path – no extra writes needed.
        'cmos_extra': False,
    },
]

# ---------------------------------------------------------------------------
# Initialize WIB and power on FEMBs
# ---------------------------------------------------------------------------
chk = WIB_CFGS()
chk.wib_fw()

print("\nPowering off FEMBs to initialize test ...")
chk.femb_powering([])
chk.fembs_vol_set(vfe=3.0, vcd=3.0, vadc=3.5)

print(f"Powering on FEMBs {fembs} ...")
chk.femb_power_com_on(fembs)
chk.femb_cd_rst()
time.sleep(1)

# ---------------------------------------------------------------------------
# Main sweep: 4 Vin × 3 ASIC configs  →  12 voltage monitoring snapshots
# ---------------------------------------------------------------------------
all_results = {}   # all_results[vin][cfg_name] = {'raw': ..., 'analysis': ..., 'check': ...}

for vin in VIN_LIST:
    print(f"\n{'='*65}")
    print(f"  Vin = {vin} V")
    print(f"{'='*65}")

    chk.fembs_vol_set(vfe=vin, vcd=vin, vadc=vin)
    time.sleep(0.5)   # let regulators settle

    all_results[vin] = {}

    for cfg in ASIC_CONFIGS:
        cfg_name = cfg['name']
        print(f"\n  [{cfg['label']}]")
        print()
        print()
        print()
        print('------------------------------')

        # --- Reset ADC parameters to defaults then apply config -----------
        chk.adcs_paras = copy.deepcopy(chk.adcs_paras_init)
        for i in range(8):
            chk.adcs_paras[i][2] = cfg['adc_sha_cs']   # sha_cs  (reg 0x84 / 0x80 mode)
            chk.adcs_paras[i][3] = cfg['adc_ibuf_cs']  # ibuf_cs (input buffer selection)
            chk.adcs_paras[i][8] = 1                    # autocali enabled

        # --- Set FE ASIC SPI register map ----------------------------------
        chk.set_fe_board(sts=cfg['fe_sts'], snc=1, sg0=0, sg1=0,
                         st0=1, st1=1, swdac=0, dac=0x00,
                         sdd=cfg['fe_sdd'])

        # --- Configure all FEMBs -------------------------------------------
        chk.femb_cd_rst()
        for femb_id in fembs:
            # Force re-config of all sub-blocks even if flags were cleared
            chk.adc_flg[femb_id] = True
            chk.fe_flg[femb_id]  = True
            chk.femb_cfg(femb_id, False)

            # Config 1 only: femb_adc_cfg took the SE path (reg 0x80 = 0x03).
            # Overwrite reg 0x80 → 0x62 to select CMOS / SDC reference and
            # also write ibuff current registers for completeness.
            if cfg['cmos_extra']:
                for adc_no in range(8):
                    c_id = chk.adcs_paras[adc_no][0]
                    # CMOS reference + SDC input buffer enable
                    chk.femb_i2c_wrchk(femb_id, chip_addr=c_id,
                                       reg_page=1, reg_addr=0x80, wrdata=0x62)
                    # ibuff0 / ibuff1 current = 200 uA  (0xFF – 0xD8 = 0x27)
                    chk.femb_i2c_wrchk(femb_id, chip_addr=c_id,
                                       reg_page=1, reg_addr=0x9d, wrdata=0x27)
                    chk.femb_i2c_wrchk(femb_id, chip_addr=c_id,
                                       reg_page=1, reg_addr=0x9e, wrdata=0x27)

        # --- Voltage monitoring for all power rails ------------------------
        print("  Monitoring power rails ...")
        sps = 10
        vold = chk.wib_vol_mon(femb_ids=fembs, sps=sps)
        monvols = [vold, fembs]

        label = f"Vin{vin}V_{cfg_name}"
        monitor_power_rail_analysis(cfg['label'], fembs, monvols, fembNo,
                                    label=label)

        vol_report = dict(log.tmp_log)
        chk_report = dict(log.check_log)

        all_results[vin][cfg_name] = {
            'raw':      monvols,
            'analysis': vol_report,
            'check':    chk_report,
        }

        # --- Print voltage summary -----------------------------------------
        for femb_id_str, rails in vol_report.items():
            print(f"  {femb_id_str}:")
            for rail, mv in rails.items():
                print(f"    {rail:25s}: {mv} mV")

        for femb_id_str, result in chk_report.items():
            status = ("\033[32mPASS\033[0m" if result.get('Result', False)
                      else "\033[31mFAIL\033[0m")
            print(f"  {femb_id_str}  →  {status}")
            if not result.get('Result', False):
                for issue in result.get('Issue List', []):
                    print(f"    ! {issue}")

        # --- Optional save -------------------------------------------------
        if save:
            fp = f"REG_MON_Vin{vin}V_{cfg_name}.bin"
            with open(fp, 'wb') as fn:
                pickle.dump([monvols, vol_report, chk_report, fembs], fn)
            print(f"  Saved → {fp}")

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------
print(f"\n{'='*65}")
print("  Summary  (PASS / FAIL per combination)")
print(f"{'='*65}")
print(f"  {'Vin':>6}  {'Config':<35}  {'Result'}")
print(f"  {'-'*6}  {'-'*35}  {'-'*6}")
for vin in VIN_LIST:
    for cfg in ASIC_CONFIGS:
        cfg_name = cfg['name']
        results_for_cfg = all_results[vin][cfg_name]['check']
        overall = all(r.get('Result', False) for r in results_for_cfg.values())
        status = "PASS" if overall else "FAIL"
        print(f"  {vin:>6.1f}  {cfg['label']:<35}  {status}")

# ---------------------------------------------------------------------------
# Power off
# ---------------------------------------------------------------------------
print(f"\n{'='*65}")
print("Powering off FEMBs")
chk.femb_powering([])

total = len(VIN_LIST) * len(ASIC_CONFIGS)
print(f"Done. {len(VIN_LIST)} Vin × {len(ASIC_CONFIGS)} configs = {total} measurements completed.")
