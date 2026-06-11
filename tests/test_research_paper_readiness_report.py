#!/usr/bin/env python3
"""Tests for C25 paper readiness report."""

from __future__ import annotations

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
    assert result.returncode == 0, f"{' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_paper_readiness_report_runs_without_modifying_sources():
    root = Path(__file__).resolve().parents[1]

    run(root, "scripts/research_consolidated_evidence_table.py", "--generate-missing", "--require-all")
    run(root, "scripts/research_claim_evidence_audit.py", "--include", "README.md", "docs", "paper")
    run(root, "scripts/research_claim_audit_triage.py")
    run(root, "scripts/research_claim_patch_proposal.py")

    before = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout

    run(root, "scripts/research_paper_readiness_report.py")

    after = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout

    assert before == after

    out = root / "experiments/results/research_paper_readiness_report"
    json_path = out / "paper_readiness_report.json"
    md_path = out / "paper_readiness_report.md"

    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text())
    assert data["metadata"]["phase"] == "C25"
    assert data["metadata"]["source_files_modified"] is False
    assert "readiness_assessment" in data
    assert "software_evidence_status" in data
    assert "now_supportable_claims" in data
    assert "not_yet_supportable_claims" in data
    assert "hardware_next_steps" in data
    assert "long_roadmap" in data

    assess = data["readiness_assessment"]
    assert assess["software_diagnostic_chain_complete"] is True
    assert assess["hardware_validation_complete"] is False
    assert assess["ota_validation_complete"] is False
    assert assess["paper_ready_without_human_review"] is False

    supportable = " ".join(data["now_supportable_claims"]).lower()
    not_yet = " ".join(data["not_yet_supportable_claims"]).lower()
    hardware = " ".join(data["hardware_next_steps"]).lower()

    assert "observability diagnostic" in supportable
    assert "proxy" in supportable
    assert "real satellite ota validation" in not_yet
    assert "localization accuracy proven" in not_yet
    assert "lr1121" in hardware
    assert "usrp b210" in hardware

    md = md_path.read_text().lower()
    assert "paper readiness report" in md
    assert "claims supportable now" in md
    assert "claims not yet supportable" in md
    assert "hardware next steps" in md
