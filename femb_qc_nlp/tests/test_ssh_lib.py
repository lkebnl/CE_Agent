"""
tests/test_ssh_lib.py — Mock-based unit tests for femb_ssh_lib.py.

No real WIB connection is made. subprocess.run is patched throughout.
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock, call

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.femb_constants import WIB_HOST, WIB_WORKDIR


def _make_completed(returncode=0, stdout="Done", stderr=""):
    """Helper: return a mock CompletedProcess."""
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


class TestSSHRun(unittest.TestCase):
    """Tests for _ssh_run helper."""

    @patch("subprocess.run")
    def test_ssh_run_basic_command(self, mock_run):
        """Verify _ssh_run constructs ["ssh", WIB_HOST, cmd]."""
        from core.femb_ssh_lib import _ssh_run
        mock_run.return_value = _make_completed(returncode=0, stdout="ok")

        result = _ssh_run("ls /tmp", timeout=10)

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        cmd_list = args[0]
        self.assertEqual(cmd_list[0], "ssh")
        self.assertEqual(cmd_list[1], WIB_HOST)
        self.assertEqual(cmd_list[2], "ls /tmp")
        self.assertEqual(result.returncode, 0)

    @patch("subprocess.run")
    def test_ssh_run_returns_none_on_timeout(self, mock_run):
        """_ssh_run returns None when subprocess.TimeoutExpired."""
        import subprocess
        from core.femb_ssh_lib import _ssh_run
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ssh", timeout=5)

        result = _ssh_run("sleep 100", timeout=5)
        self.assertIsNone(result)

    @patch("subprocess.run")
    def test_ssh_run_passes_user_input(self, mock_run):
        """_ssh_run forwards user_input as stdin."""
        from core.femb_ssh_lib import _ssh_run
        mock_run.return_value = _make_completed(returncode=0)

        _ssh_run("python3 interactive.py", user_input="Lke\nN\nN\nnote\n")

        _, kwargs = mock_run.call_args
        self.assertEqual(kwargs.get("input"), "Lke\nN\nN\nnote\n")


class TestScpHelpers(unittest.TestCase):
    """Tests for _scp_to_wib and _scp_from_wib."""

    @patch("subprocess.run")
    def test_scp_to_wib_correct_command(self, mock_run):
        """_scp_to_wib uses scp -r local root@...:remote."""
        from core.femb_ssh_lib import _scp_to_wib
        mock_run.return_value = _make_completed(returncode=0)

        result = _scp_to_wib("/local/file.bin", "/remote/file.bin")

        self.assertTrue(result)
        args, _ = mock_run.call_args
        cmd = args[0]
        self.assertEqual(cmd[0], "scp")
        self.assertIn("-r", cmd)
        self.assertEqual(cmd[-2], "/local/file.bin")
        self.assertIn(WIB_HOST, cmd[-1])
        self.assertIn("/remote/file.bin", cmd[-1])

    @patch("subprocess.run")
    def test_scp_from_wib_correct_command(self, mock_run):
        """_scp_from_wib uses scp -r root@...:remote local."""
        from core.femb_ssh_lib import _scp_from_wib
        mock_run.return_value = _make_completed(returncode=0)

        result = _scp_from_wib("/remote/data/", "/local/data/")

        self.assertTrue(result)
        args, _ = mock_run.call_args
        cmd = args[0]
        self.assertEqual(cmd[0], "scp")
        self.assertIn("-r", cmd)
        src = cmd[-2]
        self.assertIn(WIB_HOST, src)
        self.assertIn("/remote/data/", src)
        self.assertEqual(cmd[-1], "/local/data/")

    @patch("subprocess.run")
    def test_scp_to_wib_returns_false_on_failure(self, mock_run):
        """_scp_to_wib returns False on non-zero returncode."""
        from core.femb_ssh_lib import _scp_to_wib
        mock_run.return_value = _make_completed(returncode=1, stderr="Permission denied")

        result = _scp_to_wib("/local/file.bin", "/remote/file.bin")
        self.assertFalse(result)


class TestMakeSlotArgs(unittest.TestCase):
    """Tests for _make_slot_args."""

    def test_all_on(self):
        from core.femb_ssh_lib import _make_slot_args
        self.assertEqual(_make_slot_args([0, 1, 2, 3]), "on on on on")

    def test_all_off(self):
        from core.femb_ssh_lib import _make_slot_args
        self.assertEqual(_make_slot_args([]), "off off off off")

    def test_partial(self):
        from core.femb_ssh_lib import _make_slot_args
        self.assertEqual(_make_slot_args([0, 2]), "on off on off")

    def test_single_slot(self):
        from core.femb_ssh_lib import _make_slot_args
        self.assertEqual(_make_slot_args([1]), "off on off off")


class TestMakeFembInputStr(unittest.TestCase):
    """Tests for _make_femb_input_str."""

    def test_rt_environment(self):
        from core.femb_ssh_lib import _make_femb_input_str
        s = _make_femb_input_str(
            operator="Alice",
            env="RT",
            toy_tpc="N",
            comment="unit test",
            femb_ids={0: "FEMB-001"},
        )
        lines = s.strip().split("\n")
        self.assertEqual(lines[0], "Alice")
        self.assertEqual(lines[1], "N")   # RT → N for cold question
        self.assertEqual(lines[2], "N")   # toy_tpc
        self.assertEqual(lines[3], "unit test")
        self.assertEqual(lines[4], "FEMB-001")

    def test_ln_environment(self):
        from core.femb_ssh_lib import _make_femb_input_str
        s = _make_femb_input_str(
            operator="Bob",
            env="LN",
            toy_tpc="Y",
            comment="cold test",
            femb_ids={0: "FEMB-002", 1: "FEMB-003"},
        )
        lines = s.strip().split("\n")
        self.assertEqual(lines[1], "Y")   # LN → Y for cold question
        self.assertIn("FEMB-002", lines)
        self.assertIn("FEMB-003", lines)


class TestWibPing(unittest.TestCase):
    """Tests for wib_ping."""

    @patch("subprocess.run")
    def test_ping_success(self, mock_run):
        from core.femb_ssh_lib import wib_ping
        mock_run.return_value = _make_completed(returncode=0)
        self.assertTrue(wib_ping())
        args, _ = mock_run.call_args
        cmd = args[0]
        self.assertEqual(cmd[0], "ping")
        self.assertIn("192.168.121.123", cmd)

    @patch("subprocess.run")
    def test_ping_failure(self, mock_run):
        from core.femb_ssh_lib import wib_ping
        mock_run.return_value = _make_completed(returncode=1)
        self.assertFalse(wib_ping())


class TestFembPowerOn(unittest.TestCase):
    """Tests for femb_power_on."""

    @patch("subprocess.run")
    def test_power_on_rt_command_structure(self, mock_run):
        """femb_power_on RT calls top_femb_powering.py with correct slot args."""
        from core.femb_ssh_lib import femb_power_on
        stdout_text = "SLOT#0 Power Connection Normal\nSLOT#1 Power Connection Normal\n"
        mock_run.return_value = _make_completed(returncode=0, stdout=stdout_text)

        result = femb_power_on(slots=[0, 1], env="RT")

        args, _ = mock_run.call_args
        cmd_list = args[0]
        self.assertEqual(cmd_list[0], "ssh")
        ssh_cmd = cmd_list[2]
        self.assertIn("top_femb_powering.py", ssh_cmd)
        self.assertIn("on on off off", ssh_cmd)

    @patch("subprocess.run")
    def test_power_on_ln_uses_ln_script(self, mock_run):
        """femb_power_on LN calls top_femb_powering_LN.py."""
        from core.femb_ssh_lib import femb_power_on
        mock_run.return_value = _make_completed(
            returncode=0,
            stdout="SLOT#0 Power Connection Normal\n"
        )
        femb_power_on(slots=[0], env="LN")

        args, _ = mock_run.call_args
        ssh_cmd = args[0][2]
        self.assertIn("top_femb_powering_LN.py", ssh_cmd)

    @patch("subprocess.run")
    def test_power_on_returns_slot_status(self, mock_run):
        """femb_power_on correctly parses per-slot pass/fail from stdout."""
        from core.femb_ssh_lib import femb_power_on
        # Only slot 0 prints success; slot 1 does not
        mock_run.return_value = _make_completed(
            returncode=0,
            stdout="SLOT#0 Power Connection Normal\n"
        )
        result = femb_power_on(slots=[0, 1], env="RT")
        self.assertTrue(result["slot_status"][0])
        self.assertFalse(result["slot_status"][1])
        self.assertFalse(result["success"])   # not all slots passed


class TestWibStartup(unittest.TestCase):
    """Tests for wib_startup."""

    @patch("subprocess.run")
    def test_startup_success_on_done(self, mock_run):
        from core.femb_ssh_lib import wib_startup
        mock_run.return_value = _make_completed(returncode=0, stdout="...Done\n")
        self.assertTrue(wib_startup())

    @patch("subprocess.run")
    def test_startup_fails_without_done(self, mock_run):
        from core.femb_ssh_lib import wib_startup
        mock_run.return_value = _make_completed(returncode=0, stdout="Some error")
        self.assertFalse(wib_startup())


if __name__ == "__main__":
    unittest.main()
