#!/usr/bin/env python3
"""Tests for H1C controlled capture runner (dry-run, no hardware) + firmware safety."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def run(root: Path, *args: str):
    return subprocess.run([sys.executable, *args], cwd=root, text=True, capture_output=True, check=False)


def test_h1c_dry_run_no_tx_no_capture(tmp_path):
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    out_dir = tmp_path / "report"
    result = run(
        root, "scripts/research_h1c_controlled_capture_runner.py",
        "--dry-run", "--run-id", "h1c_dryrun_001",
        "--output-root", str(tmp_path / "runs"), "--output-dir", str(out_dir),
        "--center-frequency-hz", "915000000", "--sample-rate-sps", "1000000",
        "--gain-db", "20", "--duration-s", "1",
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    assert before == after

    data = json.loads((out_dir / "h1c_controlled_capture_runner.json").read_text())
    assert data["metadata"]["phase"] == "H1C"
    assert data["metadata"]["mode"] == "dry_run"
    assert data["packet_transmission_executed"] is False
    assert data["rx_capture_executed"] is False
    assert data["capture_file_path"] is None
    assert data["ota_validation_complete"] is False
    assert data["hil_validation_complete"] is False
    assert data["hardware_validation_complete"] is False
    assert data["localization_accuracy_proven"] is False

    # Planned USRP command is receive-only.
    assert "rx_samples_to_file" in data["planned_usrp_command"]
    for tx_token in ["tx_samples", "tx_waveform", "--tx"]:
        assert tx_token not in data["planned_usrp_command"]

    # Planned serial commands require the arm confirm token.
    assert "arm_tx CONFIRM_CONDUCTED_TEST" in data["planned_serial_commands"]

    # Run dir metadata-only, no capture file.
    run_dir = tmp_path / "runs" / "h1c_dryrun_001"
    for f in ["metadata.json", "capture_manifest.json", "planned_usrp_command.txt",
              "planned_serial_commands.txt", "analysis_summary.json"]:
        assert (run_dir / f).exists(), f"missing {f}"
    assert not (run_dir / "controlled_capture.sc16").exists()

    meta = json.loads((run_dir / "metadata.json").read_text())
    assert meta["hardware_stage"] == "H1C_controlled_conducted_capture"
    assert meta["conducted_or_shielded"] is True
    assert meta["packet_transmission_executed"] is False
    assert meta["rx_capture_executed"] is False
    assert meta["hil_validation_complete"] is False
    assert meta["hardware_validation_complete"] is False


def test_default_is_dry_run(tmp_path):
    root = Path(__file__).resolve().parents[1]
    out_dir = tmp_path / "report"
    result = run(root, "scripts/research_h1c_controlled_capture_runner.py", "--output-dir", str(out_dir))
    assert result.returncode == 0, result.stderr
    data = json.loads((out_dir / "h1c_controlled_capture_runner.json").read_text())
    assert data["metadata"]["mode"] == "dry_run"
    assert data["packet_transmission_executed"] is False
    assert data["rx_capture_executed"] is False


def test_controlled_firmware_is_tx_gated():
    root = Path(__file__).resolve().parents[1]
    fw = root / "firmware/lr1121_controlled_packet_source/lr1121_controlled_packet_source.ino"
    assert fw.exists()
    text = fw.read_text()

    # TX disabled by default + compile-time gate default off.
    assert "#define ENABLE_REAL_TX 0" in text
    assert "g_rf_transmission_enabled = false" in text

    # Arm gate with confirm token.
    assert "CONFIRM_CONDUCTED_TEST" in text
    assert "send_test_packet refused: not armed" in text

    # HIL/OTA/hardware validation false by default.
    assert "HIL_VALIDATION_COMPLETE      = false" in text
    assert "OTA_VALIDATION_COMPLETE      = false" in text
    assert "HARDWARE_VALIDATION_COMPLETE = false" in text

    # No auto-transmit: setup() and loop() must not call sendTestPacket().
    setup_block = re.search(r"void setup\(\)\s*\{.*?\n\}", text, re.DOTALL)
    loop_block = re.search(r"void loop\(\)\s*\{.*?\n\}", text, re.DOTALL)
    assert setup_block and "sendTestPacket" not in setup_block.group(0)
    assert loop_block and "sendTestPacket" not in loop_block.group(0)
