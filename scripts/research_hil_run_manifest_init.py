#!/usr/bin/env python3
"""H1: HIL run manifest initializer (metadata-only).

Creates a metadata-only run directory for a planned conducted/shielded capture.
It does NOT create IQ data, does NOT capture, does NOT transmit, and does NOT
claim any HIL/OTA/hardware validation. It only scaffolds:

  data/hil_runs/{run_id}/metadata.json
  data/hil_runs/{run_id}/README.md
  data/hil_runs/{run_id}/tx_log_template.csv
  data/hil_runs/{run_id}/capture_manifest.json

Use --output-root to redirect (tests use a tmp dir). Generated run directories
under data/hil_runs/ are gitignored and must not be committed.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "data/hil_runs"

TX_LOG_HEADER = "packet_index,timestamp_ms,center_frequency_hz,packet_duration_ms,modulation,notes"

EXPECTED_FILES = [
    "metadata.json",
    "README.md",
    "tx_log.csv",
    "capture_IQ.sigmf-data",
    "capture_IQ.sigmf-meta",
    "extracted_observations.csv",
    "analysis_summary.json",
]


def build_metadata(run_id: str, operator: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "operator": operator,
        "hardware_stage": "H0/H1_pre_capture",
        "hardware_validation_complete": False,
        "hil_validation_complete": False,
        "ota_validation_complete": False,
        "lr1121_role": "tx_only",
        "usrp_role": "rx_only",
        "second_board_correct_firmware": False,
        "firmware_hash": "unknown",
        "board_id": "unknown",
        "serial_port": "unknown",
        "center_frequency_hz": None,
        "bandwidth_hz": None,
        "packet_interval_s": None,
        "packet_duration_ms": None,
        "usrp_sample_rate_sps": None,
        "usrp_gain_db": None,
        "clock_source": "unknown",
        "attenuator_db": None,
        "cable_loss_db": None,
        "temperature_c": None,
        "conducted_or_shielded": True,
        "ota_allowed": False,
        "notes": "",
    }


def build_capture_manifest() -> dict[str, Any]:
    return {
        "expected_files": EXPECTED_FILES,
        "metadata_required": True,
        "tx_log_required": True,
        "iq_capture_required_later": True,
        "extracted_observations_required_later": True,
        "claim_boundary": {
            "stage": "pre_capture",
            "hardware_validation_complete": False,
            "hil_validation_complete": False,
            "ota_validation_complete": False,
            "localization_accuracy_proven": False,
            "allowed_now": [
                "Metadata-only run scaffold prepared.",
                "Planned conducted/shielded capture parameters recorded.",
            ],
            "forbidden_now": [
                "completed HIL validation",
                "real satellite OTA validation",
                "real satellite capture validated",
                "localization accuracy proven",
            ],
        },
    }


def run_readme(run_id: str) -> str:
    return (
        f"# HIL Run {run_id} (metadata-only scaffold)\n\n"
        "This directory is a PRE-CAPTURE scaffold. No IQ data, no capture, no transmission.\n\n"
        "- lr1121_role: tx_only\n"
        "- usrp_role: rx_only\n"
        "- conducted_or_shielded: true\n"
        "- ota_allowed: false\n"
        "- hardware_validation_complete: false\n"
        "- hil_validation_complete: false\n\n"
        "## Manual gates (operator must approve before each)\n"
        "1. Flashing firmware to the board.\n"
        "2. Enabling any RF transmission.\n"
        "3. Changing USRP RF gain/frequency for capture.\n"
        "4. Connecting antennas.\n"
        "5. Any OTA operation (not permitted unlicensed).\n\n"
        "## Files\n"
        "- metadata.json: run metadata (fill in before capture).\n"
        "- tx_log_template.csv: copy to tx_log.csv and fill during Tx.\n"
        "- capture_manifest.json: expected files + claim boundary.\n"
        "- capture_IQ.sigmf-* / extracted_observations.csv / analysis_summary.json: created later, after approved capture.\n"
    )


def init_run(run_id: str, operator: str, output_root: Path) -> dict[str, Any]:
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    metadata = build_metadata(run_id, operator)
    manifest = build_capture_manifest()

    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    (run_dir / "capture_manifest.json").write_text(json.dumps(manifest, indent=2))
    (run_dir / "tx_log_template.csv").write_text(TX_LOG_HEADER + "\n")
    (run_dir / "README.md").write_text(run_readme(run_id))

    return {
        "run_dir": str(run_dir),
        "metadata": metadata,
        "capture_manifest": manifest,
        "created_files": [
            str(run_dir / "metadata.json"),
            str(run_dir / "capture_manifest.json"),
            str(run_dir / "tx_log_template.csv"),
            str(run_dir / "README.md"),
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--operator", default="unknown")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    result = init_run(args.run_id, args.operator, args.output_root)
    print(f"Initialized metadata-only run scaffold: {result['run_dir']}")
    for f in result["created_files"]:
        print(f"  wrote {f}")
    print("NOTE: no IQ data, no capture, no transmission. hardware_validation_complete=False")


if __name__ == "__main__":
    main()
