#!/usr/bin/env python3
"""Tests for H4 controlled replay scaffold (software-only)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_h4_controlled_replay_scaffold_software_only():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    result = subprocess.run(
        [sys.executable, "scripts/research_h4_controlled_replay_scaffold.py"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    assert before == after

    out = root / "experiments/results/research_h4_controlled_replay_scaffold"
    data = json.loads((out / "h4_controlled_replay_scaffold.json").read_text())
    assert (out / "h4_controlled_replay_scaffold.md").exists()

    meta = data["metadata"]
    assert meta["phase"] == "H4"
    assert meta["hardware_validation_complete"] is False
    assert meta["hil_validation_complete"] is False
    assert meta["localization_accuracy_proven"] is False

    # No hardware runs -> pending.
    assert data["replay_status"] == "pending_hardware_runs"
    assert data["rf_safety"]["ota_allowed"] is False
    assert data["rf_safety"]["conducted_or_shielded_required"] is True
    assert data["comparison_contract"]["repeatability_required"] is True
