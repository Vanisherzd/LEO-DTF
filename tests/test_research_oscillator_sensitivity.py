#!/usr/bin/env python3
"""Tests for C21 oscillator sensitivity sweep."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def test_oscillator_sensitivity_quick_run():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "research_oscillator_sensitivity.py"

    result = subprocess.run(
        [sys.executable, str(script), "--quick", "--seed", "42", "--max-trials", "12"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    out_dir = root / "experiments" / "results" / "research_oscillator_sensitivity"
    json_path = out_dir / "oscillator_sensitivity_summary.json"
    md_path = out_dir / "oscillator_sensitivity_summary.md"
    csv_path = out_dir / "oscillator_sensitivity_trials.csv"

    assert json_path.exists()
    assert md_path.exists()
    assert csv_path.exists()

    data = json.loads(json_path.read_text())
    assert data["completed_trials"] > 0
    assert "aggregate_metrics" in data
    assert "robustness_by_drift" in data
    assert "robustness_by_phase_noise" in data
    assert data["claim_status"]["oscillator_model_is_proxy_not_RF_validation"] is True
    assert data["claim_status"]["diagnostic_only_not_OTA"] is True
    assert data["claim_status"]["no_localization_accuracy_claim"] is True

    notes = " ".join(data["conservative_notes"]).lower()
    assert "not ota" in notes
    assert "not localization" in notes

    md = md_path.read_text().lower()
    assert "proxy" in md
    assert "not real rf phase-noise validation" in md
    assert "localization accuracy" in md

    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert len(rows) == 12
    assert {"100", "5000"}.issubset({row["offset_m"] for row in rows})
    assert {"300", "1800"}.issubset({row["duration_s"] for row in rows})
    for field in [
        "base_dtoi",
        "stressed_dtoi",
        "cfo_drift_hz_per_s",
        "phase_noise_index",
        "stress_loss_fraction",
    ]:
        assert field in rows[0]

    assert data["recommended_next_action"]
