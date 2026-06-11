#!/usr/bin/env python3
"""Tests for C24B-alt conservative claim patch proposal."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_claim_patch_proposal_runs_without_modifying_sources():
    root = Path(__file__).resolve().parents[1]

    subprocess.run(
        [sys.executable, "scripts/research_claim_evidence_audit.py", "--include", "README.md", "docs", "paper"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/research_claim_audit_triage.py"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )

    before_status = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout

    result = subprocess.run(
        [sys.executable, "scripts/research_claim_patch_proposal.py"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    after_status = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout

    assert before_status == after_status

    out = root / "experiments/results/research_claim_patch_proposal"
    json_path = out / "claim_patch_proposal.json"
    md_path = out / "claim_patch_proposal.md"

    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text())
    assert data["metadata"]["phase"] == "C24B-alt"
    assert data["metadata"]["source_files_modified"] is False
    assert data["proposal_summary"]["selected_proposals"] >= 1
    assert data["safe_claim_boundary"]["diagnostic_only"] is True
    assert data["safe_claim_boundary"]["no_OTA_validation"] is True
    assert data["safe_claim_boundary"]["no_HIL_validation"] is True
    assert data["safe_claim_boundary"]["no_localization_accuracy"] is True
    assert data["recommended_next_action"]

    proposal_text = json.dumps(data["patch_proposals"]).lower()
    assert "diagnostic" in proposal_text
    assert "proxy" in proposal_text or "planned" in proposal_text

    md = md_path.read_text().lower()
    assert "does not modify docs or paper files" in md
    assert "safe claim boundary" in md
    assert "suggested rewrite" in md
