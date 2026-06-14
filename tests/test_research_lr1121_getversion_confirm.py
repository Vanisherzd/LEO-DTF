#!/usr/bin/env python3
"""Tests for H0.5C LR1121 GetVersion confirmation report (no hardware)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FORBIDDEN_TX_TOKENS = ["startTransmit", "beginTransmit", "setTx(", "SetTx(", ".transmit(", "sendPacket", "startTx"]


def test_getversion_confirm_runs_no_hardware():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    result = subprocess.run(
        [sys.executable, "scripts/research_lr1121_getversion_confirm.py"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    assert before == after

    out = root / "experiments/results/research_lr1121_getversion_confirm"
    data = json.loads((out / "lr1121_getversion_confirm.json").read_text())
    assert (out / "lr1121_getversion_confirm.md").exists()

    meta = data["metadata"]
    assert meta["phase"] == "H0.5C"
    assert meta["mode"] == "documentation_only_no_flash_no_serial"

    # Locked pin map.
    assert data["pin_map_locked"] is True
    assert data["nss"] == "D7"
    assert data["busy"] == "D3"
    assert data["reset"] == "D9"
    assert data["dio"] == "D5"
    assert data["spi_mode"] == 0

    # All claim flags false.
    assert data["rf_transmission_enabled"] is False
    assert data["packet_transmission_executed"] is False
    assert data["hardware_validation_complete"] is False
    assert data["hil_validation_complete"] is False
    assert data["ota_validation_complete"] is False
    assert data["localization_accuracy_proven"] is False

    # Offline (no boot log) -> not verified.
    assert data["lr1121_init_verified"] is False

    # Firmware statically TX-safe with locked pins.
    scan = data["firmware_safety_scan"]
    assert scan["firmware_present"] is True
    assert scan["all_expected_markers_present"] is True
    assert scan["no_forbidden_tx_tokens"] is True
    assert scan["pin_map_locked"] is True
    assert data["firmware_tx_safe_by_static_scan"] is True


def test_getversion_confirm_parses_verified_log(tmp_path):
    root = Path(__file__).resolve().parents[1]
    log = tmp_path / "boot_log.txt"
    log.write_text(
        "SPI_PROBE_PLAUSIBLE=true\n"
        "LR1121_GETVERSION_RAW=07 22 03 01 03\n"
        "LR1121_GETVERSION_DECODED=stat1=0x7,hw=0x22,device=0x3,fw=1.3\n"
        "parser_confidence=vendor_confirmed\n"
        "LR1121_INIT_VERIFIED=true\n"
    )
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "scripts/research_lr1121_getversion_confirm.py",
         "--boot-log", str(log), "--output-dir", str(out)],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads((out / "lr1121_getversion_confirm.json").read_text())

    assert data["raw_response"] == "07 22 03 01 03"
    assert data["parser_confidence"] == "vendor_confirmed"
    assert data["spi_probe_plausible"] is True
    assert data["decoded_response"]["device"] == "0x3"
    # Verified: vendor_confirmed + device 0x03.
    assert data["lr1121_init_verified"] is True
    assert data["next_gate"].startswith("lr1121_confirmed")
    # Even when chip confirmed, hardware validation stays false.
    assert data["hardware_validation_complete"] is False
    assert data["hil_validation_complete"] is False


def test_getversion_confirm_rejects_non_vendor_confidence(tmp_path):
    root = Path(__file__).resolve().parents[1]
    log = tmp_path / "boot_log.txt"
    # device ok but confidence not vendor_confirmed -> must NOT verify.
    log.write_text(
        "LR1121_GETVERSION_RAW=07 22 03 01 03\n"
        "LR1121_GETVERSION_DECODED=stat1=0x7,hw=0x22,device=0x3,fw=1.3\n"
        "parser_confidence=locally_inferred\n"
        "LR1121_INIT_VERIFIED=true\n"
    )
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "scripts/research_lr1121_getversion_confirm.py",
         "--boot-log", str(log), "--output-dir", str(out)],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads((out / "lr1121_getversion_confirm.json").read_text())
    assert data["lr1121_init_verified"] is False


def test_firmware_source_no_active_tx_and_locked_pins():
    root = Path(__file__).resolve().parents[1]
    fw = root / "firmware/lr1121_tx_disabled_init/lr1121_tx_disabled_init.ino"
    assert fw.exists()
    text = fw.read_text()
    for forbidden in FORBIDDEN_TX_TOKENS:
        assert forbidden not in text, f"firmware contains forbidden active TX call: {forbidden}"
    assert "TX command blocked in this firmware build" in text
    assert "PIN_LR_NSS   = D7" in text or "PIN_LR_NSS = D7" in text
