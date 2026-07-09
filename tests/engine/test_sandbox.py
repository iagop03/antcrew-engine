"""Tests for antcrew_engine.engine.sandbox."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from antcrew_engine.engine import sandbox


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------

class TestIsAvailable:
    def setup_method(self):
        sandbox._AVAILABLE = None  # reset cache

    def teardown_method(self):
        sandbox._AVAILABLE = None

    def test_returns_true_when_docker_exits_zero(self):
        with patch("subprocess.run") as mock_run, \
             patch("shutil.which", return_value="/usr/bin/docker"):
            mock_run.return_value = MagicMock(returncode=0)
            assert sandbox.is_available() is True

    def test_returns_false_when_docker_not_on_path(self):
        with patch("shutil.which", return_value=None):
            assert sandbox.is_available() is False

    def test_returns_false_when_docker_info_fails(self):
        with patch("subprocess.run") as mock_run, \
             patch("shutil.which", return_value="/usr/bin/docker"):
            mock_run.return_value = MagicMock(returncode=1)
            assert sandbox.is_available() is False

    def test_returns_false_when_docker_raises(self):
        with patch("subprocess.run", side_effect=FileNotFoundError), \
             patch("shutil.which", return_value="/usr/bin/docker"):
            assert sandbox.is_available() is False

    def test_caches_result(self):
        with patch("subprocess.run") as mock_run, \
             patch("shutil.which", return_value="/usr/bin/docker"):
            mock_run.return_value = MagicMock(returncode=0)
            sandbox.is_available()
            sandbox.is_available()
            assert mock_run.call_count == 1  # only called once


# ---------------------------------------------------------------------------
# run() — mode=none (always direct)
# ---------------------------------------------------------------------------

class TestRunModeNone:
    def test_skips_docker_when_mode_is_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "none")
        sandbox._AVAILABLE = None

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["echo"], returncode=0, stdout="hi", stderr=""
            )
            result = sandbox.run(["echo", "hi"], cwd=tmp_path)

        assert mock_run.call_count == 1
        # called with direct args, not wrapped in docker
        called_args = mock_run.call_args[0][0]
        assert "docker" not in called_args[0]
        assert result.returncode == 0

    def test_direct_run_passes_cwd_and_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "none")
        env = {"PYTHONPATH": str(tmp_path)}

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            sandbox.run(["python", "--version"], cwd=tmp_path, env=env)

        kwargs = mock_run.call_args[1]
        assert kwargs["cwd"] == str(tmp_path)
        assert kwargs["env"] == env


# ---------------------------------------------------------------------------
# run() — mode=auto, Docker available
# ---------------------------------------------------------------------------

class TestRunDockerAvailable:
    @pytest.fixture(autouse=True)
    def _linux_platform(self, monkeypatch):
        """Simulate Linux so Windows CI doesn't short-circuit to _direct()."""
        monkeypatch.setattr(sys, "platform", "linux")

    def setup_method(self):
        sandbox._AVAILABLE = True  # pre-set to skip the probe

    def teardown_method(self):
        sandbox._AVAILABLE = None

    def test_wraps_in_docker_run(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "auto")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="ok", stderr=""
            )
            sandbox.run(["pytest", "."], cwd=tmp_path)

        docker_cmd = mock_run.call_args[0][0]
        assert docker_cmd[0] == "docker"
        assert "run" in docker_cmd
        assert "--rm" in docker_cmd

    def test_network_none_flag_present(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "auto")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            sandbox.run(["pytest"], cwd=tmp_path)

        docker_cmd = mock_run.call_args[0][0]
        assert "--network=none" in docker_cmd

    def test_memory_flag_present(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "auto")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            sandbox.run(["pytest"], cwd=tmp_path, memory="512m")

        docker_cmd = mock_run.call_args[0][0]
        assert "--memory=512m" in docker_cmd

    def test_pids_limit_present(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "auto")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            sandbox.run(["pytest"], cwd=tmp_path)

        docker_cmd = mock_run.call_args[0][0]
        assert "--pids-limit=256" in docker_cmd

    def test_no_new_privileges_present(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "auto")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            sandbox.run(["pytest"], cwd=tmp_path)

        docker_cmd = mock_run.call_args[0][0]
        assert "--security-opt=no-new-privileges" in docker_cmd

    def test_cwd_mounted_at_same_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "auto")
        cwd_abs = tmp_path.resolve()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            sandbox.run(["pytest"], cwd=tmp_path)

        docker_cmd = mock_run.call_args[0][0]
        v_idx = docker_cmd.index("-v") + 1
        assert docker_cmd[v_idx] == f"{cwd_abs}:{cwd_abs}"

    def test_pythonpath_forwarded(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "auto")
        env = {"PYTHONPATH": str(tmp_path), "IRRELEVANT": "skip_me"}

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            sandbox.run(["pytest"], cwd=tmp_path, env=env)

        docker_cmd = mock_run.call_args[0][0]
        assert f"-e" in docker_cmd
        e_idx = docker_cmd.index("-e") + 1
        assert "PYTHONPATH" in docker_cmd[e_idx]
        assert "IRRELEVANT" not in " ".join(docker_cmd)

    def test_timeout_result_on_timeout_expired(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "auto")

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 30)):
            result = sandbox.run(["pytest"], cwd=tmp_path, timeout=30)

        assert result.returncode == 124
        assert "timeout" in result.stderr.lower()

    def test_extra_mounts_added_as_readonly(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "auto")
        extra = [("/host/venv", "/venv")]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            sandbox.run(["pytest"], cwd=tmp_path, extra_mounts=extra)

        docker_cmd = mock_run.call_args[0][0]
        assert "/host/venv:/venv:ro" in docker_cmd

    def test_image_uses_host_python_version(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "auto")
        vi = sys.version_info
        expected_image = f"python:{vi.major}.{vi.minor}-slim"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            sandbox.run(["pytest"], cwd=tmp_path)

        docker_cmd = mock_run.call_args[0][0]
        assert expected_image in docker_cmd


# ---------------------------------------------------------------------------
# run() — mode=auto, Docker unavailable → fallback
# ---------------------------------------------------------------------------

class TestRunDockerUnavailableFallback:
    def setup_method(self):
        sandbox._AVAILABLE = False

    def teardown_method(self):
        sandbox._AVAILABLE = None

    def test_falls_back_to_direct_subprocess(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "auto")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["pytest"], returncode=0, stdout="ok", stderr=""
            )
            result = sandbox.run(["pytest", "."], cwd=tmp_path)

        docker_cmd = mock_run.call_args[0][0]
        assert docker_cmd[0] != "docker"
        assert result.returncode == 0

    def test_required_mode_raises_when_docker_unavailable(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTCREW_SANDBOX", "required")

        with pytest.raises(RuntimeError, match="Docker is not available"):
            sandbox.run(["pytest"], cwd=tmp_path)
