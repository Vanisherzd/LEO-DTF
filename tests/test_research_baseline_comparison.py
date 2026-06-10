#!/usr/bin/env python3
"""Tests for C20 baseline comparison."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def test_baseline_comparison_quick_run():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "research_baseline_comparison.py"

    result = subprocess.run(
        [sys.executable, str(script), "--quick", "--seed", "42"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    out_dir = root / "experiments" / "results" / "research_baseline_comparison"
    json_path = out_dir / "baseline_comparison_summary.json"
    md_path = out_dir / "baseline_comparison_summary.md"
    csv_path = out_dir / "baseline_comparison_trials.csv"

    assert json_path.exists()
    assert md_path.exists()
    assert csv_path.exists()

    data = json.loads(json_path.read_text())
    assert data["completed_trials"] > 0
    assert "aggregate_metrics" in data
    assert "method_rank_summary" in data
    assert "mismatch_cases" in data
    assert data["claim_status"]["matched_filter_is_proxy_not_real_receiver"] is True
    assert data["claim_status"]["diagnostic_only_not_OTA"] is True
    assert data["claim_status"]["no_localization_accuracy_claim"] is True

    notes = " ".join(data["conservative_notes"]).lower()
    assert "not ota" in notes
    assert "not localization" in notes

    md = md_path.read_text().lower()
    assert "proxy baseline" in md
    assert "does not create ota" in md or "not ota" in md
    assert "localization accuracy" in md

    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    assert rows
    for field in ["dtoi", "naive_snr", "matched_filter_score", "energy_removed_by_nuisance"]:
        assert field in rows[0]

    assert data["recommended_next_action"]
