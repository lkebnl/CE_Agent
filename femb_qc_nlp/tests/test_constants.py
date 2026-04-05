"""
tests/test_constants.py — Unit tests for femb_constants.py.
"""
import sys
import os

# Ensure the project root is on sys.path for direct pytest invocation
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_gain_encoding():
    from core.femb_constants import GAIN_MAP
    assert GAIN_MAP["14mV/fC"]  == (0, 0)
    assert GAIN_MAP["25mV/fC"]  == (1, 0)
    assert GAIN_MAP["7.8mV/fC"] == (0, 1)
    assert GAIN_MAP["4.7mV/fC"] == (1, 1)


def test_peaking_encoding():
    from core.femb_constants import PEAKING_MAP
    # Counter-intuitive encoding — verify strictly against datasheet
    assert PEAKING_MAP["1us"]   == (0, 0)   # NOT (1,0)
    assert PEAKING_MAP["1.0us"] == (0, 0)
    assert PEAKING_MAP["0.5us"] == (1, 0)
    assert PEAKING_MAP["2us"]   == (1, 1)
    assert PEAKING_MAP["3us"]   == (0, 1)


def test_baseline_encoding():
    from core.femb_constants import BASELINE_MAP
    assert BASELINE_MAP["200mV"] == 1
    assert BASELINE_MAP["900mV"] == 0


def test_chip_channel_mapping():
    from core.femb_constants import CHIP_CHANNEL_MAP, SILKSCREEN_TO_CHIP

    # Spot-check each chip
    assert CHIP_CHANNEL_MAP[0] == ("U07",   0,  15)
    assert CHIP_CHANNEL_MAP[1] == ("U17",  16,  31)
    assert CHIP_CHANNEL_MAP[2] == ("U11",  32,  47)
    assert CHIP_CHANNEL_MAP[3] == ("U03",  48,  63)
    assert CHIP_CHANNEL_MAP[4] == ("U19",  64,  79)
    assert CHIP_CHANNEL_MAP[5] == ("U23",  80,  95)
    assert CHIP_CHANNEL_MAP[6] == ("U25",  96, 111)
    assert CHIP_CHANNEL_MAP[7] == ("U21", 112, 127)

    # Silkscreen reverse lookup
    assert SILKSCREEN_TO_CHIP["U03"] == 3
    assert SILKSCREEN_TO_CHIP["U07"] == 0

    # Chip 3, local channel 11 → global channel 59
    chip_id, ch_start, ch_end = CHIP_CHANNEL_MAP[3]
    assert ch_start + 11 == 59


def test_gain_tags():
    from core.femb_constants import GAIN_TAG
    assert GAIN_TAG[(0, 0)] == "14_0mVfC"
    assert GAIN_TAG[(1, 0)] == "25_0mVfC"
    assert GAIN_TAG[(0, 1)] == "7_8mVfC"
    assert GAIN_TAG[(1, 1)] == "4_7mVfC"


def test_peaking_tags():
    from core.femb_constants import PEAKING_TAG
    assert PEAKING_TAG[(1, 0)] == "0_5us"
    assert PEAKING_TAG[(0, 0)] == "1_0us"
    assert PEAKING_TAG[(1, 1)] == "2_0us"
    assert PEAKING_TAG[(0, 1)] == "3_0us"


def test_baseline_tags():
    from core.femb_constants import BASELINE_TAG
    assert BASELINE_TAG[1] == "200mVBL"
    assert BASELINE_TAG[0] == "900mVBL"


def test_silkscreen_to_chip_complete():
    """Verify all 8 chips are reversible via silkscreen."""
    from core.femb_constants import CHIP_CHANNEL_MAP, SILKSCREEN_TO_CHIP
    for chip_id, (silk, _, _) in CHIP_CHANNEL_MAP.items():
        assert SILKSCREEN_TO_CHIP[silk] == chip_id


def test_channel_ranges_contiguous():
    """Verify channels cover exactly 0-127 with no gaps."""
    from core.femb_constants import CHIP_CHANNEL_MAP
    covered = set()
    for chip_id, (silk, ch_start, ch_end) in CHIP_CHANNEL_MAP.items():
        for ch in range(ch_start, ch_end + 1):
            assert ch not in covered, "Channel {} appears in multiple chips!".format(ch)
            covered.add(ch)
    assert covered == set(range(128)), "Channels 0-127 not fully covered"
