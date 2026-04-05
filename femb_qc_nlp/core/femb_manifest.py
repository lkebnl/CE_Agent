"""
femb_manifest.py — Acquisition manifest management.

Manages the bidirectional mapping between configuration parameters and
data file names for the FEMB QC NLP system.

acquisition_manifest.json format:
{
  "created_at": "2025-04-05 14:30:00",
  "pc_data_dir": "./data/20250405_143000/",
  "fembs": [0, 1],
  "operator": "Lke",
  "env": "RT",
  "acquisitions": [
    {
      "file": "RMS_SE_200mVBL_14_0mVfC_2_0us_0x00.bin",
      "config": {
        "mode": "SE",
        "snc": 1,   "snc_label": "200mV",
        "sg0": 0,   "sg1": 0,   "gain_label": "14mV/fC",
        "st0": 1,   "st1": 1,   "peaking_label": "2us",
        "dac": "0x00"
      },
      "num_samples": 10,
      "timestamp": "2025-04-05 14:30:05"
    },
    ...
  ]
}
"""

import json
import os
import datetime

from core.femb_constants import (
    GAIN_MAP, PEAKING_MAP, BASELINE_MAP,
    GAIN_TAG, PEAKING_TAG, BASELINE_TAG,
)


def generate_filename(mode, snc, sg0, sg1, st0, st1, dac=0):
    """
    Generate a file name compatible with QC_runs.py naming conventions.

    Parameters
    ----------
    mode : str
        Acquisition mode, e.g. "SE".
    snc : int
        Baseline code: 1 = 200mV, 0 = 900mV.
    sg0, sg1 : int
        Gain bits.
    st0, st1 : int
        Peaking-time bits.
    dac : int
        DAC value (default 0).

    Returns
    -------
    str
        File name, e.g. "RMS_SE_200mVBL_14_0mVfC_2_0us_0x00.bin"
    """
    bl_tag  = BASELINE_TAG[snc]
    gain_tag = GAIN_TAG[(sg0, sg1)]
    peak_tag = PEAKING_TAG[(st0, st1)]
    dac_hex  = "0x{:02X}".format(dac)
    return "RMS_{mode}_{bl}_{gain}_{peak}_{dac}.bin".format(
        mode=mode,
        bl=bl_tag,
        gain=gain_tag,
        peak=peak_tag,
        dac=dac_hex,
    )


def parse_filename(fname):
    """
    Reverse-parse a file name into configuration parameters.

    Parameters
    ----------
    fname : str
        File name such as "RMS_SE_200mVBL_14_0mVfC_2_0us_0x00.bin".

    Returns
    -------
    dict
        {'mode', 'snc', 'snc_label', 'gain_label',
         'peaking_label', 'sg0', 'sg1', 'st0', 'st1', 'dac'}
    """
    # Strip directory path and extension
    base = os.path.basename(fname)
    if base.endswith(".bin"):
        base = base[:-4]

    # Expected tokens after splitting on "_":
    # RMS_SE_200mVBL_14_0mVfC_2_0us_0x00
    # [0]  [1] [2]   [3][4]   [5][6] [7]
    # parts[0] = "RMS"
    # parts[1] = mode  (e.g. "SE")
    # parts[2] = bl tag  (e.g. "200mVBL" — single token, no underscore)
    # parts[3..4] = gain tag (e.g. "14" + "0mVfC" → "14_0mVfC")
    # parts[5..6] = peak tag (e.g. "2" + "0us"   → "2_0us")
    # parts[7]   = dac hex  (e.g. "0x00")
    parts = base.split("_")

    if len(parts) < 8 or parts[0] != "RMS":
        raise ValueError("Cannot parse filename: {}".format(fname))

    mode     = parts[1]
    bl_tag   = parts[2]                      # e.g. "200mVBL" or "900mVBL"
    gain_tag = parts[3] + "_" + parts[4]     # e.g. "14_0mVfC"
    peak_tag = parts[5] + "_" + parts[6]     # e.g. "2_0us"
    dac_str  = parts[7]                      # e.g. "0x00"

    # Reverse lookups
    snc_label_map = {v: k for k, v in BASELINE_TAG.items()}   # "200mVBL" → 1
    gain_tag_map  = {v: k for k, v in GAIN_TAG.items()}       # "14_0mVfC" → (0,0)
    peak_tag_map  = {v: k for k, v in PEAKING_TAG.items()}    # "2_0us" → (1,1)

    snc = snc_label_map[bl_tag]
    sg0, sg1 = gain_tag_map[gain_tag]
    st0, st1 = peak_tag_map[peak_tag]

    # Build human-readable labels (reverse of BASELINE_MAP, GAIN_MAP, PEAKING_MAP)
    bl_label_map = {v: k for k, v in BASELINE_MAP.items()}   # 1 → "200mV"
    gain_label_map = {}
    for label, (g0, g1) in GAIN_MAP.items():
        # prefer the shorter canonical key
        key = (g0, g1)
        if key not in gain_label_map or len(label) < len(gain_label_map[key]):
            gain_label_map[key] = label
    peak_label_map = {}
    for label, (p0, p1) in PEAKING_MAP.items():
        key = (p0, p1)
        if key not in peak_label_map or len(label) < len(peak_label_map[key]):
            peak_label_map[key] = label

    return {
        "mode":          mode,
        "snc":           snc,
        "snc_label":     bl_label_map[snc],
        "sg0":           sg0,
        "sg1":           sg1,
        "gain_label":    gain_label_map[(sg0, sg1)],
        "st0":           st0,
        "st1":           st1,
        "peaking_label": peak_label_map[(st0, st1)],
        "dac":           dac_str,
    }


def create_manifest(data_dir, fembs, operator, env):
    """
    Create an empty acquisition manifest and save it to disk.

    Parameters
    ----------
    data_dir : str
        Local PC data directory for this test session.
    fembs : list
        List of FEMB slot numbers, e.g. [0, 1].
    operator : str
        Operator name.
    env : str
        Test environment: "RT" or "LN".

    Returns
    -------
    dict
        The newly created manifest.
    """
    manifest = {
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pc_data_dir": data_dir,
        "fembs":       fembs,
        "operator":    operator,
        "env":         env,
        "acquisitions": [],
    }
    os.makedirs(data_dir, exist_ok=True)
    manifest_path = os.path.join(data_dir, "acquisition_manifest.json")
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


def add_acquisition(manifest, file, config, num_samples):
    """
    Append one acquisition record to the manifest and persist it.

    Parameters
    ----------
    manifest : dict
        Manifest dict (created by create_manifest or load_manifest).
    file : str
        Data file name (basename only, e.g. "RMS_SE_200mVBL_...bin").
    config : dict
        Configuration dictionary matching the manifest schema.
    num_samples : int
        Number of spy-buffer samples acquired.

    Returns
    -------
    dict
        Updated manifest.
    """
    entry = {
        "file":        file,
        "config":      config,
        "num_samples": num_samples,
        "timestamp":   datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    manifest["acquisitions"].append(entry)
    data_dir = manifest["pc_data_dir"]
    manifest_path = os.path.join(data_dir, "acquisition_manifest.json")
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


def load_manifest(manifest_path):
    """
    Load an existing acquisition manifest from disk.

    Parameters
    ----------
    manifest_path : str
        Path to acquisition_manifest.json.

    Returns
    -------
    dict
        The manifest dictionary.
    """
    with open(manifest_path, "r") as fh:
        return json.load(fh)


def find_files_by_config(manifest, snc_label=None, gain_label=None,
                         peaking_label=None, mode=None):
    """
    Filter acquisition records by configuration criteria.

    Parameters
    ----------
    manifest : dict
        Loaded manifest.
    snc_label : str or None
        Baseline label, e.g. "200mV". None means no filter.
    gain_label : str or None
        Gain label, e.g. "14mV/fC". None means no filter.
    peaking_label : str or None
        Peaking-time label, e.g. "2us". None means no filter.
    mode : str or None
        Mode string, e.g. "SE". None means no filter.

    Returns
    -------
    list
        List of matching acquisition entry dicts.
    """
    results = []
    for acq in manifest.get("acquisitions", []):
        cfg = acq.get("config", {})

        if snc_label is not None and cfg.get("snc_label") != snc_label:
            continue
        if gain_label is not None and cfg.get("gain_label") != gain_label:
            continue
        if peaking_label is not None and cfg.get("peaking_label") != peaking_label:
            continue
        if mode is not None and cfg.get("mode") != mode:
            continue

        results.append(acq)
    return results
