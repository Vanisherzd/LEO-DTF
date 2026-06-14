#!/usr/bin/env python3
"""Tests for H2 IQ extraction scaffold (software-only)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_h2_iq_extraction_scaffold_software_only():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    result = subprocess.run(
        [sys.executable, "scripts/research_h2_iq_extraction_scaffold.py"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    assert before == after

    out = root / "experiments/results/research_h2_iq_extraction_scaffold"
    data = json.loads((out / "h2_iq_extraction_scaffold.json").read_text())
    assert (out / "h2_iq_extraction_scaffold.md").exists()

    meta = data["metadata"]
    assert meta["phase"] == "H2"
    assert meta["mode"] == "software_only_scaffold"
    assert meta["hardware_validation_complete"] is False
    assert meta["localization_accuracy_proven"] is False

    # With no run dir, extraction must be pending (no capture exists).
    assert data["extraction_status"] in {"pending_capture", "no_run_dir_provided"}
    assert "pipeline_stages" in data and len(data["pipeline_stages"]) > 0
    assert data["output_contract"]["header"].startswith("packet_index,")
