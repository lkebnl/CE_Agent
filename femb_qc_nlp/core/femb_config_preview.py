# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : Pre-execution config preview TXT generation and y/e/n user confirmation flow
"""
femb_config_preview.py — Config preview TXT generator and parser.

Generates a human-readable, editable TXT file from parsed intent params.
The tester can review, approve, or edit params before execution.

TXT format uses simple "key : value" lines grouped by section headers.
Designed to be both human-friendly and machine-parseable.
"""

import json
import os
import re
from datetime import datetime


# ── Section keys (order matters for display) ────────────────────────────────

_INTENT_KEYS   = ["intent", "confidence"]
_HW_KEYS       = ["fembs", "operator", "env"]
_ASIC_KEYS     = ["snc", "gain", "peaking"]
_ACQ_KEYS      = ["num_samples"]
_CHANNEL_KEYS  = ["chips", "chip_channels", "global_channels"]

_ALL_PARAM_KEYS = _HW_KEYS + _ASIC_KEYS + _ACQ_KEYS + _CHANNEL_KEYS

_HELP_BLOCK = """\
# ── Edit Instructions ─────────────────────────────────────────────────────────
# Edit the parameter values above directly, save the file, then press Enter
# in the terminal to continue.
# Lines that do not need changes can be left as-is; comment lines (starting
# with #) are ignored.
#
# Allowed values:
#   env         : RT (room temperature) | LN (liquid nitrogen)
#   snc         : 200mV | 900mV
#   gain        : 4.7mV/fC | 7.8mV/fC | 14mV/fC | 25mV/fC
#   peaking     : 0.5us | 1us | 2us | 3us
#   fembs       : single slot [0]  multiple slots [0, 1]
#   chips       : silkscreen list ["U03"] or chip number [3], set null to skip filtering
#   chip_channels: {"U03": [11]} format, set null to skip filtering
#   global_channels: [48, 59] format, set null to skip filtering
#   num_samples : integer, recommended 10
# ─────────────────────────────────────────────────────────────────────────────
"""


def generate_config_txt(intent_dict):
    """
    Generate a human-readable config preview string from parsed intent dict.

    Parameters
    ----------
    intent_dict : dict
        Output of FEMBNLAgent.parse_intent(). Must have 'intent', 'params',
        'confidence' keys.

    Returns
    -------
    str
        Formatted preview text.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    intent_name = intent_dict.get("intent", "unknown")
    confidence  = intent_dict.get("confidence", 0.0)
    params      = intent_dict.get("params", {})

    lines = []
    lines.append("=" * 60)
    lines.append("  FEMB QC Test Configuration Preview")
    lines.append("  Generated : {}".format(now_str))
    lines.append("=" * 60)
    lines.append("")

    # [Intent]
    lines.append("[Intent]")
    lines.append("intent      : {}".format(intent_name))
    lines.append("confidence  : {:.0%}".format(confidence))
    lines.append("")

    # [Hardware Configuration]
    lines.append("[Hardware Configuration]")
    lines.append("fembs       : {}".format(_fmt_val(params.get("fembs"))))
    lines.append("operator    : {}".format(_fmt_val(params.get("operator"))))
    lines.append("env         : {}".format(_fmt_val(params.get("env"))))
    lines.append("")

    # [LArASIC Configuration]
    lines.append("[LArASIC Configuration]")
    lines.append("snc         : {}".format(_fmt_val(params.get("snc"))))
    lines.append("gain        : {}".format(_fmt_val(params.get("gain"))))
    lines.append("peaking     : {}".format(_fmt_val(params.get("peaking"))))
    lines.append("")

    # [Acquisition Parameters]
    lines.append("[Acquisition Parameters]")
    lines.append("num_samples : {}".format(_fmt_val(params.get("num_samples"))))
    lines.append("")

    # [Channel Filter]
    lines.append("[Channel Filter]")
    lines.append("chips            : {}".format(_fmt_val(params.get("chips"))))
    lines.append("chip_channels    : {}".format(_fmt_val(params.get("chip_channels"))))
    lines.append("global_channels  : {}".format(_fmt_val(params.get("global_channels"))))
    lines.append("")

    lines.append("=" * 60)
    lines.append(_HELP_BLOCK)

    return "\n".join(lines)


def save_config_preview(config_txt, save_dir="./config_previews"):
    """
    Save the config preview string to a timestamped TXT file.

    Parameters
    ----------
    config_txt : str
        Output of generate_config_txt().
    save_dir : str
        Directory to save into (created if missing).

    Returns
    -------
    str
        Absolute path to the saved file.
    """
    os.makedirs(save_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = "config_preview_{}.txt".format(ts)
    fpath = os.path.join(save_dir, fname)
    with open(fpath, "w", encoding="utf-8") as fh:
        fh.write(config_txt)
    return os.path.abspath(fpath)


def parse_config_txt(txt_path):
    """
    Parse an (optionally edited) config preview TXT back to a params dict.

    Only reads lines matching "key : value" pattern outside comment lines.
    Lines starting with '#' are ignored.

    Parameters
    ----------
    txt_path : str
        Path to the TXT file.

    Returns
    -------
    dict
        Params dict with same structure as intent_dict['params'].
        Also includes 'intent' and 'confidence' keys at top level.
    """
    result = {}
    with open(txt_path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            # Skip comments, blank lines, section headers, separators
            if not line or line.startswith("#") or line.startswith("=") or line.startswith("["):
                continue
            # Match "key : value"
            m = re.match(r'^([\w_]+)\s*:\s*(.*)$', line)
            if not m:
                continue
            key   = m.group(1).strip()
            value = m.group(2).strip()
            result[key] = _parse_val(value)

    # Split intent-level keys from params
    intent_level = {}
    params = {}
    for k, v in result.items():
        if k in ("intent", "confidence"):
            intent_level[k] = v
        else:
            params[k] = v

    intent_level["params"] = params
    return intent_level


def confirm_config(intent_dict, save_dir="./config_previews"):
    """
    Display config preview, prompt tester to confirm, edit, or cancel.

    Interactive flow:
      y / Enter  → proceed with current params
      e          → open file for editing, re-read after tester saves
      n          → cancel, returns None

    Parameters
    ----------
    intent_dict : dict
        Output of FEMBNLAgent.parse_intent().
    save_dir : str
        Where to save the preview TXT.

    Returns
    -------
    dict or None
        Updated intent_dict with possibly edited params, or None if cancelled.
    """
    config_txt = generate_config_txt(intent_dict)
    fpath = save_config_preview(config_txt, save_dir=save_dir)

    # Display
    print("\n" + config_txt)
    print("[Config saved to] {}".format(fpath))
    print("")

    while True:
        print("Options:")
        print("  [y / Enter] Confirm and continue")
        print("  [e]         Edit config file then press Enter to continue")
        print("  [n]         Cancel")
        try:
            answer = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"

        if answer in ("", "y", "yes", "ok"):
            # Use current (or last-read) params
            return intent_dict

        elif answer in ("e", "edit"):
            print("\nPlease edit the file: {}".format(fpath))
            print("Save when done, then press Enter to continue...")
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                pass
            # Re-read edited file
            try:
                edited = parse_config_txt(fpath)
                # Merge edited values back: keep intent name from original if missing
                if "intent" not in edited:
                    edited["intent"] = intent_dict.get("intent", "unknown")
                if "confidence" not in edited:
                    edited["confidence"] = intent_dict.get("confidence", 0.0)
                # Show updated preview
                print("\n[Updated Parameters]")
                for k, v in edited.get("params", {}).items():
                    if v is not None:
                        print("  {:20s}: {}".format(k, v))
                print("")
                # Confirm again
                intent_dict = edited
                # Regenerate and overwrite preview with edited values
                updated_txt = generate_config_txt(intent_dict)
                with open(fpath, "w", encoding="utf-8") as fh:
                    fh.write(updated_txt)
            except Exception as exc:
                print("[Error] Failed to parse config file: {}".format(exc))
                print("Please re-edit the file.")
            # Loop back to prompt

        elif answer in ("n", "no", "cancel"):
            print("[Cancelled]")
            return None

        else:
            print("Please enter y / e / n")


# ── Internal helpers ─────────────────────────────────────────────────────────

def _fmt_val(v):
    """Format a Python value for display in the TXT."""
    if v is None:
        return "null"
    if isinstance(v, list):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _parse_val(s):
    """
    Parse a string value back to Python type.

    Handles: null, JSON arrays/objects, integers, floats, plain strings.
    """
    if s.lower() == "null" or s == "":
        return None
    # JSON array or object
    if s.startswith("[") or s.startswith("{"):
        try:
            return json.loads(s)
        except ValueError:
            return s
    # Integer
    try:
        return int(s)
    except ValueError:
        pass
    # Float
    try:
        return float(s)
    except ValueError:
        pass
    return s
