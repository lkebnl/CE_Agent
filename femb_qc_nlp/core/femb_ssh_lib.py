# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : PC-side SSH/SCP wrappers — WIB init, power control, atom-script sequencing, data pull
"""
femb_ssh_lib.py — PC-side SSH/SCP wrappers for WIB control.

Layer 0: Initialization (ping, time sync, startup, config push)
Layer 1: Power control (femb_power_on, femb_power_off)
Layer 2B: Full-flow acquisition (run_full_rms, run_single_config,
          run_config_matrix, pull_qc_data, clean_wib_data, push_atoms_to_wib)

All SSH commands go through _ssh_run() and all SCP transfers through
_scp_to_wib() / _scp_from_wib().
"""

import subprocess
import datetime
import os
import filecmp
import json
import logging

from core.femb_constants import (
    WIB_HOST, WIB_WORKDIR, WIB_QC_DIR, WIB_ATOMS_DIR,
    GAIN_MAP, PEAKING_MAP, BASELINE_MAP,
    GAIN_TAG, PEAKING_TAG, BASELINE_TAG,
    PC_DATA_ROOT,
)
from core.femb_manifest import (
    create_manifest, add_acquisition, generate_filename,
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Directory where SSH command scripts are saved
SSH_CMD_DIR = "./ssh_commands"


# ── SSH command saving ──────────────────────────────────────────────────────────

def save_ssh_commands(steps, config, local_data_dir, output_fname,
                      init_steps=None, power_steps=None, config_csv=None,
                      power_off=False):
    """
    Save the complete SSH/SCP command sequence to a local shell script file.

    Records every stage in execution order so the file is a full,
    reproducible record of one acquisition run:

      Section 0 — WIB Initialisation  (init_steps, optional)
      Section 1 — FEMB Power-On       (power_steps, optional)
      Section 2 — Atom scripts        (steps, always present)
      Section 3 — Pull QC data        (SCP from WIB)
      Section 4 — Clean WIB data      (rm on WIB)

    Parameters
    ----------
    steps : list of (cmd_str, timeout_int)
        Atom-script SSH commands (wib_coldata_reset … wib_acquire).
    config : dict
        Config dict (snc_label, gain_label, peaking_label, etc.).
    local_data_dir : str
        Local data directory used for SCP pull.
    output_fname : str
        Expected output .bin filename on WIB.
    init_steps : list of (cmd_str, timeout_int) or None
        WIB-initialisation SSH commands (time-sync, startup).
        Pass None to omit this section.
    power_steps : list of (cmd_str, timeout_int) or None
        FEMB power-on SSH commands.
        Pass None to omit this section.
    config_csv : str or None
        Local config CSV that was SCP-pushed during init.
        If provided, a scp push line is appended to the init section.

    Returns
    -------
    str
        Path to the saved file.
    """
    os.makedirs(SSH_CMD_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = "ssh_cmd_{}.sh".format(ts)
    fpath = os.path.join(SSH_CMD_DIR, fname)

    lines = []
    lines.append("#!/bin/bash")
    lines.append("# FEMB QC SSH Command Sequence")
    lines.append("# Generated  : {}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    lines.append("# WIB host   : {}".format(WIB_HOST))
    lines.append("# Baseline   : {}".format(config.get("snc_label", "")))
    lines.append("# Gain       : {}".format(config.get("gain_label", "")))
    lines.append("# Peaking    : {}".format(config.get("peaking_label", "")))
    lines.append("# Output file: {}".format(output_fname))
    lines.append("# Local dir  : {}".format(local_data_dir))
    lines.append("# ──────────────────────────────────────────────────────────")

    # Section 0: WIB Initialisation
    if init_steps:
        lines.append("")
        lines.append("# ── Section 0: WIB initialization (time sync + startup) ────────")
        for cmd, timeout in init_steps:
            lines.append('ssh {} "{}"  # timeout={}s'.format(WIB_HOST, cmd, timeout))
        if config_csv and os.path.isfile(config_csv):
            basename = os.path.basename(config_csv)
            remote = "{}/{}".format(WIB_WORKDIR, basename)
            lines.append('scp -r {} {}:{}  # config push'.format(config_csv, WIB_HOST, remote))
            lines.append('scp -r {}:{} ./readback/{}  # config verify'.format(
                WIB_HOST, remote, basename))

    # Section 1: FEMB Power-On
    if power_steps:
        lines.append("")
        lines.append("# ── Section 1: FEMB power-on ────────────────────────────────────")
        for cmd, timeout in power_steps:
            lines.append('ssh {} "{}"  # timeout={}s'.format(WIB_HOST, cmd, timeout))

    # Section 2: Atom scripts
    lines.append("")
    lines.append("# ── Section 2: Atomic scripts (coldata_reset → autocali → fe_cfg → align → acquire) ──")
    for cmd, timeout in steps:
        lines.append('ssh {} "{}"  # timeout={}s'.format(WIB_HOST, cmd, timeout))

    # Section 3: Pull QC data
    lines.append("")
    lines.append("# ── Section 3: Pull data to local machine ───────────────────────")
    lines.append('scp -r {}:{} {}'.format(WIB_HOST, WIB_QC_DIR + "/", local_data_dir))

    # Section 4: Clean WIB
    lines.append("")
    lines.append("# ── Section 4: Clean up WIB temporary data ─────────────────────")
    lines.append('ssh {} "rm -rf {}"'.format(WIB_HOST, WIB_QC_DIR))

    # Section 5: Power-off
    if power_off:
        lines.append("")
        lines.append("# ── Section 5: FEMB power-off ───────────────────────────────────")
        lines.append('ssh {} "cd {d}; python3 top_femb_powering.py off off off off"  # timeout=60s'.format(
            WIB_HOST, d=WIB_WORKDIR))

    lines.append("")

    with open(fpath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    log.info("[SSH_CMD] Command sequence saved to: %s", fpath)
    return fpath


def replay_ssh_commands(cmd_file):
    """
    Replay a previously saved SSH command script.

    Reads the .sh file, extracts ssh/scp lines (skips comments/blank lines),
    and executes them in order via _ssh_run() / _scp_from_wib().

    Parameters
    ----------
    cmd_file : str
        Path to a saved ssh_cmd_*.sh file.

    Returns
    -------
    bool
        True if all steps succeeded.
    """
    if not os.path.isfile(cmd_file):
        log.error("[REPLAY] File not found: %s", cmd_file)
        return False

    log.info("[REPLAY] Replaying: %s", cmd_file)
    with open(cmd_file, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    success = True
    for raw in lines:
        line = raw.strip()
        # Skip comments, blank lines, shebang
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        # Strip inline comments
        line = line.split("#")[0].strip()
        if not line:
            continue

        if line.startswith("ssh "):
            # Extract the remote command inside quotes
            # Format: ssh HOST "COMMAND"
            m = __import__("re").match(r'^ssh\s+\S+\s+"(.+)"', line)
            if m:
                res = _ssh_run(m.group(1), timeout=120)
                if res is None or res.returncode != 0:
                    log.error("[REPLAY] Step failed: %s", line[:80])
                    success = False
                    break
        elif line.startswith("scp "):
            # Execute scp directly via subprocess
            res = subprocess.run(line.split(), capture_output=True, text=True, timeout=120)
            if res.returncode != 0:
                log.error("[REPLAY] SCP failed: %s", line[:80])
                success = False
                break

    return success


# ── Internal helpers ────────────────────────────────────────────────────────────

def _ssh_run(cmd, timeout=60, user_input=None, check=True):
    """
    Execute a command on the WIB via SSH.

    Parameters
    ----------
    cmd : str
        Shell command to execute on the WIB.
    timeout : int
        Command timeout in seconds.
    user_input : str or None
        String to feed to stdin (for interactive scripts).
    check : bool
        If True, log an error on non-zero return code but never raise.

    Returns
    -------
    subprocess.CompletedProcess or None
        None on exception.
    """
    command = ["ssh", WIB_HOST, cmd]
    log.info("[SSH] %s", cmd[:80])
    try:
        result = subprocess.run(
            command,
            input=user_input,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        log.info("[SSH] %s → returncode=%d", cmd[:60], result.returncode)
        if result.stdout:
            log.debug("[SSH stdout] %s", result.stdout[:200])
        if result.stderr:
            log.debug("[SSH stderr] %s", result.stderr[:200])
        if check and result.returncode != 0:
            log.error("[SSH] Non-zero return: %d\nstdout: %s\nstderr: %s",
                      result.returncode, result.stdout[:300], result.stderr[:300])
        return result
    except subprocess.TimeoutExpired:
        log.error("[SSH] Timeout after %ds: %s", timeout, cmd[:80])
        return None
    except Exception as exc:
        log.error("[SSH] Exception: %s", exc)
        return None


def _scp_to_wib(local, remote, timeout=30):
    """
    Copy a local file or directory to the WIB.

    Parameters
    ----------
    local : str
        Local path (file or directory).
    remote : str
        Remote path on WIB (no host prefix — it is added automatically).
    timeout : int
        Transfer timeout in seconds.

    Returns
    -------
    bool
        True on success.
    """
    dest = "{host}:{path}".format(host=WIB_HOST, path=remote)
    cmd = ["scp", "-r", local, dest]
    log.info("[SCP->WIB] %s → %s", local, remote)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            log.error("[SCP->WIB] Failed: %s", result.stderr[:200])
            return False
        return True
    except subprocess.TimeoutExpired:
        log.error("[SCP->WIB] Timeout after %ds", timeout)
        return False
    except Exception as exc:
        log.error("[SCP->WIB] Exception: %s", exc)
        return False


def _scp_from_wib(remote, local, timeout=60):
    """
    Copy a file or directory from the WIB to the local PC.

    Parameters
    ----------
    remote : str
        Remote path on WIB (no host prefix — it is added automatically).
    local : str
        Local destination path.
    timeout : int
        Transfer timeout in seconds.

    Returns
    -------
    bool
        True on success.
    """
    src = "{host}:{path}".format(host=WIB_HOST, path=remote)
    cmd = ["scp", "-r", src, local]
    log.info("[SCP<-WIB] %s → %s", remote, local)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            log.error("[SCP<-WIB] Failed: %s", result.stderr[:200])
            return False
        return True
    except subprocess.TimeoutExpired:
        log.error("[SCP<-WIB] Timeout after %ds", timeout)
        return False
    except Exception as exc:
        log.error("[SCP<-WIB] Exception: %s", exc)
        return False


def _make_slot_args(slots):
    """
    Convert a list of active slot numbers to 'on/off' argument string.

    Parameters
    ----------
    slots : list
        Subset of [0, 1, 2, 3], e.g. [0, 2].

    Returns
    -------
    str
        Space-separated on/off flags for slots 0..3,
        e.g. [0,2] → "on off on off".
    """
    return " ".join("on" if i in slots else "off" for i in range(4))


def _make_femb_input_str(operator, env, toy_tpc, comment, femb_ids):
    """
    Build the stdin string for QC_runs interactive prompts.

    The QC_runs.__init__() calls input() in this order:
      1. tester name
      2. cold/warm  (Y/N)
      3. ToyTPC     (Y/N)
      4. short note
      5. FEMB0 ID
      6. FEMB1 ID
      ... (for each slot in fembs)

    Parameters
    ----------
    operator : str
        Tester / operator name.
    env : str
        "LN" (cold) or "RT" (warm).
    toy_tpc : str
        "Y" or "N".
    comment : str
        Short note (< 200 chars).
    femb_ids : dict
        {slot_int: "FEMB-ID-string"}, e.g. {0: "FEMB-001"}.

    Returns
    -------
    str
        Newline-separated string to pipe as stdin.
    """
    lines = [
        operator,
        "Y" if env == "LN" else "N",
        toy_tpc,
        comment,
    ]
    for slot in sorted(femb_ids.keys()):
        lines.append(femb_ids[slot])
    return "\n".join(lines) + "\n"


def _make_data_dir():
    """Create and return a timestamped data directory under PC_DATA_ROOT."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    data_dir = os.path.join(PC_DATA_ROOT, ts)
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


# ── Layer 0: Initialization ────────────────────────────────────────────────────

def wib_ping(timeout=10):
    """
    Check whether the WIB is reachable.

    Returns
    -------
    bool
        True if the WIB responds to ping.
    """
    wib_ip = WIB_HOST.split("@")[-1]
    cmd = ["ping", "-c", "3", wib_ip]
    log.info("[PING] %s", wib_ip)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        reachable = result.returncode == 0
        log.info("[PING] %s → %s", wib_ip, "OK" if reachable else "UNREACHABLE")
        return reachable
    except Exception as exc:
        log.error("[PING] Exception: %s", exc)
        return False


def wib_time_sync():
    """
    Synchronise the WIB system clock to the current PC UTC time.

    Returns
    -------
    bool
        True on success.
    """
    utc_now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cmd = "date -s '{}'".format(utc_now)
    result = _ssh_run(cmd, timeout=15)
    return result is not None and result.returncode == 0


def wib_startup():
    """
    Execute the WIB initialisation script.

    Returns
    -------
    bool
        True when the WIB script outputs "Done".
    """
    cmd = "cd {workdir}; python3 wib_startup.py".format(workdir=WIB_WORKDIR)
    result = _ssh_run(cmd, timeout=60)
    if result is None:
        return False
    success = "Done" in result.stdout
    if not success:
        log.warning("[wib_startup] 'Done' not found in stdout: %s", result.stdout[:200])
    return success


def cfg_push(local_csv="./config/femb_info_implement.csv"):
    """
    Push a femb config CSV to the WIB and verify via readback comparison.

    Steps:
      1. SCP local_csv → WIB (remote filename matches local basename)
      2. SCP readback → ./readback/<basename>
      3. filecmp comparison

    Returns
    -------
    bool
        True when the pushed and read-back files are identical.
    """
    basename = os.path.basename(local_csv)
    remote_path = "{workdir}/{fname}".format(workdir=WIB_WORKDIR, fname=basename)
    if not _scp_to_wib(local_csv, remote_path):
        return False

    readback_dir = "./readback"
    os.makedirs(readback_dir, exist_ok=True)
    readback_path = os.path.join(readback_dir, basename)
    if not _scp_from_wib(remote_path, readback_path):
        return False

    match = filecmp.cmp(local_csv, readback_path, shallow=False)
    if not match:
        log.error("[cfg_push] Readback mismatch!")
    return match


def wib_init(config_csv=None):
    """
    Run the full WIB initialisation sequence (equivalent to QC_TST_EN==0 block).

    Steps:
      1. Time sync  — set WIB clock to current PC UTC time.
      2. WIB startup — run wib_startup.py on the WIB.
      3. Config push — SCP config CSV to WIB and verify readback.

    Must be called once per test session, **before** any acquisition
    (i.e. before wib_coldata_reset / wib_adc_autocali).

    Parameters
    ----------
    config_csv : str or None
        Local path to the femb config CSV.
        Defaults to ./config/femb_info_implement.csv.

    Returns
    -------
    bool
        True when all three steps succeed.
    """
    if config_csv is None:
        config_csv = "./config/femb_info_implement.csv"

    log.info("[wib_init] Step 1/3 — time sync")
    if not wib_time_sync():
        log.error("[wib_init] Time sync FAILED")
        return False

    log.info("[wib_init] Step 2/3 — WIB startup")
    if not wib_startup():
        log.error("[wib_init] WIB startup FAILED")
        return False

    log.info("[wib_init] Step 3/3 — config push & verify")
    if not os.path.isfile(config_csv):
        log.warning("[wib_init] Config CSV not found, skipping push: %s", config_csv)
    elif not cfg_push(config_csv):
        log.error("[wib_init] Config push/verify FAILED")
        return False

    log.info("[wib_init] Initialization complete")
    return True


# ── Layer 1: Power Control ─────────────────────────────────────────────────────

def femb_power_on(slots, env="RT"):
    """
    Power on the specified FEMB slots.

    Mirrors run_femb_powering() in cts_ssh_FEMB.py:
      - LN mode: run top_femb_powering_LN.py first, sleep 2s, then
                 run top_femb_powering.py (both are always executed in LN).
      - RT mode: run top_femb_powering.py only.

    Slot-connection status is parsed from the top_femb_powering.py stdout
    (``SLOT#N Power Connection Normal`` marker).

    Parameters
    ----------
    slots : list
        Subset of [0, 1, 2, 3].
    env : str
        "RT" (room temperature) or "LN" (liquid nitrogen).

    Returns
    -------
    dict
        {
          'success':     bool,
          'slot_status': {slot_int: bool, ...},
          'stdout':      str,   # from top_femb_powering.py
          'ln_stdout':   str,   # from top_femb_powering_LN.py (empty if RT)
        }
    """
    import time as _time
    slot_args = _make_slot_args(slots)
    ln_stdout = ""

    # LN pre-step: top_femb_powering_LN.py
    if env == "LN":
        log.info("[femb_power_on] LN mode — running top_femb_powering_LN.py")
        ln_cmd = "cd {d}; python3 top_femb_powering_LN.py {a}".format(
            d=WIB_WORKDIR, a=slot_args)
        ln_res = _ssh_run(ln_cmd, timeout=120)
        ln_stdout = ln_res.stdout if ln_res else ""
        _time.sleep(2)

    # Always run top_femb_powering.py for slot-connection check
    cmd = "cd {d}; python3 top_femb_powering.py {a}".format(
        d=WIB_WORKDIR, a=slot_args)
    result = _ssh_run(cmd, timeout=120)
    if result is None:
        return {"success": False, "slot_status": {s: False for s in slots},
                "stdout": "", "ln_stdout": ln_stdout}

    slot_status = {}
    for s in slots:
        marker = "SLOT#{} Power Connection Normal".format(s)
        slot_status[s] = marker in result.stdout

    overall = all(slot_status.values()) and result.returncode == 0
    return {
        "success":     overall,
        "slot_status": slot_status,
        "stdout":      result.stdout,
        "ln_stdout":   ln_stdout,
    }


def femb_power_off():
    """
    Power off all FEMBs.

    Returns
    -------
    bool
        True on success.
    """
    cmd = "cd {workdir}; python3 top_femb_powering.py off off off off".format(
        workdir=WIB_WORKDIR
    )
    result = _ssh_run(cmd, timeout=60)
    return result is not None and result.returncode == 0


# ── Layer 2B: Full-flow acquisition ────────────────────────────────────────────

def pull_qc_data(local_dir):
    """
    Pull QC data from WIB QC directory to local PC.

    Parameters
    ----------
    local_dir : str
        Local destination directory.

    Returns
    -------
    bool
        True on success.
    """
    os.makedirs(local_dir, exist_ok=True)
    return _scp_from_wib(WIB_QC_DIR + "/", local_dir, timeout=300)


def clean_wib_data():
    """
    Remove temporary data on WIB.

    Returns
    -------
    bool
        True on success.
    """
    cmd = "rm -rf {qc_dir}".format(qc_dir=WIB_QC_DIR)
    result = _ssh_run(cmd, timeout=15)
    return result is not None and result.returncode == 0


def push_atoms_to_wib():
    """
    SCP all atom scripts from scripts/wib_atoms/ to WIB atoms directory.

    Copies each .py file individually so files land directly in
    WIB_ATOMS_DIR/ rather than in a subdirectory.

    Returns
    -------
    bool
        True on success.
    """
    local_atoms_dir = "./scripts/wib_atoms"
    # Ensure remote directory exists
    _ssh_run("mkdir -p {dir}".format(dir=WIB_ATOMS_DIR), timeout=10)

    py_files = [
        f for f in os.listdir(local_atoms_dir) if f.endswith(".py")
    ]
    if not py_files:
        log.warning("[push_atoms] No .py files found in %s", local_atoms_dir)
        return False

    success = True
    for fname in py_files:
        local_path = os.path.join(local_atoms_dir, fname)
        remote_path = WIB_ATOMS_DIR + "/" + fname
        if not _scp_to_wib(local_path, remote_path, timeout=30):
            success = False
    return success


def run_full_rms(slots, operator, env="RT", local_data_dir=None):
    """
    Execute the complete item-5 RMS test (all 32 configurations).

    Equivalent to: python3 QC_top.py {slot_list} -t 5

    Parameters
    ----------
    slots : list
        FEMB slots to test.
    operator : str
        Operator / tester name.
    env : str
        "RT" or "LN".
    local_data_dir : str or None
        Where to store data locally. Auto-generated if None.

    Returns
    -------
    dict
        {'success': bool, 'data_dir': str, 'manifest_path': str, 'configs': list}
    """
    if local_data_dir is None:
        local_data_dir = _make_data_dir()
    os.makedirs(local_data_dir, exist_ok=True)

    # Build femb_ids dict with placeholder IDs
    femb_ids = {"femb{}".format(s): "FEMB-00{}".format(s) for s in slots}

    # Write config CSV, then run full WIB init (time sync + startup + config push)
    _write_femb_info_csv(slots=slots, operator=operator, env=env,
                         femb_ids=femb_ids, out_path="./config/femb_info_implement.csv")
    if not wib_init("./config/femb_info_implement.csv"):
        return {"success": False, "data_dir": local_data_dir,
                "manifest_path": "", "configs": []}

    # Build stdin for interactive QC_top.py / QC_runs
    slot_args = " ".join(str(s) for s in slots)
    env_yn = "Y" if env == "LN" else "N"
    femb_id_lines = "\n".join(
        "FEMB-00{}".format(s) for s in sorted(slots)
    )
    user_input = "{op}\n{env}\nN\nnote\n{ids}\n".format(
        op=operator, env=env_yn, ids=femb_id_lines
    )

    cmd = "cd {workdir}; python3 QC_top.py {slots} -t 5".format(
        workdir=WIB_WORKDIR, slots=slot_args
    )
    result = _ssh_run(cmd, timeout=1800, user_input=user_input)
    success = result is not None and result.returncode == 0

    # Pull data back
    pull_qc_data(local_data_dir)
    clean_wib_data()

    # Build minimal manifest
    manifest = create_manifest(
        data_dir=local_data_dir, fembs=slots, operator=operator, env=env
    )
    manifest_path = os.path.join(local_data_dir, "acquisition_manifest.json")

    return {
        "success":       success,
        "data_dir":      local_data_dir,
        "manifest_path": manifest_path,
        "configs":       [],  # populated by caller if needed
    }


def run_single_config(slots, snc, sg0, sg1, st0, st1, mode="SE",
                      num_samples=5, local_data_dir=None,
                      do_init=True, config_csv=None,
                      do_power=True, env="RT"):
    """
    Execute a single-configuration RMS acquisition using atom scripts.

    Full session sequence when do_init=True and do_power=True:
      0. WIB init  — time sync + wib_startup.py + config push
      1. Power-on  — top_femb_powering[_LN].py for given slots
      2. Atom steps — coldata_reset → adc_autocali → fe_configure
                      → data_align → acquire
      3. Pull data  — SCP QC dir to local
      4. Clean WIB  — rm QC dir
      5. Power-off  — top_femb_powering.py off off off off

    All steps are recorded in the saved SSH command script.

    Parameters
    ----------
    slots : list
        FEMB slots to use, e.g. [0, 3].
    snc : int
        Baseline code (0=900mV, 1=200mV).
    sg0, sg1 : int
        Gain bits.
    st0, st1 : int
        Peaking-time bits.
    mode : str
        Acquisition mode, e.g. "SE".
    num_samples : int
        Number of spy-buffer samples.
    local_data_dir : str or None
        Local data directory. Auto-generated if None.
    do_init : bool
        Run WIB init (time sync + startup + config push) before acquisition.
        Pass False when run_config_matrix() has already done this.
    config_csv : str or None
        Path to the femb config CSV, forwarded to wib_init().
    do_power : bool
        Execute femb_power_on() before acquisition and femb_power_off()
        after. Pass False when run_config_matrix() manages power externally.
    env : str
        "RT" or "LN" — controls which power script to call.

    Returns
    -------
    dict
        {'success': bool, 'data_dir': str, 'file': str, 'config': dict}
    """
    if local_data_dir is None:
        local_data_dir = _make_data_dir()
    os.makedirs(local_data_dir, exist_ok=True)

    slot_list = " ".join(str(s) for s in slots)
    output_fname = generate_filename(mode, snc, sg0, sg1, st0, st1)
    py = "cd {d}; PYTHONPATH={d}".format(d=WIB_WORKDIR)

    # ── Build all step lists ────────────────────────────────────────────────────

    _init_steps = None
    if do_init:
        utc_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        _init_steps = [
            ("date -s '{}'".format(utc_str), 15),
            ("cd {d}; python3 wib_startup.py".format(d=WIB_WORKDIR), 60),
        ]

    _power_steps = None
    if do_power:
        pwr_args = _make_slot_args(slots)
        _power_steps = []
        if env == "LN":
            _power_steps.append((
                "cd {d}; python3 top_femb_powering_LN.py {a}".format(
                    d=WIB_WORKDIR, a=pwr_args),
                120
            ))
        _power_steps.append((
            "cd {d}; python3 top_femb_powering.py {a}".format(
                d=WIB_WORKDIR, a=pwr_args),
            120
        ))

    steps = [
        (
            "{py} python3 {a}/wib_coldata_reset.py {s}".format(
                py=py, a=WIB_ATOMS_DIR, s=slot_list),
            30
        ),
        (
            "{py} python3 {a}/wib_adc_autocali.py {s}".format(
                py=py, a=WIB_ATOMS_DIR, s=slot_list),
            120
        ),
        (
            "{py} python3 {a}/wib_fe_configure.py {s} "
            "--snc {snc} --sg0 {sg0} --sg1 {sg1} "
            "--st0 {st0} --st1 {st1}".format(
                py=py, a=WIB_ATOMS_DIR, s=slot_list,
                snc=snc, sg0=sg0, sg1=sg1, st0=st0, st1=st1),
            60
        ),
        (
            "{py} python3 {a}/wib_data_align.py {s}".format(
                py=py, a=WIB_ATOMS_DIR, s=slot_list),
            30
        ),
        (
            "{py} python3 {a}/wib_acquire.py {s} "
            "--samples {n} --output {out}".format(
                py=py, a=WIB_ATOMS_DIR, s=slot_list,
                n=num_samples, out=output_fname),
            120
        ),
    ]

    config = {
        "mode":          mode,
        "snc":           snc,
        "snc_label":     BASELINE_TAG[snc].replace("mVBL", "mV"),
        "sg0":           sg0,
        "sg1":           sg1,
        "gain_label":    _gain_label(sg0, sg1),
        "st0":           st0,
        "st1":           st1,
        "peaking_label": _peaking_label(st0, st1),
        "dac":           "0x00",
    }

    # ── Save complete command sequence FIRST, before any execution ─────────────
    cmd_file = save_ssh_commands(
        steps, config, local_data_dir, output_fname,
        init_steps=_init_steps,
        power_steps=_power_steps,
        config_csv=config_csv,
        power_off=do_power,
    )
    log.info("[run_single_config] SSH command file saved: %s", cmd_file)

    # ── Step 0: WIB initialisation ─────────────────────────────────────────────
    if do_init:
        if not wib_init(config_csv):
            return {"success": False, "data_dir": local_data_dir,
                    "file": "", "config": {}}

    # ── Step 1: FEMB power-on ──────────────────────────────────────────────────
    if do_power:
        pwr = femb_power_on(slots, env=env)
        if not pwr["success"]:
            log.error("[run_single_config] Power-on failed: %s", pwr["slot_status"])
            return {"success": False, "data_dir": local_data_dir,
                    "file": "", "config": {}}

    # Push atom scripts to WIB
    push_atoms_to_wib()

    # ── Step 2: Atom scripts ───────────────────────────────────────────────────
    overall_success = True
    for step_cmd, step_timeout in steps:
        res = _ssh_run(step_cmd, timeout=step_timeout)
        if res is None or res.returncode != 0:
            log.error("[run_single_config] Step failed: %s", step_cmd[:80])
            overall_success = False
            break

    # ── Step 3+4: Pull data and clean WIB ─────────────────────────────────────
    pull_qc_data(local_data_dir)
    clean_wib_data()

    # ── Step 5: FEMB power-off ─────────────────────────────────────────────────
    if do_power:
        femb_power_off()

    manifest = create_manifest(
        data_dir=local_data_dir, fembs=slots, operator="", env=""
    )
    add_acquisition(manifest, output_fname, config, num_samples)

    return {
        "success":  overall_success,
        "data_dir": local_data_dir,
        "file":     output_fname,
        "config":   config,
    }


def run_config_matrix(slots, snc_list, gain_list, peaking_list,
                      num_samples=5, local_data_dir=None, config_csv=None,
                      env="RT"):
    """
    Execute a matrix of configurations by calling run_single_config() for each.

    Session order:
      1. wib_init()       — once
      2. femb_power_on()  — once
      3. run_single_config() × N  — do_init=False, do_power=False each time
      4. femb_power_off() — once

    Parameters
    ----------
    slots : list
        FEMB slots to use.
    snc_list : list of str
        Baseline labels, e.g. ["200mV", "900mV"].
    gain_list : list of str
        Gain labels, e.g. ["14mV/fC", "25mV/fC"].
    peaking_list : list of str
        Peaking-time labels, e.g. ["2us"].
    num_samples : int
        Spy-buffer samples per configuration.
    local_data_dir : str or None
        Local data directory. Auto-generated if None.
    config_csv : str or None
        Path to the femb config CSV, forwarded to wib_init().
    env : str
        "RT" or "LN".

    Returns
    -------
    dict
        {'success': bool, 'data_dir': str, 'configs_run': list, 'manifest_path': str}
    """
    if local_data_dir is None:
        local_data_dir = _make_data_dir()
    os.makedirs(local_data_dir, exist_ok=True)

    # Step 0: WIB initialisation — once for the whole matrix
    log.info("[run_config_matrix] Step 0 — WIB initialisation")
    if not wib_init(config_csv):
        return {"success": False, "data_dir": local_data_dir,
                "configs_run": [], "manifest_path": ""}

    # Step 1: FEMB power-on — once for the whole matrix
    log.info("[run_config_matrix] Step 1 — FEMB power-on slots=%s env=%s", slots, env)
    pwr = femb_power_on(slots, env=env)
    if not pwr["success"]:
        log.error("[run_config_matrix] Power-on failed: %s", pwr["slot_status"])
        return {"success": False, "data_dir": local_data_dir,
                "configs_run": [], "manifest_path": ""}

    configs_run = []
    any_fail = False

    for snc_label in snc_list:
        snc = BASELINE_MAP[snc_label]
        for gain_label in gain_list:
            sg0, sg1 = GAIN_MAP[gain_label]
            for peaking_label in peaking_list:
                st0, st1 = PEAKING_MAP[peaking_label]
                log.info("[run_config_matrix] snc=%s gain=%s peaking=%s",
                         snc_label, gain_label, peaking_label)
                res = run_single_config(
                    slots=slots,
                    snc=snc, sg0=sg0, sg1=sg1, st0=st0, st1=st1,
                    num_samples=num_samples,
                    local_data_dir=local_data_dir,
                    do_init=False,
                    do_power=False,
                    env=env,
                )
                configs_run.append({
                    "snc_label":     snc_label,
                    "gain_label":    gain_label,
                    "peaking_label": peaking_label,
                    "success":       res["success"],
                    "file":          res.get("file", ""),
                })
                if not res["success"]:
                    any_fail = True

    # Step 2: FEMB power-off — once after all configs
    log.info("[run_config_matrix] Step 2 — FEMB power-off")
    femb_power_off()

    manifest_path = os.path.join(local_data_dir, "acquisition_manifest.json")
    return {
        "success":      not any_fail,
        "data_dir":     local_data_dir,
        "configs_run":  configs_run,
        "manifest_path": manifest_path,
    }


# ── Private helpers ────────────────────────────────────────────────────────────

def _gain_label(sg0, sg1):
    """Return the canonical gain label string for given (sg0, sg1) bits."""
    canonical = {
        (0, 0): "14mV/fC",
        (1, 0): "25mV/fC",
        (0, 1): "7.8mV/fC",
        (1, 1): "4.7mV/fC",
    }
    return canonical.get((sg0, sg1), "??mV/fC")


def _peaking_label(st0, st1):
    """Return the canonical peaking-time label string for given (st0, st1) bits."""
    canonical = {
        (1, 0): "0.5us",
        (0, 0): "1us",
        (1, 1): "2us",
        (0, 1): "3us",
    }
    return canonical.get((st0, st1), "??us")


def _write_femb_info_csv(slots, operator, env, femb_ids, out_path):
    """Write a minimal femb_info.csv file for the given session."""
    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)
    with open(out_path, "w") as fh:
        fh.write("operator,slot,env,femb_id,note\n")
        for s in slots:
            key = "femb{}".format(s)
            fid = femb_ids.get(key, "FEMB-00{}".format(s))
            fh.write("{op},{slot},{env},{fid},auto\n".format(
                op=operator, slot=s, env=env, fid=fid
            ))
