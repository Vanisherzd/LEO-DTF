#!/usr/bin/env python3
"""Tests for C28 theory and experiment blueprint."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FORBIDDEN_CLAIMS = [
    "gps/gnss replacement",
    "completed hil validation",
    "real satellite ota validation",
    "real satellite capture validated",
    "localization accuracy proven",
    "meter-level localization",
    "sub-kilometer performance claim",
    "deployment-ready system",
    "hardware oscillator specification derived",
    "surveyed station placement validation",
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


def test_theory_experiment_blueprint_runs_without_modifying_sources():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout

    run(root, "scripts/research_theory_experiment_blueprint.py", "--generate-missing")

    after = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout

    # No tracked paper/docs/README/source files may change.
    assert before == after

    out = root / "experiments/results/research_theory_experiment_blueprint"
    json_path = out / "theory_experiment_blueprint.json"
    md_path = out / "theory_experiment_blueprint.md"

    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text())

    meta = data["metadata"]
    assert meta["phase"] == "C28"
    assert meta["source_files_modified"] is False
    assert meta["hardware_validation_complete"] is False
    assert meta["hil_validation_complete"] is False
    assert meta["ota_validation_complete"] is False
    assert meta["localization_accuracy_proven"] is False

    # Required top-level sections.
    for key in [
        "final_problem_statement",
        "revised_core_contributions",
        "non_contributions",
        "mathematical_model",
        "method_stack",
        "experiment_matrix",
        "hardware_validation_roadmap",
        "paper_outline",
        "claim_boundary_table",
        "figure_table_plan",
        "implementation_plan",
        "final_recommendation",
    ]:
        assert key in data, f"missing section: {key}"

    fps = data["final_problem_statement"]
    fps_text = " ".join(str(v) for v in fps.values()).lower()
    assert "gnss-free" in fps_text
    assert "coarse roi" in fps_text

    mm = data["mathematical_model"]
    mm_text = json.dumps(mm).lower()
    assert "dtoi" in mm_text
    assert "nuisance projection" in mm_text or "nuisance_projection" in mm_text

    # Exactly 4 contributions C1-C4.
    ids = [c["id"] for c in data["revised_core_contributions"]]
    assert ids == ["C1", "C2", "C3", "C4"]

    # E1-E6 present.
    e_ids = [e["id"] for e in data["experiment_matrix"]]
    assert e_ids == ["E1", "E2", "E3", "E4", "E5", "E6"]

    # H0-H5 present.
    h_ids = [h["id"] for h in data["hardware_validation_roadmap"]]
    assert h_ids == ["H0", "H1", "H2", "H3", "H4", "H5"]

    assert len(data["paper_outline"]) > 0

    # final_recommendation mandatory statements.
    rec = data["final_recommendation"]
    assert rec["do_not_rewrite_paper_until_blueprint_reviewed"] is True
    assert rec["do_not_claim_hardware_validation_before_mac_captures"] is True
    rec_text = " ".join(rec["statements"]).lower()
    assert "do not rewrite paper" in rec_text
    assert "do not claim hardware validation" in rec_text

    # Forbidden claims must appear ONLY in non_contributions / claim-boundary /
    # forbidden-claim fields, never as supportable claims.
    supportable_text = " ".join(
        [c["name"] + " " + c["summary"] for c in data["revised_core_contributions"]]
        + [str(r["safe_wording"]) for r in data["claim_boundary_table"]["rows"]]
        + [str(e["expected_claim"]) for e in data["experiment_matrix"]]
        + [str(h["claim_allowed_after_completion"]) for h in data["hardware_validation_roadmap"]]
    ).lower()
    for forbidden in FORBIDDEN_CLAIMS:
        assert forbidden not in supportable_text, f"forbidden claim leaked into supportable: {forbidden}"

    # Forbidden claims should be acknowledged somewhere (non_contributions / forbidden fields).
    acknowledged_text = " ".join(
        data["non_contributions"]
        + [str(e["forbidden_claim"]) for e in data["experiment_matrix"]]
        + [str(h["claim_still_forbidden"]) for h in data["hardware_validation_roadmap"]]
        + [str(r["claim"]) for r in data["claim_boundary_table"]["rows"]]
    ).lower()
    assert "gnss" in acknowledged_text or "gps" in acknowledged_text
    assert "ota" in acknowledged_text
    assert "meter-level localization" in acknowledged_text

    md = md_path.read_text().lower()
    assert "theory and experiment blueprint" in md
    assert "experiment matrix" in md
    assert "hardware validation roadmap" in md
    assert "does not claim hil/ota/localization validation" in md
