#!/usr/bin/env python3
"""Tests for H1 HIL run manifest initializer (metadata-only, tmp_path)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_hil_run_manifest_init_metadata_only(tmp_path):
    root = Path(__file__).resolve().parents[1]

    before = subprocess.run(
        ["git", "status", "--short"],
        cwd=root, text=True, capture_output=True, check=True,
    ).stdout

    run_id = "dryrun_h0_001"
    result = subprocess.run(
        [
            sys.executable, "scripts/research_hil_run_manifest_init.py",
            "--run-id", run_id,
            "--operator", "unknown",
            "--output-root", str(tmp_path),
        ],
        cwd=root, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    after = subprocess.run(
        ["git", "status", "--short"],
        cwd=root, text=True, capture_output=True, check=True,
    ).stdout
    # Writing to tmp_path must not change the repo working tree.
    assert before == after

    run_dir = tmp_path / run_id
    metadata_path = run_dir / "metadata.json"
    manifest_path = run_dir / "capture_manifest.json"
    tx_template_path = run_dir / "tx_log_template.csv"
    readme_path = run_dir / "README.md"

    assert metadata_path.exists()
    assert manifest_path.exists()
    assert tx_template_path.exists()
    assert readme_path.exists()

    # No IQ data must be created by init.
    assert not (run_dir / "capture_IQ.sigmf-data").exists()
    assert not (run_dir / "capture_IQ.sigmf-meta").exists()

    meta = json.loads(metadata_path.read_text())
    assert meta["run_id"] == run_id
    assert meta["operator"] == "unknown"
    assert meta["hardware_validation_complete"] is False
    assert meta["hil_validation_complete"] is False
    assert meta["ota_validation_complete"] is False
    assert meta["lr1121_role"] == "tx_only"
    assert meta["usrp_role"] == "rx_only"
    assert meta["second_board_correct_firmware"] is False
    assert meta["ota_allowed"] is False
    assert meta["conducted_or_shielded"] is True
    # Capture parameters start unset.
    assert meta["center_frequency_hz"] is None
    assert meta["usrp_sample_rate_sps"] is None

    # Required metadata schema fields all present.
    for field in [
        "run_id", "timestamp_utc", "operator", "hardware_stage", "firmware_hash",
        "board_id", "serial_port", "center_frequency_hz", "bandwidth_hz",
        "packet_interval_s", "packet_duration_ms", "usrp_sample_rate_sps",
        "usrp_gain_db", "clock_source", "attenuator_db", "cable_loss_db",
        "temperature_c", "notes",
    ]:
        assert field in meta, f"missing metadata field: {field}"

    manifest = json.loads(manifest_path.read_text())
    assert manifest["metadata_required"] is True
    assert manifest["tx_log_required"] is True
    assert manifest["iq_capture_required_later"] is True
    assert manifest["extracted_observations_required_later"] is True
    cb = manifest["claim_boundary"]
    assert cb["hardware_validation_complete"] is False
    assert cb["localization_accuracy_proven"] is False

    header = tx_template_path.read_text().splitlines()[0]
    assert header == "packet_index,timestamp_ms,center_frequency_hz,packet_duration_ms,modulation,notes"
