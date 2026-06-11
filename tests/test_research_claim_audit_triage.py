#!/usr/bin/env python3
"""Tests for C24A claim audit triage."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_cmd(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )


def test_claim_audit_triage_real_audit_runs():
    root = Path(__file__).resolve().parents[1]

    audit = run_cmd(root, "scripts/research_claim_evidence_audit.py", "--include", "README.md", "docs", "paper")
    assert audit.returncode == 0, audit.stderr

    triage = run_cmd(root, "scripts/research_claim_audit_triage.py")
    assert triage.returncode == 0, triage.stderr

    out = root / "experiments/results/research_claim_audit_triage"
    data = json.loads((out / "claim_audit_triage.json").read_text())
    assert (out / "claim_audit_triage.csv").exists()
    assert (out / "claim_audit_triage.md").exists()
    assert data["total_hits"] >= 0
    assert "triage_counts" in data
    assert "triage_records" in data
    assert "recommended_doc_actions" in data
    assert "conservative_rewrite_rules" in data
    assert "safe_claim_boundary" in data
    assert data["safe_claim_boundary"]["diagnostic_only"] is True
    assert data["safe_claim_boundary"]["no_OTA_validation"] is True
    assert data["safe_claim_boundary"]["no_HIL_validation"] is True
    assert data["recommended_next_action"]

    rules = " ".join(data["conservative_rewrite_rules"].keys()).lower()
    values = " ".join(data["conservative_rewrite_rules"].values()).lower()
    assert "ota validation" in rules
    assert "hil validation" in rules
    assert "localization accuracy" in rules
    assert "meter-level localization" in rules
    assert "no ota validation claimed" in values
    assert "no localization accuracy claimed" in values


def test_claim_audit_triage_fixture_categories(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    docs = tmp_path / "docs"
    docs.mkdir()

    (docs / "forbidden.md").write_text(
        "# Forbidden claims\nDo not claim OTA validation completed.\n"
    )
    (docs / "planned.md").write_text(
        "# Plan\nPlanned HIL validation is pending and not yet completed.\n"
    )
    (docs / "overclaim.md").write_text(
        "# Result\nWe have completed OTA validation and localization accuracy proven.\n"
    )

    fixture = tmp_path / "fixture_audit.json"
    fixture.write_text(json.dumps({
        "unsafe_hits": [
            {
                "path": "docs/forbidden.md",
                "line": 2,
                "pattern_id": "ota_validation_completed",
                "matched_text": "OTA validation completed",
                "severity": "high",
            },
            {
                "path": "docs/planned.md",
                "line": 2,
                "pattern_id": "hil_validation_completed",
                "matched_text": "HIL validation",
                "severity": "high",
            },
            {
                "path": "docs/overclaim.md",
                "line": 2,
                "pattern_id": "localization_accuracy_proven",
                "matched_text": "localization accuracy proven",
                "severity": "high",
            },
        ]
    }))

    out = tmp_path / "out"
    result = run_cmd(
        root,
        "scripts/research_claim_audit_triage.py",
        "--input",
        str(fixture),
        "--output-dir",
        str(out),
        "--base-dir",
        str(tmp_path),
    )
    assert result.returncode == 0, result.stderr

    data = json.loads((out / "claim_audit_triage.json").read_text())
    categories = {r["triage_category"] for r in data["triage_records"]}
    assert "likely_false_positive_forbidden_list" in categories
    assert "planned_or_future_work_context" in categories
    assert "likely_true_overclaim" in categories
