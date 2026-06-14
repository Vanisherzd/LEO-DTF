#!/usr/bin/env python3
"""Tests for H0 board discovery (inspection-only, no hardware dependency)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_h0_board_discovery_inspection_only():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    result = subprocess.run(
        [sys.executable, "scripts/research_h0_board_discovery.py"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    assert before == after

    out = root / "experiments/results/research_h0_board_discovery"
    data = json.loads((out / "h0_board_discovery.json").read_text())
    assert (out / "h0_board_discovery.md").exists()

    meta = data["metadata"]
    assert meta["phase"] == "H0"
    assert meta["mode"] == "inspection_only_no_flash_no_serial"
    assert meta["hardware_validation_complete"] is False
    assert meta["localization_accuracy_proven"] is False

    sc = data["stop_conditions"]
    assert sc["serial_not_opened"] is True
    assert sc["no_flash_performed"] is True
    assert sc["no_rf_transmission"] is True
    assert "upload_gate" in data
