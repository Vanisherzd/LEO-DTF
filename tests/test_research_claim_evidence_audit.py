#!/usr/bin/env python3
"""Tests for C24 claim/evidence audit scanner."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def test_claim_evidence_audit_runs_and_reports_boundaries():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "research_claim_evidence_audit.py"

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    out_dir = root / "experiments" / "results" / "research_claim_evidence_audit"
    json_path = out_dir / "claim_evidence_audit.json"
    csv_path = out_dir / "claim_evidence_audit_unsafe_hits.csv"
    md_path = out_dir / "claim_evidence_audit.md"

    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text())
    assert data["metadata"]["phase"] == "C24"
    assert "claim_boundary" in data
    assert "scan_summary" in data
    assert "evidence_status" in data
    assert "unsafe_hits" in data
    assert "recommended_actions" in data

    allowed = " ".join(data["claim_boundary"]["allowed_framing"]).lower()
    forbidden = " ".join(data["claim_boundary"]["forbidden_framing"]).lower()
    assert "observability diagnostic" in allowed
    assert "simulation/proxy" in allowed
    assert "ota validation completed" in forbidden
    assert "localization accuracy proven" in forbidden
    assert "deployment-ready system" in forbidden

    assert data["scan_summary"]["files_scanned"] >= 0
    assert isinstance(data["scan_summary"]["unsafe_hit_count"], int)
    assert data["evidence_status"]["diagnostic_only"] is True

    md = md_path.read_text().lower()
    assert "allowed framing" in md
    assert "forbidden framing" in md
    assert "does not modify manuscript files" in md

    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    assert rows == [] or {"path", "line", "pattern_id", "matched_text", "severity"}.issubset(rows[0].keys())


def test_claim_evidence_audit_detects_unsafe_tmp_file():
    root = Path(__file__).resolve().parents[1]
    tmp = root / "tmp_claim_audit_fixture.md"
    tmp.write_text("This system has OTA validation completed and localization accuracy proven.\n")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/research_claim_evidence_audit.py",
                "--include",
                str(tmp),
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        out_dir = root / "experiments" / "results" / "research_claim_evidence_audit"
        data = json.loads((out_dir / "claim_evidence_audit.json").read_text())
        assert data["scan_summary"]["unsafe_hit_count"] >= 2
        pattern_ids = {hit["pattern_id"] for hit in data["unsafe_hits"]}
        assert "ota_validation_completed" in pattern_ids
        assert "localization_accuracy_proven" in pattern_ids
    finally:
        tmp.unlink(missing_ok=True)
