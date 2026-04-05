"""
femb_analysis_lib.py — PC-local data analysis for FEMB QC NLP system.

No SSH calls here — all operations are purely local.

Core dependencies:
  - spymemory_decode.wib_dec   (decode spy buffer raw data)
  - QC_check.CHKPulse          (Pass/Fail determination)

NOTE: spymemory_decode and QC_check live in the parent repository
(/home/ke/BNL_CE_WIB_SW_QC/). They may not be importable on an isolated PC
without the parent repo on sys.path. The imports are wrapped in try/except.
"""

import os
import sys
import pickle
import logging
import numpy as np

# Try to import wib_dec from the parent repo
try:
    from spymemory_decode import wib_dec as _wib_dec
    _WIBD_AVAILABLE = True
except ImportError:
    _WIBD_AVAILABLE = False
    _wib_dec = None

# Try to import QC_check for CHKPulse
try:
    import QC_check as _qc_check
    _QCCHECK_AVAILABLE = True
except ImportError:
    _QCCHECK_AVAILABLE = False
    _qc_check = None

from core.femb_constants import CHIP_CHANNEL_MAP, SILKSCREEN_TO_CHIP
from core.femb_manifest import load_manifest, find_files_by_config

log = logging.getLogger(__name__)


# ── Data Loading ────────────────────────────────────────────────────────────────

def load_rms_bin(filepath):
    """
    Load a single RMS bin file saved in the QC_runs format.

    The file contains a pickle of [rawdata, cfg_paras_rec, fembs].

    Parameters
    ----------
    filepath : str
        Absolute or relative path to the .bin file.

    Returns
    -------
    tuple
        (rawdata, cfg_paras_rec, fembs)
    """
    with open(filepath, "rb") as fh:
        data = pickle.load(fh)
    if isinstance(data, list) and len(data) == 3:
        rawdata, cfg_paras_rec, fembs = data
    else:
        rawdata = data
        cfg_paras_rec = []
        fembs = []
    return rawdata, cfg_paras_rec, fembs


def load_full_rms_dict(data_dir):
    """
    Load the item-5 full-result file QC_femb_rms_t5.bin.

    The file is a pickle dict:
    {filename: [rawdata, pwr_meas, cfg_paras_rec, logs], ...}

    Parameters
    ----------
    data_dir : str
        Local directory that contains the QC output files.

    Returns
    -------
    dict
        Keyed by filename string.
    """
    target = os.path.join(data_dir, "QC_femb_rms_t5.bin")
    if not os.path.isfile(target):
        # Search recursively
        for root, dirs, files in os.walk(data_dir):
            for fname in files:
                if fname == "QC_femb_rms_t5.bin":
                    target = os.path.join(root, fname)
                    break
    with open(target, "rb") as fh:
        return pickle.load(fh)


# ── Data Decoding ───────────────────────────────────────────────────────────────

def decode_to_channels(rawdata, fembs, spy_num=5):
    """
    Decode spy-buffer raw data into per-channel numpy arrays.

    Calls wib_dec() from spymemory_decode. If wib_dec is not available
    (running on a PC without the parent repo), raises ImportError with
    a helpful message.

    Data structure from wib_dec:
        wibdata[spy_idx]  — list of spy frames
        wibdata[spy_idx][femb_idx]  — channel list for that FEMB
        wibdata[spy_idx][femb_idx][ch]  — tuple of samples for channel ch

    Channels 0-63 come from CD0, channels 64-127 from CD1, with 64 channels
    each. They are concatenated by wib_dec into a 128-element list per FEMB.

    Parameters
    ----------
    rawdata : list
        Raw spy buffer data as returned by spybuf_trig() / pickle.load().
    fembs : list
        List of FEMB slot numbers present in rawdata.
    spy_num : int
        Number of spy-buffer frames to use (default 5).

    Returns
    -------
    dict
        {femb_id: channels_data}
        where channels_data[ch] is a np.ndarray of shape (N_samples,), ch=0..127.
    """
    if not _WIBD_AVAILABLE:
        raise ImportError(
            "spymemory_decode.wib_dec is not available. "
            "Ensure the parent BNL_CE_WIB_SW_QC repo is on sys.path."
        )

    wibdata = _wib_dec(rawdata, fembs=fembs, spy_num=spy_num, fastchk=False,
                       cd0cd1sync=True)

    result = {}
    for femb_id in fembs:
        # wibdata is a list of spy frames; each frame is
        # [femb0_channels, femb1_channels, femb2_channels, femb3_channels, t0max]
        # femb_channels is a list of 128 tuples (one per channel)
        all_ch_data = [[] for _ in range(128)]

        for spy_frame in wibdata:
            femb_channels = spy_frame[femb_id]
            if femb_channels is None:
                continue
            # femb_channels is a list of 128 tuples; each tuple has tick samples
            for ch in range(min(128, len(femb_channels))):
                all_ch_data[ch].extend(list(femb_channels[ch]))

        channels_data = {}
        for ch in range(128):
            if all_ch_data[ch]:
                channels_data[ch] = np.array(all_ch_data[ch], dtype=np.float64)
            else:
                channels_data[ch] = np.array([], dtype=np.float64)

        result[femb_id] = channels_data

    return result


# ── Channel Selection ────────────────────────────────────────────────────────────

def resolve_chip(chip_spec):
    """
    Resolve a chip specifier to a chip ID integer.

    Parameters
    ----------
    chip_spec : int or str
        Either a chip ID (0-7) or a silkscreen label like 'U03'.

    Returns
    -------
    int
        Chip ID (0-7).

    Raises
    ------
    ValueError
        If chip_spec cannot be resolved.
    """
    if isinstance(chip_spec, int):
        if chip_spec not in CHIP_CHANNEL_MAP:
            raise ValueError("Unknown chip_id: {}".format(chip_spec))
        return chip_spec
    if isinstance(chip_spec, str):
        # Try silkscreen lookup
        if chip_spec in SILKSCREEN_TO_CHIP:
            return SILKSCREEN_TO_CHIP[chip_spec]
        # Try integer string
        try:
            return int(chip_spec)
        except ValueError:
            pass
    raise ValueError("Cannot resolve chip spec: {!r}".format(chip_spec))


def resolve_channels(chips=None, chip_channels=None, global_channels=None):
    """
    Resolve a channel selection into a sorted list of global channel numbers.

    Priority (highest first):
      1. global_channels  — used directly
      2. chip_channels    — {chip_spec: [local_ch, ...]} dict
      3. chips            — [chip_spec, ...] list (all channels in those chips)
      4. None / all None  — all 128 channels

    Parameters
    ----------
    chips : list or None
        List of chip specs (int or silkscreen str), e.g. [3, 'U07'].
    chip_channels : dict or None
        Mapping chip_spec → list of local channel indices,
        e.g. {'U03': [11], 3: [0, 1]}.
    global_channels : list or None
        Direct list of global channel numbers, e.g. [48, 49, 59].

    Returns
    -------
    list
        Sorted list of unique global channel numbers (0-127).
    """
    if global_channels is not None:
        return sorted(set(int(c) for c in global_channels))

    if chip_channels is not None:
        result = set()
        for chip_spec, local_chs in chip_channels.items():
            chip_id = resolve_chip(chip_spec)
            _, ch_start, _ = CHIP_CHANNEL_MAP[chip_id]
            for lch in local_chs:
                result.add(ch_start + int(lch))
        return sorted(result)

    if chips is not None:
        result = set()
        for chip_spec in chips:
            chip_id = resolve_chip(chip_spec)
            _, ch_start, ch_end = CHIP_CHANNEL_MAP[chip_id]
            result.update(range(ch_start, ch_end + 1))
        return sorted(result)

    # Default: all 128 channels
    return list(range(128))


# ── RMS Computation ─────────────────────────────────────────────────────────────

def compute_rms(channels_data, femb_id, target_channels=None):
    """
    Compute pedestal and RMS for each (selected) channel.

    Ported from ana_tools.GetRMS(), extended with channel filtering.

    Parameters
    ----------
    channels_data : dict
        Output of decode_to_channels(): {femb_id: {ch: np.ndarray}}.
        Also accepts a plain {ch: np.ndarray} dict directly (for testing).
    femb_id : int
        FEMB slot to analyse.
    target_channels : list or None
        Global channel numbers to compute. None = all 128 channels.

    Returns
    -------
    dict
        {
          'femb_id': int,
          'channels': {
            'ch_000': {
              'global_ch': 0, 'chip_id': 0, 'silkscreen': 'U07', 'chip_chn': 0,
              'ped': float,
              'rms': float,
              'ped_max': float,
              'ped_min': float,
            }, ...
          },
          'summary': {
            'ped_mean': float, 'ped_std': float,
            'rms_mean': float, 'rms_std': float,
            'rms_median': float,
          }
        }
    """
    # Accept either {femb_id: {ch: arr}} or plain {ch: arr}
    if femb_id in channels_data and isinstance(channels_data[femb_id], dict):
        ch_data = channels_data[femb_id]
    else:
        ch_data = channels_data

    if target_channels is None:
        target_channels = list(range(128))

    channels_out = {}
    rms_vals = []
    ped_vals = []

    for gch in target_channels:
        # Determine chip info
        chip_id = gch // 16
        silk, ch_start, _ = CHIP_CHANNEL_MAP[chip_id]
        chip_chn = gch - ch_start

        arr = ch_data.get(gch, np.array([]))
        if len(arr) == 0:
            ped = 0.0
            rms = 0.0
            ped_max = 0.0
            ped_min = 0.0
        else:
            arr_f = arr.astype(np.float64)
            ped     = float(np.mean(arr_f))
            rms     = float(np.std(arr_f))
            ped_max = float(np.max(arr_f))
            ped_min = float(np.min(arr_f))

        key = "ch_{:03d}".format(gch)
        channels_out[key] = {
            "global_ch":  gch,
            "chip_id":    chip_id,
            "silkscreen": silk,
            "chip_chn":   chip_chn,
            "ped":        ped,
            "rms":        rms,
            "ped_max":    ped_max,
            "ped_min":    ped_min,
        }
        if len(arr) > 0:
            rms_vals.append(rms)
            ped_vals.append(ped)

    rms_arr = np.array(rms_vals) if rms_vals else np.array([0.0])
    ped_arr = np.array(ped_vals) if ped_vals else np.array([0.0])

    summary = {
        "ped_mean":   float(np.mean(ped_arr)),
        "ped_std":    float(np.std(ped_arr)),
        "rms_mean":   float(np.mean(rms_arr)),
        "rms_std":    float(np.std(rms_arr)),
        "rms_median": float(np.median(rms_arr)),
    }

    return {
        "femb_id":  femb_id,
        "channels": channels_out,
        "summary":  summary,
    }


# ── Pass / Fail Determination ────────────────────────────────────────────────────

def check_passfail(rms_result, ped_threshold=1500.0, rms_threshold=0.6):
    """
    Determine Pass/Fail status based on pedestal and RMS values.

    Loosely follows QC_check.CHKPulse() logic.

    Parameters
    ----------
    rms_result : dict
        Output of compute_rms().
    ped_threshold : float
        Maximum allowed pedestal value (ADC counts). Default 1500.
    rms_threshold : float
        Maximum allowed relative RMS deviation from the median
        (fraction of median RMS). Default 0.6 (60%).

    Returns
    -------
    dict
        {
          'pass': bool,
          'ped_status': bool,
          'rms_status': bool,
          'bad_channels': [int, ...],
          'bad_chips':    [int, ...],
          'bad_silkscreens': [str, ...],
          'summary': str,
        }
    """
    channels = rms_result.get("channels", {})
    if not channels:
        return {
            "pass": False,
            "ped_status": False,
            "rms_status": False,
            "bad_channels": [],
            "bad_chips": [],
            "bad_silkscreens": [],
            "summary": "No channel data",
        }

    rms_list = [v["rms"] for v in channels.values()]
    ped_list = [v["ped"] for v in channels.values()]
    rms_median = float(np.median(rms_list)) if rms_list else 0.0

    bad_channels = []
    bad_chips = set()
    bad_silkscreens = set()
    ped_bad = []
    rms_bad = []

    for key, ch_data in channels.items():
        gch  = ch_data["global_ch"]
        ped  = ch_data["ped"]
        rms  = ch_data["rms"]
        chip = ch_data["chip_id"]
        silk = ch_data["silkscreen"]

        ch_ped_fail = ped > ped_threshold
        ch_rms_fail = (rms_median > 0 and
                       abs(rms - rms_median) / rms_median > rms_threshold)

        if ch_ped_fail:
            ped_bad.append(gch)
        if ch_rms_fail:
            rms_bad.append(gch)

        if ch_ped_fail or ch_rms_fail:
            bad_channels.append(gch)
            bad_chips.add(chip)
            bad_silkscreens.add(silk)

    ped_status = len(ped_bad) == 0
    rms_status = len(rms_bad) == 0
    overall    = ped_status and rms_status

    if overall:
        summary_str = "PASS — all {} channels within thresholds.".format(len(channels))
    else:
        summary_str = (
            "FAIL — {n_bad}/{n_tot} channels failed. "
            "Bad chips: {chips}. Bad silkscreens: {silks}.".format(
                n_bad=len(bad_channels),
                n_tot=len(channels),
                chips=sorted(bad_chips),
                silks=sorted(bad_silkscreens),
            )
        )

    return {
        "pass":            overall,
        "ped_status":      ped_status,
        "rms_status":      rms_status,
        "bad_channels":    sorted(bad_channels),
        "bad_chips":       sorted(bad_chips),
        "bad_silkscreens": sorted(bad_silkscreens),
        "summary":         summary_str,
    }


# ── Plotting ─────────────────────────────────────────────────────────────────────

def plot_rms_128ch(rms_result, config_label, save_path=None, show=False):
    """
    Plot 128-channel RMS distribution (mirrors ana_tools._plot_data()).

    X-axis: global channel number (0-127), tick marks every 16 channels.
    Y-axis: RMS in ADC counts.
    Annotations: chip silkscreen labels at chip boundaries.

    Parameters
    ----------
    rms_result : dict
        Output of compute_rms().
    config_label : str
        Plot title label, e.g. "200mV_14mVfC_2us".
    save_path : str or None
        File path to save the figure. None = do not save.
    show : bool
        Whether to display the figure interactively.
    """
    try:
        import matplotlib
        if not show:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning("matplotlib not available — skipping plot.")
        return

    channels = rms_result.get("channels", {})
    if not channels:
        log.warning("[plot_rms_128ch] No channel data to plot.")
        return

    # Build sorted arrays
    items = sorted(channels.items(), key=lambda kv: kv[1]["global_ch"])
    x_vals = [v["global_ch"] for _, v in items]
    y_rms  = [v["rms"]       for _, v in items]

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(x_vals, y_rms, marker=".", linestyle="-", alpha=0.7,
            label="RMS mean={:.2f}".format(np.mean(y_rms)))

    ax.set_title("RMS Distribution — {}".format(config_label), fontsize=13)
    ax.set_xlabel("Channel", fontsize=12)
    ax.set_ylabel("RMS (ADC counts)", fontsize=12)
    ax.set_xticks(range(0, 129, 16))
    ax.grid(axis="x")

    # Annotate chip silkscreen labels
    for chip_id, (silk, ch_start, _) in CHIP_CHANNEL_MAP.items():
        ax.axvline(x=ch_start, color="grey", linewidth=0.5, linestyle="--")
        ax.text(ch_start + 0.5, ax.get_ylim()[1] * 0.95, silk,
                fontsize=8, color="blue", va="top")

    ax.legend()
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path)
        log.info("[plot_rms_128ch] Saved → %s", save_path)

    if show:
        plt.show()
    plt.close(fig)


def plot_rms_compare(results_dict, save_path=None, show=False):
    """
    Overlay RMS distributions for multiple configurations.

    Parameters
    ----------
    results_dict : dict
        {config_label: rms_result} mapping, e.g.:
        {'200mV_14mVfC_2us': result1, '200mV_25mVfC_2us': result2}
    save_path : str or None
        File path to save the figure.
    show : bool
        Whether to display the figure interactively.
    """
    try:
        import matplotlib
        if not show:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning("matplotlib not available — skipping plot.")
        return

    fig, ax = plt.subplots(figsize=(14, 5))

    for config_label, rms_result in results_dict.items():
        channels = rms_result.get("channels", {})
        if not channels:
            continue
        items = sorted(channels.items(), key=lambda kv: kv[1]["global_ch"])
        x_vals = [v["global_ch"] for _, v in items]
        y_rms  = [v["rms"]       for _, v in items]
        ax.plot(x_vals, y_rms, marker=".", linestyle="-", alpha=0.7,
                label=config_label)

    ax.set_title("RMS Comparison", fontsize=13)
    ax.set_xlabel("Channel", fontsize=12)
    ax.set_ylabel("RMS (ADC counts)", fontsize=12)
    ax.set_xticks(range(0, 129, 16))
    ax.grid(axis="x")
    ax.legend(fontsize=8)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path)
        log.info("[plot_rms_compare] Saved → %s", save_path)

    if show:
        plt.show()
    plt.close(fig)


# ── High-level Interface (for NL Agent) ─────────────────────────────────────────

def analyze_from_manifest(manifest_path, femb_id,
                          snc_label=None, gain_label=None, peaking_label=None,
                          chips=None, chip_channels=None, global_channels=None,
                          plot=True, save_dir=None):
    """
    Phase-1 main analysis entry point.

    Loads the manifest, selects matching acquisition files, decodes them and
    runs compute_rms + check_passfail.

    Parameters
    ----------
    manifest_path : str
        Path to acquisition_manifest.json.
    femb_id : int
        FEMB slot to analyse.
    snc_label : str or None
        Baseline filter, e.g. "200mV". None = no filter.
    gain_label : str or None
        Gain filter, e.g. "14mV/fC". None = no filter.
    peaking_label : str or None
        Peaking-time filter, e.g. "2us". None = no filter.
    chips : list or None
        Chip selection (passed to resolve_channels).
    chip_channels : dict or None
        Per-chip channel selection (passed to resolve_channels).
    global_channels : list or None
        Global channel list (passed to resolve_channels).
    plot : bool
        Whether to generate figures.
    save_dir : str or None
        Directory for saved plots. Defaults to manifest directory.

    Returns
    -------
    dict
        {
          'matched_configs': int,
          'results': {
            'config_label': {
              'rms_result': dict,
              'passfail': dict,
            }, ...
          },
          'summary': str,
        }
    """
    manifest = load_manifest(manifest_path)
    data_dir = manifest.get("pc_data_dir", os.path.dirname(manifest_path))

    if save_dir is None:
        save_dir = os.path.join(data_dir, "analysis_results")
    os.makedirs(save_dir, exist_ok=True)

    # Filter acquisitions by config labels
    matching = find_files_by_config(
        manifest,
        snc_label=snc_label,
        gain_label=gain_label,
        peaking_label=peaking_label,
    )

    # Resolve target channels once
    target_channels = resolve_channels(
        chips=chips,
        chip_channels=chip_channels,
        global_channels=global_channels,
    )
    if not target_channels:
        target_channels = None  # compute_rms will use all 128

    results = {}
    rms_results_for_plot = {}

    for acq in matching:
        cfg = acq.get("config", {})
        fname = acq["file"]

        # Build label string
        parts = [
            cfg.get("snc_label", "?mV"),
            cfg.get("gain_label", "?gain"),
            cfg.get("peaking_label", "?us"),
        ]
        config_label = "_".join(str(p) for p in parts)

        # Locate the data file
        bin_path = os.path.join(data_dir, fname)
        if not os.path.isfile(bin_path):
            # Try recursive search
            found = False
            for root, dirs, files in os.walk(data_dir):
                if fname in files:
                    bin_path = os.path.join(root, fname)
                    found = True
                    break
            if not found:
                log.warning("[analyze_from_manifest] File not found: %s", fname)
                continue

        # Load and decode
        try:
            rawdata, _, fembs_in_file = load_rms_bin(bin_path)
            if femb_id not in fembs_in_file:
                log.warning("[analyze_from_manifest] femb_id=%d not in file %s",
                            femb_id, fname)
                continue
            channels_data = decode_to_channels(rawdata, fembs_in_file)
        except ImportError as exc:
            log.error("[analyze_from_manifest] Decode failed: %s", exc)
            continue
        except Exception as exc:
            log.error("[analyze_from_manifest] Error loading %s: %s", fname, exc)
            continue

        rms_result = compute_rms(channels_data, femb_id,
                                 target_channels=target_channels)
        pf_result  = check_passfail(rms_result)

        results[config_label] = {
            "rms_result": rms_result,
            "passfail":   pf_result,
        }
        rms_results_for_plot[config_label] = rms_result

        if plot:
            plot_path = os.path.join(
                save_dir, "rms_{}.png".format(config_label.replace("/", "_"))
            )
            plot_rms_128ch(rms_result, config_label, save_path=plot_path)

    # Comparison plot when multiple configs were matched
    if plot and len(rms_results_for_plot) > 1:
        compare_path = os.path.join(save_dir, "rms_compare.png")
        plot_rms_compare(rms_results_for_plot, save_path=compare_path)

    n_pass = sum(1 for r in results.values() if r["passfail"]["pass"])
    n_total = len(results)

    if n_total == 0:
        summary = "No matching acquisitions found for the given filters."
    else:
        summary = (
            "Analysed {n_total} configuration(s) for FEMB {femb}. "
            "{n_pass}/{n_total} passed.".format(
                n_total=n_total, femb=femb_id, n_pass=n_pass
            )
        )
        for label, r in results.items():
            summary += "\n  [{label}] {pf}".format(
                label=label, pf=r["passfail"]["summary"]
            )

    return {
        "matched_configs": n_total,
        "results":         results,
        "summary":         summary,
    }
