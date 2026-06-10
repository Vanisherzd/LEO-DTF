#!/usr/bin/env python3
"""Tests for C21B strong-observability oscillator inspection."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def test_oscillator_strong_focus_quick_run():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "research_oscillator_strong_focus.py"

    result = subprocess.run(
        [sys.executable, str(script), "--quick", "--seed", "42", "--max-trials", "12"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    out_dir = root / "experiments" / "results" / "research_oscillator_strong_focus"
    json_path = out_dir / "oscillator_strong_focus_summary.json"
    md_path = out_dir / "oscillator_strong_focus_summary.md"
    csv_path = out_dir / "oscillator_strong_focus_trials.csv"

    assert json_path.exists()
    assert md_path.exists()
    assert csv_path.exists()

    data = json.loads(json_path.read_text())
    assert data["completed_trials"] > 0
    assert "aggregate_metrics" in data
    assert "threshold_summary" in data
    assert "robustness_by_drift" in data
    assert "robustness_by_phase_noise" in data
    assert data["claim_status"]["oscillator_model_is_proxy_not_RF_validation"] is True
    assert data["claim_status"]["thresholds_are_proxy_not_hardware_specs"] is True
    assert data["claim_status"]["diagnostic_only_not_OTA"] is True
    assert data["claim_status"]["no_localization_accuracy_claim"] is True

    notes = " ".join(data["conservative_notes"]).lower()
    assert "not ota" in notes
    assert "not real oscillator rf validation" in notes
    assert "not localization" in notes

    md = md_path.read_text().lower()
    assert "proxy" in md
    assert "not real rf phase-noise validation" in md
    assert "localization accuracy" in md

    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert len(rows) == 12
    for field in [
        "base_dtoi",
        "stressed_dtoi",
        "cfo_drift_hz_per_s",
        "phase_noise_index",
        "stress_loss_fraction",
        "observability_class",
    ]:
        assert field in rows[0]

    assert data["recommended_next_action"]
