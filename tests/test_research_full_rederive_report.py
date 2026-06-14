#!/usr/bin/env python3
"""Tests for C27 full re-derivation readiness report."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FORBIDDEN_CLAIMS = [
    "ota validation completed",
    "hil validation completed",
    "real satellite capture validated",
    "localization accuracy proven",
    "meter-level localization",
    "deployment-ready system",
]


def run(root: Path, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, f"{' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_full_rederive_report_runs_without_modifying_sources():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout

    run(root, "scripts/research_full_rederive_report.py", "--generate-missing")

    after = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout

    # The script must not touch tracked paper/docs/README sources.
    assert before == after

    out = root / "experiments/results/research_full_rederive_report"
    json_path = out / "full_rederive_report.json"
    md_path = out / "full_rederive_report.md"

    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text())

    assert data["metadata"]["phase"] == "C27"
    assert data["metadata"]["source_files_modified"] is False

    # Required top-level sections.
    for key in [
        "problem_statement",
        "revised_core_contribution",
        "non_contributions",
        "method_stack",
        "evidence_map",
        "claim_boundary",
        "paper_section_risk_map",
        "hardware_gap_map",
        "Mac_hardware_execution_plan",
        "recommended_next_phases",
        "final_readiness_assessment",
    ]:
        assert key in data, f"missing section: {key}"

    # Mandatory claim-boundary flags.
    cb = data["claim_boundary"]
    assert cb["hardware_validation_complete"] is False
    assert cb["HIL_validation_complete"] is False
    assert cb["OTA_validation_complete"] is False
    assert cb["localization_accuracy_proven"] is False
    assert cb["software_diagnostic_chain_complete"] is True

    fr = data["final_readiness_assessment"]
    assert fr["hardware_validation_complete"] is False
    assert fr["HIL_validation_complete"] is False
    assert fr["OTA_validation_complete"] is False
    assert fr["localization_accuracy_proven"] is False
    assert fr["software_diagnostic_chain_complete"] is True

    # final_readiness_assessment must be non-empty/meaningful.
    assert isinstance(fr["summary"], str) and len(fr["summary"]) > 0
    assert len(fr["can_commit_now"]) > 0
    assert len(fr["must_wait_for_hardware"]) > 0

    # Mac hardware execution plan exists and has steps.
    plan = data["Mac_hardware_execution_plan"]
    assert len(plan["steps"]) > 0
    assert "Mac" in plan["environment"]
    plan_text = json.dumps(plan).lower()
    assert "lr1121" in plan_text
    assert "usrp b210" in plan_text
    assert "no unlicensed ota" in plan_text or "no unlicensed ota transmission" in plan_text

    # Forbidden claims must appear ONLY in not-supported / forbidden lists,
    # never in supportable claims.
    supportable_text = " ".join(
        data["revised_core_contribution"]["genuinely_novel"]
        + cb["supportable_claims"]
    ).lower()
    for forbidden in FORBIDDEN_CLAIMS:
        assert forbidden not in supportable_text, f"forbidden claim leaked into supportable: {forbidden}"

    not_supported_text = " ".join(data["evidence_map"]["not_supported"]).lower()
    assert "ota validation completed" in not_supported_text
    assert "localization accuracy proven" in not_supported_text

    forbidden_until_text = " ".join(cb["forbidden_until_hardware"]).lower()
    assert "hil validation completed" in forbidden_until_text

    md = md_path.read_text().lower()
    assert "full re-derivation readiness report" in md
    assert "mac hardware execution plan" in md
    assert "final readiness assessment" in md
    assert "does not claim hil/ota/localization validation" in md
