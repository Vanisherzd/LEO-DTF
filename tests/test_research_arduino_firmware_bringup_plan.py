#!/usr/bin/env python3
"""Tests for H0 Arduino firmware bring-up plan (no hardware, no flash)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_arduino_firmware_bringup_plan_records_tx_safety():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    result = subprocess.run(
        [sys.executable, "scripts/research_arduino_firmware_bringup_plan.py"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    assert before == after

    out = root / "experiments/results/research_arduino_firmware_bringup_plan"
    data = json.loads((out / "arduino_firmware_bringup_plan.json").read_text())
    assert (out / "arduino_firmware_bringup_plan.md").exists()

    meta = data["metadata"]
    assert meta["phase"] == "H0"
    assert meta["mode"] == "documentation_only_no_flash_no_serial"

    assert data["target_port"] == "/dev/cu.usbmodem1303"
    assert data["fqbn_candidate"] == "STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_L476RG"
    assert data["firmware_path"] == "firmware/lr1121_tx_disabled_init/lr1121_tx_disabled_init.ino"
    assert data["firmware_tx_default_disabled"] is True
    assert data["auto_transmit_on_boot"] is False
    assert data["rf_transmission_enabled"] is False
    assert data["packet_transmission_executed"] is False
    assert data["hardware_validation_complete"] is False
    assert data["hil_validation_complete"] is False
    assert data["ota_validation_complete"] is False

    # Firmware must be present and statically TX-safe.
    scan = data["firmware_safety_scan"]
    assert scan["firmware_present"] is True
    assert scan["all_expected_markers_present"] is True
    assert scan["no_forbidden_tx_tokens"] is True
    assert data["firmware_tx_safe_by_static_scan"] is True


def test_firmware_source_has_no_transmit_calls():
    root = Path(__file__).resolve().parents[1]
    fw = root / "firmware/lr1121_tx_disabled_init/lr1121_tx_disabled_init.ino"
    assert fw.exists()
    text = fw.read_text()
    for forbidden in ["startTransmit", "setTx(", ".transmit(", "beginTransmit"]:
        assert forbidden not in text, f"firmware contains forbidden TX call: {forbidden}"
