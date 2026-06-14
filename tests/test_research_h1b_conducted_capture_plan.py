#!/usr/bin/env python3
"""Tests for H1B controlled conducted capture plan (no hardware)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_h1b_plan_runs_no_hardware():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    result = subprocess.run(
        [sys.executable, "scripts/research_h1b_conducted_capture_plan.py"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    assert before == after

    out = root / "experiments/results/research_h1b_conducted_capture_plan"
    data = json.loads((out / "h1b_conducted_capture_plan.json").read_text())
    assert (out / "h1b_conducted_capture_plan.md").exists()

    assert data["metadata"]["phase"] == "H1B"
    assert data["lr1121_confirmed"] is True
    assert data["usrp_rx_ready"] is True
    assert data["tx_currently_disabled"] is True
    assert data["conducted_or_shielded_required"] is True
    assert data["antenna_ota_forbidden"] is True

    # All validation flags false.
    assert data["metadata"]["hardware_validation_complete"] is False
    assert data["metadata"]["hil_validation_complete"] is False
    assert data["metadata"]["ota_validation_complete"] is False
    assert data["metadata"]["localization_accuracy_proven"] is False

    assert len(data["required_setup"]) > 0
    assert len(data["go_no_go_checklist"]) > 0
    assert "center_frequency_hz" in data["first_capture_parameters"]
    assert len(data["success_criteria"]) > 0

    # Forbidden claims must be acknowledged in the still-forbidden list.
    forbidden = " ".join(data["claim_still_forbidden_after_h1c"]).lower()
    assert "hil validation" in forbidden
    assert "ota validation" in forbidden
    assert "localization accuracy proven" in forbidden
