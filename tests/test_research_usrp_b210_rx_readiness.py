#!/usr/bin/env python3
"""Tests for H1 USRP B210 Rx-only readiness (dry-run, no hardware)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run(root: Path, *args: str):
    return subprocess.run(
        [sys.executable, *args], cwd=root, text=True, capture_output=True, check=False,
    )


def test_usrp_rx_readiness_dry_run(tmp_path):
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    out_dir = tmp_path / "report"
    result = run(
        root,
        "scripts/research_usrp_b210_rx_readiness.py",
        "--dry-run", "--run-id", "h1_dryrun_001",
        "--output-root", str(tmp_path / "runs"),
        "--output-dir", str(out_dir),
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"], cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    assert before == after

    data = json.loads((out_dir / "usrp_b210_rx_readiness.json").read_text())
    assert (out_dir / "usrp_b210_rx_readiness.md").exists()

    assert data["metadata"]["phase"] == "H1"
    assert data["metadata"]["mode"] == "dry_run"

    # RX-only, no TX.
    assert data["usrp_role"] == "rx_only"
    assert data["lr1121_role"] == "tx_only_but_tx_disabled"
    assert data["packet_transmission_executed"] is False
    assert data["rf_transmission_enabled"] is False

    # Dry-run: no probe, no capture.
    assert data["usrp_probe_executed"] is False
    assert data["rx_capture_executed"] is False

    # All validation flags false.
    assert data["hardware_validation_complete"] is False
    assert data["hil_validation_complete"] is False
    assert data["ota_validation_complete"] is False
    assert data["localization_accuracy_proven"] is False

    assert data["next_gate"] == "H1B_controlled_conducted_packet_capture_planning"

    # Metadata-only run dir created and safe.
    run_dir = tmp_path / "runs" / "h1_dryrun_001"
    meta = json.loads((run_dir / "metadata.json").read_text())
    assert meta["hardware_stage"] == "H1_rx_only_readiness"
    assert meta["lr1121_tx_enabled"] is False
    assert meta["usrp_role"] == "rx_only"
    assert meta["no_packet_tx"] is True
    assert meta["conducted_or_shielded"] is True
    assert meta["hil_validation_complete"] is False
    assert meta["hardware_validation_complete"] is False

    # No capture file produced by dry-run.
    assert not (run_dir / "noise_floor_capture.sc16").exists()

    manifest = json.loads((run_dir / "capture_manifest.json").read_text())
    assert manifest["rx_only"] is True
    assert manifest["no_packet_tx"] is True


def test_rx_command_is_receive_only(tmp_path):
    """The generated RX command must use the receive-only UHD tool and no TX flags."""
    root = Path(__file__).resolve().parents[1]
    out_dir = tmp_path / "report"
    result = run(
        root,
        "scripts/research_usrp_b210_rx_readiness.py",
        "--dry-run", "--output-dir", str(out_dir),
    )
    assert result.returncode == 0, result.stderr
    data = json.loads((out_dir / "usrp_b210_rx_readiness.json").read_text())
    cmd = data["rx_command_preview"]
    # Receive-only UHD example tool (may be an absolute path on some installs).
    assert "rx_samples_to_file" in cmd
    for tx_token in ["tx_samples", "tx_waveform", "--tx", "transmit"]:
        assert tx_token not in cmd, f"RX command contains TX token: {tx_token}"


def test_default_is_dry_run_without_flags(tmp_path):
    root = Path(__file__).resolve().parents[1]
    out_dir = tmp_path / "report"
    result = run(
        root,
        "scripts/research_usrp_b210_rx_readiness.py",
        "--output-dir", str(out_dir),
    )
    assert result.returncode == 0, result.stderr
    data = json.loads((out_dir / "usrp_b210_rx_readiness.json").read_text())
    # No flags -> safe default dry run, no hardware actions.
    assert data["metadata"]["mode"] == "dry_run"
    assert data["usrp_probe_executed"] is False
    assert data["rx_capture_executed"] is False
