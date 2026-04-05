"""
tests/test_analysis_lib.py — Unit tests for femb_analysis_lib.py.

Uses synthetic data so no WIB hardware or real data files are required.
"""
import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_mock_channels_data(n_channels=128, n_samples=500, seed=42):
    """
    Generate a mock channels_data dict:
      {ch: np.ndarray(n_samples,)}  for ch in range(n_channels)

    Pedestal increases with channel number; RMS is ~3 ADC counts.
    """
    rng = np.random.default_rng(seed)
    return {
        ch: rng.normal(loc=800 + ch * 2, scale=3.0, size=n_samples)
        for ch in range(n_channels)
    }


# ── resolve_channels tests ─────────────────────────────────────────────────────

def test_resolve_channels_all():
    """No arguments → all 128 channels."""
    from core.femb_analysis_lib import resolve_channels
    chs = resolve_channels()
    assert chs == list(range(128))


def test_resolve_channels_by_silkscreen():
    """chips=['U03'] → global channels 48-63."""
    from core.femb_analysis_lib import resolve_channels
    chs = resolve_channels(chips=["U03"])
    assert chs == list(range(48, 64))


def test_resolve_channels_by_chip_id():
    """chips=[3] → global channels 48-63."""
    from core.femb_analysis_lib import resolve_channels
    chs = resolve_channels(chips=[3])
    assert chs == list(range(48, 64))


def test_resolve_channels_by_chip_channels():
    """chip_channels={'U03': [11]} → [59]."""
    from core.femb_analysis_lib import resolve_channels
    chs = resolve_channels(chip_channels={"U03": [11]})
    assert chs == [59]


def test_resolve_channels_by_chip_channels_int_key():
    """chip_channels={3: [0, 1]} → [48, 49]."""
    from core.femb_analysis_lib import resolve_channels
    chs = resolve_channels(chip_channels={3: [0, 1]})
    assert chs == [48, 49]


def test_resolve_channels_global():
    """global_channels=[1, 5, 59] → [1, 5, 59]."""
    from core.femb_analysis_lib import resolve_channels
    chs = resolve_channels(global_channels=[59, 1, 5])
    assert chs == [1, 5, 59]   # sorted


def test_resolve_channels_priority_global_wins():
    """global_channels takes priority over chips."""
    from core.femb_analysis_lib import resolve_channels
    chs = resolve_channels(chips=["U03"], global_channels=[0, 1])
    assert chs == [0, 1]


def test_resolve_chip_silkscreen():
    from core.femb_analysis_lib import resolve_chip
    assert resolve_chip("U03") == 3
    assert resolve_chip("U07") == 0


def test_resolve_chip_int():
    from core.femb_analysis_lib import resolve_chip
    assert resolve_chip(3) == 3


def test_resolve_chip_invalid():
    from core.femb_analysis_lib import resolve_chip
    with pytest.raises(ValueError):
        resolve_chip("U99")


# ── compute_rms tests ──────────────────────────────────────────────────────────

def test_compute_rms_basic():
    """compute_rms on all 128 channels returns correct structure."""
    from core.femb_analysis_lib import compute_rms
    mock_data = {0: make_mock_channels_data()}
    result = compute_rms(mock_data, femb_id=0)

    assert result["femb_id"] == 0
    assert len(result["channels"]) == 128
    for key, val in result["channels"].items():
        assert "ped" in val
        assert "rms" in val
        assert "ped_max" in val
        assert "ped_min" in val
        assert val["rms"] > 0
        assert val["ped_max"] >= val["ped"]
        assert val["ped_min"] <= val["ped"]

    summary = result["summary"]
    assert "rms_mean" in summary
    assert "ped_mean" in summary


def test_compute_rms_filtered():
    """compute_rms with target_channels=[48, 49, 59] returns only 3 channels."""
    from core.femb_analysis_lib import compute_rms
    mock_data = {0: make_mock_channels_data()}
    result = compute_rms(mock_data, femb_id=0, target_channels=[48, 49, 59])

    assert len(result["channels"]) == 3
    assert "ch_048" in result["channels"]
    assert "ch_049" in result["channels"]
    assert "ch_059" in result["channels"]

    ch59 = result["channels"]["ch_059"]
    assert ch59["chip_id"] == 3
    assert ch59["silkscreen"] == "U03"
    assert ch59["chip_chn"] == 11   # 59 - 48 = 11


def test_compute_rms_ped_values():
    """Pedestal values match the mock data generation formula."""
    from core.femb_analysis_lib import compute_rms
    mock_data = {0: make_mock_channels_data(seed=0)}
    result = compute_rms(mock_data, femb_id=0, target_channels=[0, 64])

    ch0  = result["channels"]["ch_000"]
    ch64 = result["channels"]["ch_064"]

    # Mock: loc = 800 + ch * 2
    assert abs(ch0["ped"]  - 800) < 1.0   # within 1 ADC of expected
    assert abs(ch64["ped"] - 928) < 1.0   # 800 + 64*2 = 928


def test_compute_rms_accepts_plain_dict():
    """compute_rms also works when channels_data is plain {ch: arr} (not nested)."""
    from core.femb_analysis_lib import compute_rms
    plain_data = make_mock_channels_data()
    result = compute_rms(plain_data, femb_id=0, target_channels=[0])
    assert "ch_000" in result["channels"]


# ── check_passfail tests ───────────────────────────────────────────────────────

def test_check_passfail_all_pass():
    """All channels within threshold → pass=True, bad_channels=[]."""
    from core.femb_analysis_lib import compute_rms, check_passfail
    mock_data = {0: make_mock_channels_data()}
    rms_result = compute_rms(mock_data, femb_id=0)

    # With generous thresholds everything should pass
    pf = check_passfail(rms_result, ped_threshold=100000.0, rms_threshold=10.0)
    assert pf["pass"] is True
    assert pf["bad_channels"] == []
    assert pf["bad_chips"] == []


def test_check_passfail_detects_bad_channel():
    """A channel with very high pedestal should be flagged."""
    from core.femb_analysis_lib import compute_rms, check_passfail
    # Inject one bad channel with artificially high pedestal
    mock_data = make_mock_channels_data()
    mock_data[0] = np.full(500, 5000.0)   # pedestal >> threshold of 1500

    rms_result = compute_rms({0: mock_data}, femb_id=0, target_channels=[0])
    pf = check_passfail(rms_result, ped_threshold=1500.0, rms_threshold=0.6)

    assert pf["pass"] is False
    assert 0 in pf["bad_channels"]


def test_check_passfail_summary_string():
    """The summary field should be a non-empty string."""
    from core.femb_analysis_lib import compute_rms, check_passfail
    mock_data = {0: make_mock_channels_data()}
    rms_result = compute_rms(mock_data, femb_id=0)
    pf = check_passfail(rms_result)
    assert isinstance(pf["summary"], str)
    assert len(pf["summary"]) > 0


# ── generate_filename / parse_filename round-trip ─────────────────────────────

def test_manifest_filename_roundtrip():
    """generate_filename and parse_filename should be inverses."""
    from core.femb_manifest import generate_filename, parse_filename
    fname = generate_filename("SE", snc=1, sg0=0, sg1=0, st0=1, st1=1, dac=0)
    assert fname == "RMS_SE_200mVBL_14_0mVfC_2_0us_0x00.bin"

    parsed = parse_filename(fname)
    assert parsed["mode"]          == "SE"
    assert parsed["snc"]           == 1
    assert parsed["snc_label"]     == "200mV"
    assert parsed["sg0"]           == 0
    assert parsed["sg1"]           == 0
    assert parsed["gain_label"]    == "14mV/fC"
    assert parsed["st0"]           == 1
    assert parsed["st1"]           == 1
    assert parsed["peaking_label"] == "2us"


def test_manifest_filename_900mv():
    """900mV filename generation and parsing."""
    from core.femb_manifest import generate_filename, parse_filename
    fname = generate_filename("SE", snc=0, sg0=1, sg1=0, st0=0, st1=0, dac=0)
    assert "900mVBL" in fname
    assert "25_0mVfC" in fname
    assert "1_0us" in fname

    parsed = parse_filename(fname)
    assert parsed["snc"] == 0
    assert parsed["sg0"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
