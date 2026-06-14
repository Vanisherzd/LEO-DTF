#!/usr/bin/env python3
"""Tests for H0.5 LR1121 read-only SPI bring-up report (no hardware)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Active radio TX/send API call tokens that must NOT appear in firmware.
FORBIDDEN_TX_TOKENS = ["startTransmit", "beginTransmit", "setTx(", "SetTx(", ".transmit(", "sendPacket"]


def test_lr1121_spi_bringup_report_runs_no_hardware():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    result = subprocess.run(
        [sys.executable, "scripts/research_lr1121_spi_bringup_report.py"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    assert before == after

    out = root / "experiments/results/research_lr1121_spi_bringup_report"
    data = json.loads((out / "lr1121_spi_bringup_report.json").read_text())
    assert (out / "lr1121_spi_bringup_report.md").exists()

    meta = data["metadata"]
    assert meta["phase"] == "H0.5"
    assert meta["mode"] == "documentation_only_no_flash_no_serial"

    assert data["board"] == "NUCLEO_L476RG"
    assert data["port"] == "/dev/cu.usbmodem1303"
    assert data["fqbn"] == "STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_L476RG"
    assert data["firmware_tx_default_disabled"] is True
    assert data["rf_transmission_enabled"] is False
    assert data["packet_transmission_executed"] is False
    assert data["hardware_validation_complete"] is False
    assert data["hil_validation_complete"] is False
    assert data["ota_validation_complete"] is False

    # Pin map must exist and contain the SPI + control pins.
    pm = data["pin_map"]
    for pin in ["LR1121_NSS", "LR1121_BUSY", "LR1121_RESET", "SPI_MOSI", "SPI_MISO", "SPI_SCK"]:
        assert pin in pm, f"missing pin: {pin}"

    # Firmware must be statically TX-safe.
    scan = data["firmware_safety_scan"]
    assert scan["firmware_present"] is True
    assert scan["all_expected_markers_present"] is True
    assert scan["no_forbidden_tx_tokens"] is True
    assert data["firmware_tx_safe_by_static_scan"] is True

    # next_gate must gate H1 on read-only SPI ok.
    assert "next_gate" in data


def test_firmware_source_has_no_active_tx_calls():
    root = Path(__file__).resolve().parents[1]
    fw = root / "firmware/lr1121_tx_disabled_init/lr1121_tx_disabled_init.ino"
    assert fw.exists()
    text = fw.read_text()
    for forbidden in FORBIDDEN_TX_TOKENS:
        assert forbidden not in text, f"firmware contains forbidden active TX call: {forbidden}"
    # tx serial command must remain blocked.
    assert "TX command blocked in this firmware build" in text
