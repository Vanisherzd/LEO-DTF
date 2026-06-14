#!/usr/bin/env python3
"""Tests for H3 noise calibration scaffold (software-only)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_h3_noise_calibration_scaffold_software_only():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    result = subprocess.run(
        [sys.executable, "scripts/research_h3_noise_calibration_scaffold.py"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    assert before == after

    out = root / "experiments/results/research_h3_noise_calibration_scaffold"
    data = json.loads((out / "h3_noise_calibration_scaffold.json").read_text())
    assert (out / "h3_noise_calibration_scaffold.md").exists()

    meta = data["metadata"]
    assert meta["phase"] == "H3"
    assert meta["hardware_validation_complete"] is False
    assert meta["localization_accuracy_proven"] is False

    # No measurement provided -> pending; proxy assumptions are not measured.
    assert data["calibration_status"] == "pending_measurement"
    assert len(data["proxy_assumptions"]) > 0
    for p in data["proxy_assumptions"]:
        assert p["measured"] is None
