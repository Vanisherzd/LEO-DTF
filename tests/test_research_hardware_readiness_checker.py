#!/usr/bin/env python3
"""Tests for C26 hardware readiness checker."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_hardware_readiness_checker_runs_without_hardware_or_source_edits():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout

    result = subprocess.run(
        [sys.executable, "scripts/research_hardware_readiness_checker.py"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert before == after

    out = root / "experiments/results/research_hardware_readiness_checker"
    json_path = out / "hardware_readiness_report.json"
    md_path = out / "hardware_readiness_report.md"

    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text())
    assert data["metadata"]["phase"] == "C26"
    assert data["metadata"]["source_files_modified"] is False
    assert "Mac" in data["metadata"]["intended_hardware_execution_environment"]
    assert "required_docs" in data
    assert "metadata_status" in data
    assert "safety_status" in data
    assert "hardware_boundary_status" in data
    assert "claim_boundary_status" in data
    assert data["claim_boundary_status"]["hardware_validation_complete"] is False
    assert data["claim_boundary_status"]["hil_validation_complete"] is False
    assert data["claim_boundary_status"]["ota_validation_complete"] is False
    assert "completed HIL validation" in data["forbidden_claims_until_hardware_done"]

    for key in [
        "hil_plan",
        "lr1121_packet_source",
        "usrp_b210_capture_protocol",
        "rf_safety_checklist",
    ]:
        assert key in data["required_docs"]

    md = md_path.read_text().lower()
    assert "mac-based hardware bring-up" in md
    assert "does not access hardware" in md
    assert "does not claim hil/ota validation" in md
    assert "forbidden claims until hardware is done" in md
