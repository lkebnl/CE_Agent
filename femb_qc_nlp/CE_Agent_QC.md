# CE Agent QC — System Flow Diagram

FEMB QC natural-language driven system, located in `femb_qc_nlp/`.

---

## Overall Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         femb_qc_nlp/                            │
│                                                                 │
│   main.py          ← entry point, sys.path config, interactive loop    │
│   agent/           ← NL parsing + intent dispatch layer                │
│   core/            ← SSH control + data analysis layer                  │
│   scripts/         ← WIB-side atomic scripts (SCP-pushed, run on WIB)  │
│   config/          ← femb_info_implement.csv                           │
│   data/            ← locally collected data + manifest                  │
│   ssh_commands/    ← complete .sh scripts generated per acquisition     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Complete Execution Flow

```mermaid
flowchart TD
    %% ── Entry ─────────────────────────────────────────────────────
    A([User Input\nInteractive mode / single command]) --> B

    subgraph MAIN["main.py"]
        B[sys.path adds\nfemb_qc_nlp/ and\nBNL_CE_WIB_SW_QC/]
        B --> C[FEMBNLAgent init\nload femb_function_registry.json]
    end

    C --> D

    %% ── NL Parsing Layer ─────────────────────────────────────────────
    subgraph AGENT["agent/femb_nl_agent.py  —  FEMBNLAgent"]
        D[execute\nuser_input] --> E

        subgraph PARSE["parse_intent()"]
            E[build messages\nsystem_prompt + few_shots\n+ user_input] --> F
            F["_call_ollama()\nPOST /api/chat\nmodel=qwen3:8b\nthink=False\nnum_predict=400\ntimeout=300s"] --> G
            G[parse JSON response\nintent_dict]
        end

        G --> H

        subgraph PREVIEW["core/femb_config_preview.py"]
            H[confirm_config\ngenerate config_preview_*.txt\ndisplay full parameter preview] --> I{User confirm\ny / e / n}
            I -- e --> H
            I -- n --> Z1([Cancel exit])
            I -- y --> J
        end

        J[_map_intent_to_action\nintent → callable] --> K

        subgraph DISPATCH["Intent Dispatch"]
            K{intent}
            K -- run_single --> L1[_action_run_single_config]
            K -- run_rms --> L2[_action_run_full_rms]
            K -- run_and_analyze --> L3[_action_run_and_analyze]
            K -- analyze_rms --> L4[_action_analyze_rms]
            K -- power_on --> L5[_action_power_on]
            K -- power_off --> L6[_action_power_off]
        end
    end

    %% ── SSH Control Layer ────────────────────────────────────────────
    subgraph SSH["core/femb_ssh_lib.py"]

        subgraph SINGLE["run_single_config(slots, snc, sg, st, ...)"]
            M0[build all step lists\ninit_steps / power_steps\natom steps] --> M1
            M1["save_ssh_commands()\ngenerate ssh_commands/ssh_cmd_*.sh\nSection 0~5 complete record"] --> M2

            subgraph INIT["Layer 0 — wib_init()"]
                M2[wib_time_sync\nSSH: date -s 'UTC'] --> M3
                M3[wib_startup\nSSH: python3 wib_startup.py\nwait for Done] --> M4
                M4{cfg_push\nfemb_info_implement.csv\nexists?}
                M4 -- exists --> M4A[SCP push → WIB\nSCP readback ← WIB\nfilecmp verify]
                M4 -- not found --> M4B[WARNING skip]
            end

            M4A --> M5
            M4B --> M5

            subgraph POWER["Layer 1 — femb_power_on(slots, env)"]
                M5{env == LN?}
                M5 -- yes --> M5A[SSH: top_femb_powering_LN.py\non/off × 4\nsleep 2s]
                M5 -- no --> M5B
                M5A --> M5B[SSH: top_femb_powering.py\non/off × 4\ncheck SLOT#N Power Connection Normal]
            end

            M5B --> M6[push_atoms_to_wib\nSCP: scripts/wib_atoms/*.py\n→ WIB /atoms/]

            subgraph ATOMS["Layer 2 — Atom Script Sequence (SSH)"]
                M6 --> M7[wib_coldata_reset.py\nslots  timeout=30s]
                M7 --> M8[wib_adc_autocali.py\nslots  timeout=120s]
                M8 --> M9["wib_fe_configure.py\nslots --snc --sg0 --sg1 --st0 --st1\ntimeout=60s"]
                M9 --> M10[wib_data_align.py\nslots  timeout=30s]
                M10 --> M11["wib_acquire.py\nslots --samples N --output *.bin\ntimeout=120s"]
            end

            M11 --> M12[pull_qc_data\nSCP: WIB /QC/ → ./data/YYYYMMDD_HHMMSS/]
            M12 --> M13[clean_wib_data\nSSH: rm -rf /QC/]
            M13 --> M14[femb_power_off\nSSH: top_femb_powering.py\noff off off off]
            M14 --> M15[create_manifest\nadd_acquisition\nacquisition_manifest.json]
        end

        subgraph MATRIX["run_config_matrix(slots, snc_list, gain_list, peaking_list)"]
            N1[wib_init once] --> N2[femb_power_on once]
            N2 --> N3["run_single_config × N\ndo_init=False, do_power=False\neach config has independent .sh file"]
            N3 --> N4[femb_power_off once]
        end
    end

    L1 --> M0
    L2 --> N1
    L5 --> M5
    L6 --> M14

    %% ── Analysis Layer ────────────────────────────────────────────────
    subgraph ANALYSIS["core/femb_analysis_lib.py"]

        subgraph ANA["analyze_from_manifest(manifest_path, femb_id, ...)"]
            P1[load_manifest\nfind_files_by_config\nfilter by snc/gain/peaking] --> P2
            P2[resolve_channels\nchips / chip_channels\n/ global_channels → list] --> P3
            P3[load_rms_bin\npickle.load .bin] --> P4
            P4["decode_to_channels()\ncall spymemory_decode.wib_dec\n→ femb_id: ch: np.ndarray"] --> P5
            P5["compute_rms()\nper channel ped=mean\nrms=std\nped_max/min"] --> P6
            P6["check_passfail()\nped > 1500 ADC?\nrms deviates from median > 60%?"] --> P7

            P7{Channel subset\nselected?}

            P7 -- yes --> P8

            subgraph PEDPLOT["plot_pedestal()"]
                P8["Top: time trace\nX=sample index  Y=ADC counts\nall selected channels overlaid\ny_lo=min(ped_min)-3σ\ny_hi=max(ped_max)+3σ"] --> P9
                P9["Bottom: Histogram\nX=ADC counts (same Y range as top)\nY=Entries  [0, max×1.15]\nstep line\n≤16ch overlay / >16ch subplot grid"]
            end

            P7 -- no --> P10

            subgraph RMSPLOT["plot_rms_128ch() / plot_rms_compare()"]
                P10[128ch RMS overview\nX=channel number  Y=RMS ADC\nchip boundary silkscreen labels] --> P11{Multiple configs?}
                P11 -- yes --> P12[plot_rms_compare\nmulti-config overlay comparison]
            end
        end
    end

    M15 --> ANA
    L3 --> M0
    L3 -. after acquisition .-> ANA
    L4 --> ANA

    %% ── Output ──────────────────────────────────────────────────────────
    P9 --> OUT
    P10 --> OUT
    P12 --> OUT
    P6 --> OUT

    OUT[/"Output\n• summary string (PASS/FAIL + bad channels)\n• PNG images saved to data/.../analysis_results/\n• acquisition_manifest.json\n• ssh_commands/ssh_cmd_*.sh"/]

    %% ── Styles ──────────────────────────────────────────────────────────
    style MAIN fill:#e8f4f8,stroke:#2196F3
    style AGENT fill:#f3e8ff,stroke:#9C27B0
    style PARSE fill:#fce8ff,stroke:#BA68C8
    style PREVIEW fill:#fce8ff,stroke:#BA68C8
    style DISPATCH fill:#fce8ff,stroke:#BA68C8
    style SSH fill:#e8ffe8,stroke:#4CAF50
    style SINGLE fill:#f0fff0,stroke:#66BB6A
    style INIT fill:#e0f7e0,stroke:#81C784
    style POWER fill:#e0f7e0,stroke:#81C784
    style ATOMS fill:#e0f7e0,stroke:#81C784
    style MATRIX fill:#f0fff0,stroke:#66BB6A
    style ANALYSIS fill:#fff8e8,stroke:#FF9800
    style ANA fill:#fffaee,stroke:#FFA726
    style PEDPLOT fill:#fff3e0,stroke:#FFB74D
    style RMSPLOT fill:#fff3e0,stroke:#FFB74D
```

---

## File Responsibility Quick Reference

| File | Layer | Responsibility |
|------|-------|----------------|
| `main.py` | Entry | sys.path config, interactive loop, single-shot execution |
| `agent/femb_nl_agent.py` | Agent | NL parsing, intent dispatch, result aggregation |
| `agent/femb_prompt_templates.py` | Agent | system prompt (with `/no_think`) + 6 few-shot examples |
| `core/femb_config_preview.py` | Core | Pre-execution parameter preview + y/e/n user confirmation |
| `core/femb_ssh_lib.py` | Core | All SSH/SCP operations, split into Layer 0/1/2 |
| `core/femb_analysis_lib.py` | Core | Local data decoding, RMS calculation, plotting |
| `core/femb_manifest.py` | Core | Acquisition record creation/reading/querying |
| `core/femb_constants.py` | Core | WIB address, Gain/Peaking/Baseline mapping tables |
| `scripts/wib_atoms/*.py` | WIB-side | Atomic operation scripts executed on the WIB |

---

## Intent → Execution Path Reference

| User Says | intent | Execution Path |
|-----------|--------|----------------|
| Acquire FEMB 3 data, 200mV 14mVfC 2us | `run_single` | wib_init → power_on → atoms×5 → pull → power_off |
| Measure FEMB 0 noise for all configs | `run_rms` | run_full_rms → QC_top.py -t 5 |
| Acquire and analyze FEMB 3, 200mV 14mVfC 2us | `run_and_analyze` | run_single → analyze_from_manifest |
| Analyze U03 chip RMS | `analyze_rms` | analyze_from_manifest → plot_rms_128ch |
| View chip3 channel 11 baseline | `analyze_rms` | analyze_from_manifest → plot_pedestal |
| Power on FEMB 0 | `power_on` | femb_power_on |
| Power off | `power_off` | femb_power_off |

---

## SSH Command File Structure (ssh_cmd_*.sh)

Generated before each `run_single_config()` call, contains the complete flow:

```bash
# Section 0: WIB Initialization
ssh root@192.168.121.123 "date -s '...'"                    # timeout=15s
ssh root@192.168.121.123 "cd ...; python3 wib_startup.py"  # timeout=60s
scp femb_info_implement.csv root@...:...                    # config push
scp root@...:... ./readback/                                # config verify

# Section 1: FEMB Power On
ssh root@192.168.121.123 "cd ...; python3 top_femb_powering.py off off off on"  # timeout=120s

# Section 2: Atom Scripts
ssh ... wib_coldata_reset.py 3     # timeout=30s
ssh ... wib_adc_autocali.py 3      # timeout=120s
ssh ... wib_fe_configure.py 3 ...  # timeout=60s
ssh ... wib_data_align.py 3        # timeout=30s
ssh ... wib_acquire.py 3 ...       # timeout=120s

# Section 3: Pull Data
scp -r root@...:QC/ ./data/YYYYMMDD_HHMMSS/

# Section 4: Clean WIB
ssh root@... "rm -rf .../QC"

# Section 5: FEMB Power Off
ssh root@... "cd ...; python3 top_femb_powering.py off off off off"  # timeout=60s
```

---

## Ollama Call Parameters

```python
{
    "model":   "qwen3:8b",
    "think":   False,        # disable chain-of-thought to avoid timeout
    "stream":  False,
    "options": {
        "temperature": 0.1,  # low temperature ensures deterministic JSON output
        "num_predict": 400,  # limit max tokens (JSON < 300 tokens)
    },
    "timeout": 300,          # requests timeout
}
```
