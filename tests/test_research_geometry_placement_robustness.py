#!/usr/bin/env python3
"""Tests for C22 geometry / station placement robustness."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def test_geometry_placement_robustness_quick_run():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "research_geometry_placement_robustness.py"

    result = subprocess.run(
        [sys.executable, str(script), "--quick", "--seed", "42", "--max-trials", "16"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    out_dir = root / "experiments" / "results" / "research_geometry_placement_robustness"
    json_path = out_dir / "geometry_placement_summary.json"
    md_path = out_dir / "geometry_placement_summary.md"
    csv_path = out_dir / "geometry_placement_trials.csv"

    assert json_path.exists()
    assert md_path.exists()
    assert csv_path.exists()

    data = json.loads(json_path.read_text())
    assert data["completed_trials"] > 0
    assert "aggregate_metrics" in data
    assert "geometry_summary" in data
    assert "suspicious_flags" in data
    assert data["claim_status"]["geometry_model_is_proxy_not_surveyed_station_validation"] is True
    assert data["claim_status"]["diagnostic_only_not_OTA"] is True
    assert data["claim_status"]["no_localization_accuracy_claim"] is True

    notes = " ".join(data["conservative_notes"]).lower()
    assert "not ota" in notes
    assert "not surveyed station placement validation" in notes
    assert "not localization" in notes

    md = md_path.read_text().lower()
    assert "geometry proxy" in md
    assert "not surveyed station placement validation" in md
    assert "localization accuracy" in md

    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert len(rows) == 16
    for field in [
        "placement_direction",
        "geometry_class",
        "geometry_factor",
        "base_dtoi",
        "geometry_adjusted_dtoi",
        "geometry_loss_fraction",
        "observability_class",
    ]:
        assert field in rows[0]

    assert data["recommended_next_action"]
