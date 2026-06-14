#!/usr/bin/env python3
"""Tests for H1 USRP B210 Rx-only readiness (dry-run, no hardware)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_usrp_receive_readiness_dry_run_no_hardware_or_source_edits():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"],
        cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    result = subprocess.run(
        [sys.executable, "scripts/research_usrp_receive_readiness.py"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"],
        cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    assert before == after

    out = root / "experiments/results/research_usrp_receive_readiness"
    json_path = out / "usrp_receive_readiness.json"
    md_path = out / "usrp_receive_readiness.md"
    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text())
    assert data["metadata"]["phase"] == "H1"
    assert data["metadata"]["mode"] == "dry_run_command_availability_only"
    assert data["usrp_role"] == "rx_only"
    assert data["transmit_forbidden"] is True
    assert data["ota_allowed"] is False
    # Default run must never execute a hardware probe.
    assert data["probe_executed"] is False
    assert "uhd_command_availability" in data
    for cmd in ["uhd_find_devices", "uhd_usrp_probe"]:
        assert cmd in data["uhd_command_availability"]
