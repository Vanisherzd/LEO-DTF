#!/usr/bin/env python3
"""Tests for H0 Mac board checklist."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_h0_board_checklist_runs_without_hardware_or_source_edits():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"],
        cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    result = subprocess.run(
        [sys.executable, "scripts/research_mac_h0_board_checklist.py"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"],
        cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    assert before == after

    out = root / "experiments/results/research_mac_h0_board_checklist"
    json_path = out / "mac_h0_board_checklist.json"
    md_path = out / "mac_h0_board_checklist.md"
    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text())

    meta = data["metadata"]
    assert meta["phase"] == "H0"
    assert meta["source_files_modified"] is False
    assert meta["hardware_validation_complete"] is False
    assert meta["hil_validation_complete"] is False
    assert meta["ota_validation_complete"] is False
    assert meta["localization_accuracy_proven"] is False

    board = data["board"]
    assert board["firmware_status"] == "not_confirmed"
    assert board["second_board_correct_firmware"] is False
    assert board["serial_port_required"] is True

    rs = data["roles_and_safety"]
    assert rs["lr1121_tx_only"] is True
    assert rs["lr1121_rx_claim_forbidden"] is True
    assert rs["rf_transmission_enabled"] is False
    assert rs["ota_allowed"] is False
    assert rs["conducted_or_shielded_required"] is True
    assert rs["manual_gate_required_before_flashing"] is True
    assert rs["manual_gate_required_before_tx"] is True

    ids = {c["id"] for c in data["checklist"]}
    for required in [
        "identify_board",
        "confirm_firmware_target",
        "confirm_flashing_toolchain",
        "confirm_serial_log",
        "confirm_lr1121_config",
        "confirm_no_antenna_setup",
        "confirm_tx_log_format",
        "confirm_no_tx_until_gate",
    ]:
        assert required in ids, f"missing checklist item: {required}"

    md = md_path.read_text().lower()
    assert "h0 mac board" in md
    assert "manual gates — before flashing" in md
    assert "manual gates — before rf transmission" in md
