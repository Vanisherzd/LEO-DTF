#!/usr/bin/env python3
"""Tests for H0.5B LR1121 read-only SPI sweep report (no hardware)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FORBIDDEN_TX_TOKENS = ["startTransmit", "beginTransmit", "setTx(", "SetTx(", ".transmit(", "sendPacket", "startTx"]


def test_lr1121_spi_sweep_report_runs_no_hardware():
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    result = subprocess.run(
        [sys.executable, "scripts/research_lr1121_spi_sweep_report.py"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    assert before == after

    out = root / "experiments/results/research_lr1121_spi_sweep_report"
    data = json.loads((out / "lr1121_spi_sweep_report.json").read_text())
    assert (out / "lr1121_spi_sweep_report.md").exists()

    meta = data["metadata"]
    assert meta["phase"] == "H0.5B"
    assert meta["mode"] == "documentation_only_no_flash_no_serial"

    # All validation/RF flags false.
    assert data["rf_transmission_enabled"] is False
    assert data["packet_transmission_executed"] is False
    assert data["hardware_validation_complete"] is False
    assert data["hil_validation_complete"] is False
    assert data["ota_validation_complete"] is False
    # Plausible SPI response must not auto-confirm LR1121 init.
    assert data["lr1121_init_verified"] is False

    # Candidate pin maps must include the required variants.
    maps = data["candidate_pin_maps"]
    # D7/D3/A0/D5 variant.
    assert maps["map_alt_shield"] == {"NSS": "D7", "BUSY": "D3", "RESET": "A0", "DIO": "D5"}
    # D10/D8/D9/D3 variant.
    assert maps["map_current"] == {"NSS": "D10", "BUSY": "D8", "RESET": "D9", "DIO": "D3"}

    # SPI settings + variants present.
    assert any(s["hz"] == 125000 for s in data["spi_settings"])
    assert any(s["mode"] == 3 for s in data["spi_settings"])
    assert "variant_raw_0101" in data["command_variants"]

    # Firmware statically TX-safe.
    scan = data["firmware_safety_scan"]
    assert scan["firmware_present"] is True
    assert scan["all_expected_markers_present"] is True
    assert scan["no_forbidden_tx_tokens"] is True
    assert data["firmware_tx_safe_by_static_scan"] is True
    assert "next_gate" in data


def test_sweep_report_parses_log(tmp_path):
    root = Path(__file__).resolve().parents[1]
    log = tmp_path / "spi_sweep_log.txt"
    log.write_text(
        "SWEEP_BEGIN\n"
        "header,RESULT,map,spi_mode,spi_hz,busy_before,busy_after,variant,response_hex,score,interpretation\n"
        "RESULT,map_current,0,500000,0,0,variant_raw_0101,00-00-00-00,all_zero,bad_likely_power_wiring_miso\n"
        "RESULT,map_alt_reset_d9,0,500000,0,0,variant_raw_0101,06-22-03-01-03,changing_nonzero,plausible\n"
        "SPI_PROBE_PLAUSIBLE=true\n"
        "SWEEP_END\n"
    )
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "scripts/research_lr1121_spi_sweep_report.py",
         "--sweep-log", str(log), "--output-dir", str(out)],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads((out / "lr1121_spi_sweep_report.json").read_text())
    assert data["best_candidate"] == "map_alt_reset_d9"
    assert data["best_response_hex"] == "06-22-03-01-03"
    assert data["spi_probe_plausible"] is True
    # Still must not claim validation.
    assert data["lr1121_init_verified"] is False
    assert data["next_gate"] == "plausible_response_implement_vendor_confirmed_getversion_parser"


def test_firmware_source_has_no_active_tx_calls():
    root = Path(__file__).resolve().parents[1]
    fw = root / "firmware/lr1121_tx_disabled_init/lr1121_tx_disabled_init.ino"
    assert fw.exists()
    text = fw.read_text()
    for forbidden in FORBIDDEN_TX_TOKENS:
        assert forbidden not in text, f"firmware contains forbidden active TX call: {forbidden}"
    assert "TX command blocked in this firmware build" in text
