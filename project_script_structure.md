# BNL CE WIB SW QC — Project Script Structure

**Date:** 2026-03-24
**Branch:** CTS_2025

---

## Overview

The project has four run chains that work together during a full QC test.

| Run Chain | Entry Point | How It Runs |
|---|---|---|
| A — Main QC | `CTS_FEMB_QC_top.py` | Run locally, SSHes into WIB |
| B — WIB QC Test | `QC_top.py` | Launched ON the WIB via SSH from Chain A |
| C — Real-Time Monitor | `CTS_Real_Time_Monitor.py` | Run locally in parallel with Chain A |
| D — Report Generator | `QC_report_all.py` | Launched as subprocess by Chain C |
| E — Assembly Test | `femb_assembly_chk.py` | Standalone, direct WIB connection |

---

## Run Chain A — Main QC (Local Driver)

**Entry:** `CTS_FEMB_QC_top.py`
**Role:** Orchestrates the full QC sequence. Calls `cts_ssh_FEMB.py` for each test step.

```
CTS_FEMB_QC_top.py
├── cts_ssh_FEMB.py                    Core test logic, SSH to WIB
│   ├── components/assembly_log.py     Log data structures
│   ├── GUI/Rigol_DP800.py             Rigol power supply (VISA/USB)
│   └── GUI/send_email.py              Gmail SMTP notifications
├── cts_cryo_uart.py                   UART serial control
├── qc_utils.py                        QC_Process() wrapper (errors, retries, email)
│   ├── cts_ssh_FEMB.py
│   └── GUI/send_email.py
├── qc_power.py                        Safe power-off helper
├── qc_ui.py                           User input prompts
├── qc_results.py                      Result display and analysis
├── GUI/pop_window.py                  Tkinter popup windows
├── GUI/State_List.py                  Test state list GUI
├── GUI/Rigol_DP800.py
└── GUI/send_email.py
```

### QC Test Steps (driven by `QC_TST_EN` in `cts_ssh_FEMB.py`)

| Step | Value | Description |
|---|---|---|
| Init | 0 | Initialize WIB and FEMB |
| Slot Confirm | 1 | Confirm FEMB slot assignment |
| Checkout | 2 | Basic checkout |
| QC | 3 | Full QC test — triggers Chain B on WIB |
| Final Checkout | 5 | Final verification |
| Power Off | 6 | Safe power down |

---

## Run Chain B — WIB QC Test (Runs ON the WIB via SSH)

**Entry:** `QC_top.py`
**Role:** Executed remotely on the WIB by `cts_ssh_FEMB.py`. Runs the actual FEMB QC measurements.
**How invoked:** `cts_ssh_FEMB.py:1234` → `python3 QC_top.py {slot_list} -t {testid}`

```
QC_top.py
└── QC_runs.py                         QC_Runs class, test sequence runner
    ├── wib_cfgs.py                    WIB configuration class (WIB_CFGS)
    │   ├── llc.py                     Low-level C-library communication
    │   ├── fe_asic_reg_mapping.py     FE ASIC register map
    │   └── spymemory_decode.py        Spy buffer decoding
    ├── QC_components/qc_function.py   QC measurement functions
    │   ├── wib_cfgs.py
    │   └── QC_components/qc_log.py   Log data structures
    ├── QC_components/qc_log.py
    └── QC_tools.py                    Analysis algorithms
        ├── spymemory_decode.py
        ├── QC_components/qc_log.py
        └── QC_check.py                Pass/fail criteria
```

---

## Run Chain C — Real-Time Monitor (Local, Parallel Process)

**Entry:** `CTS_Real_Time_Monitor.py`
**Role:** Runs in parallel alongside Chain A. Watches test progress and triggers report generation.
**How invoked:** Launched manually before starting Chain A.

```
CTS_Real_Time_Monitor.py
└── [subprocess] QC_report_all.py     Triggered when test data is ready (Chain D)
```

---

## Run Chain D — Report Generator (Subprocess of Chain C)

**Entry:** `QC_report_all.py`
**Role:** Generates PDF and CSV reports from saved test data.
**How invoked:** `CTS_Real_Time_Monitor.py:338` → `python3 QC_report_all.py {path} -n {slot} -t {item}`

```
QC_report_all.py
└── QC_report.py                       QC_reports class, full report builder
    ├── QC_tools.py                    Analysis algorithms
    │   ├── spymemory_decode.py
    │   ├── QC_components/qc_log.py
    │   └── QC_check.py
    ├── QC_check.py
    ├── Path.py                        Path utilities
    ├── components/item_report.py      Per-item report helpers
    ├── QC_components/qc_a_function.py QC analysis functions
    │   ├── QC_tools.py
    │   ├── QC_components/qc_log.py
    │   └── QC_check.py
    ├── QC_components/qc_log.py
    ├── QC_components/All_Report.py    Full report assembly
    │   └── QC_components/qc_log.py
    └── QC_components/QC_CSV_Report.py CSV report generation
        ├── QC_components/qc_log.py
        └── QC_components/csv_style.py CSV formatting styles
```

---

## Run Chain E — FEMB Assembly Test (Standalone)

**Entry:** `femb_assembly_chk.py`
**Role:** Standalone assembly-level test with direct WIB connection. Independent of Chains A–D.

```
femb_assembly_chk.py
├── wib_cfgs.py                        WIB configuration class (WIB_CFGS)
│   ├── llc.py                         Low-level C-library communication
│   ├── fe_asic_reg_mapping.py         FE ASIC register map
│   └── spymemory_decode.py            Spy buffer decoding
├── components/assembly_parameter.py   Test limits and thresholds
├── components/assembly_log.py         Log data structures
├── components/assembly_function.py    Test measurement functions
│   ├── wib_cfgs.py
│   ├── QC_tools.py
│   │   ├── spymemory_decode.py
│   │   ├── QC_components/qc_log.py
│   │   └── QC_check.py
│   ├── components/assembly_log.py
│   └── QC_check.py
├── components/assembly_report.py      PDF report generation
└── components/assembly_CSV_report.py  CSV report generation
```

### Assembly Test Sequence

| Part | Step | Description |
|---|---|---|
| 01 | Input | Collect operator info, FEMB IDs, environment |
| 02 | Power | Initial current measurement and register check |
| 03 | SE | Single-ended noise, power, LDO rails, pulse response |
| 04 | DIFF | Differential pulse, power, LDO rails |
| 05 | Monitor | Monitor path analysis |
| — | Report | Generate PDF and CSV final report |

---

## Scripts NOT Used in Any Project Run

### Old Versions / Backups

| File | Notes |
|---|---|
| `CTS_FEMB_QC_top_0.py` | Old version of main entry |
| `CTS_FEMB_QC_top1202.py` | Old version (Dec 2) |
| `CTS_FEMB_QC_top1222.py` | Old version (Dec 22) |
| `cts_ssh_FEMB_0.py` | Old version of SSH core |
| `cts_ssh_FEMB_1202.py` | Old version (Dec 2) |
| `cts_ssh_FEMB120202.py` | Old version |
| `femb_assembly_chk_backup.py` | Backup of assembly test |
| `llc_back.py` | Backup of LLC module |
| `QC_components/backup.py` | Backup |
| `QC_components/back.py` | Backup |
| `QC_components/backup2025.py` | Backup (2025) |
| `QC_components/qc_a_function_back.py` | Backup of analysis function |

### Standalone Checkout / Powering Scripts

| File | Description |
|---|---|
| `CTS_Checkout.py` | Standalone checkout script |
| `top_checkout.py` | Standalone checkout |
| `top_chkout_mon.py` | Checkout with monitor |
| `top_chkout_pls_fake_timing.py` | Checkout with fake timing pulse |
| `top_chkout_pls_p11.py` | Checkout pulse P11 |
| `top_dac_set.py` | DAC setting tool |
| `top_ext_cali.py` | External calibration |
| `top_ext_cali_period.py` | External calibration (period) |
| `top_femb_powering.py` | FEMB power control (room temp) |
| `top_femb_powering_LN.py` | FEMB power control (LN2) |

### Standalone Test / Debug

| File | Description |
|---|---|
| `FEMB_BIST.py` | Built-in self test |
| `FEMB_CHK.py` | FEMB checker |
| `CE_item17.py` | CE item 17 test |
| `CE_regulator_output_monitor.py` | Regulator output monitor |
| `cts_noise_debug.py` | Noise debug tool |
| `debug.py` | General debug script |
| `qc_test.py` | QC test runner (dev) |
| `testing.py` | Testing script |
| `testing2.py` | Testing script v2 |
| `test_py.py` | Python test |
| `quick_script.py` | Quick utility |
| `dat_cfg.py` | Data config tool |

### Standalone Analysis Tools

| File | Description |
|---|---|
| `adc_hist.py` | ADC histogram tool |
| `adc_hist_plot.py` | ADC histogram plotting |
| `TestPattern_chk.py` | Test pattern checker |
| `TP_tools.py` | Test pattern analysis tools |
| `ana_femb_assembly_chk.py` | Offline analysis of assembly test data |
| `fft_chn.py` | FFT per channel analysis |
| `compare_decodes.py` | Decode comparison utility |

### Data Reading Demos

| File | Description |
|---|---|
| `dunedaq_decode.py` | DUNE DAQ decode demo |
| `rd_demo_dunedaq.py` | Read demo (DUNE DAQ) |
| `rd_demo_raw_hermes.py` | Read demo (raw Hermes) |

### Unused GUI Tools

| File | Description |
|---|---|
| `DUNE_QC_GUI.py` | Standalone GUI application |
| `GUI/initial_part.py` | GUI initialization helper |
| `GUI/Git_Syn.py` | Git sync utility |
| `GUI/wib_initial.py` | WIB initialization GUI |
| `GUI/Tera.py` | Tera terminal GUI |
| `GUI/initial_csv.py` | Initial CSV GUI |

### Unused Component Modules

| File | Notes |
|---|---|
| `components/analysis.py` | Not imported in any active chain |
| `components/analysis2.py` | Not imported in any active chain |
| `components/qc_log.py` | Unused (active chain uses `QC_components/qc_log.py`) |
| `components/Cable_assembly_report.py` | Not imported in any active chain |

---

## Summary Count

| Category | Count |
|---|---|
| Active scripts — Chain A (Main QC, local) | 11 |
| Active scripts — Chain B (WIB QC test, on WIB) | 8 |
| Active scripts — Chain C (Real-Time Monitor) | 1 |
| Active scripts — Chain D (Report generator) | 10 |
| Active scripts — Chain E (Assembly test) | 10 |
| Old versions / backups | 12 |
| Standalone scripts | 26 |
| Unused component modules | 4 |
| **Total project scripts** | **82** |
