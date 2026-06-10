#!/usr/bin/env python3
"""Tests for C23 consolidated research evidence table."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def run(root: Path, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, f"Command failed: {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_consolidated_evidence_table_quick_sources():
    root = Path(__file__).resolve().parents[1]

    run(root, "scripts/research_orbit_parameter_sweep.py", "--quick", "--seed", "42")
    run(root, "scripts/research_baseline_comparison.py", "--quick", "--seed", "42")
    run(root, "scripts/research_oscillator_sensitivity.py", "--quick", "--seed", "42", "--max-trials", "12")
    run(root, "scripts/research_oscillator_strong_focus.py", "--quick", "--seed", "42", "--max-trials", "12")
    run(root, "scripts/research_geometry_placement_robustness.py", "--quick", "--seed", "42", "--max-trials", "16")
    run(root, "scripts/research_consolidated_evidence_table.py", "--require-all")

    out_dir = root / "experiments" / "results" / "research_consolidated_evidence_table"
    json_path = out_dir / "consolidated_evidence_table.json"
    md_path = out_dir / "consolidated_evidence_table.md"
    csv_path = out_dir / "consolidated_evidence_table.csv"

    assert json_path.exists()
    assert md_path.exists()
    assert csv_path.exists()

    data = json.loads(json_path.read_text())
    assert data["metadata"]["phase"] == "C23"
    assert len(data["evidence_records"]) == 5
    assert data["overall_assessment"]["available_sources"] == 5
    assert data["overall_assessment"]["total_sources"] == 5
    assert data["overall_assessment"]["all_sources_available"] is True
    assert data["overall_assessment"]["diagnostic_only"] is True
    assert data["overall_assessment"]["not_ota_not_hil_not_localization"] is True
    assert "safe_claims" in data
    assert "forbidden_claims" in data

    forbidden = " ".join(data["forbidden_claims"]).lower()
    assert "ota validation completed" in forbidden
    assert "localization accuracy proven" in forbidden
    assert "deployment-ready system" in forbidden

    md = md_path.read_text().lower()
    assert "diagnostic-only evidence table" in md
    assert "forbidden claims" in md
    assert "localization-accuracy evidence" in md

    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 5
    assert {"C19", "C20", "C21", "C21B", "C22"} == {row["phase"] for row in rows}
    for row in rows:
        assert row["status"] == "available"
        assert row["claim_scope"]
