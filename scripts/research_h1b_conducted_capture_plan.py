#!/usr/bin/env python3
"""H1B: controlled conducted packet capture plan/report.

Documents the go/no-go plan for the first CONDUCTED/SHIELDED LR1121 packet
capture into the USRP B210. It does NOT transmit, capture, flash, or access
hardware. Conducted/shielded path only; OTA is forbidden.

Read-only w.r.t. paper/docs/README. Does not claim HIL/OTA/hardware validation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_h1b_conducted_capture_plan"

LR1121_GETVERSION_RAW = "07 22 03 01 03"
LR1121_PIN_MAP = {"nss": "D7", "busy": "D3", "reset": "D9", "dio": "D5", "spi_mode": 0}
USRP_SERIAL = "8000304"


def build_report() -> dict[str, Any]:
    return {
        "metadata": {
            "phase": "H1B",
            "generated_by": "research_h1b_conducted_capture_plan.py",
            "source_files_modified": False,
            "mode": "planning_only_no_hardware",
            "hardware_validation_complete": False,
            "hil_validation_complete": False,
            "ota_validation_complete": False,
            "localization_accuracy_proven": False,
        },
        "lr1121_confirmed": True,
        "lr1121_getversion_raw": LR1121_GETVERSION_RAW,
        "lr1121_pin_map": LR1121_PIN_MAP,
        "usrp_rx_ready": True,
        "usrp_serial": USRP_SERIAL,
        "tx_currently_disabled": True,
        "conducted_or_shielded_required": True,
        "antenna_ota_forbidden": True,
        "required_setup": [
            "LR1121 RF output routed to attenuator / shielded enclosure / dummy-load-safe path (NO antenna).",
            "USRP B210 RX input connected via cable + attenuator to the conducted path.",
            "Conservative USRP RX gain (e.g. 20 dB or lower) to avoid front-end overload.",
            "Known fixed center frequency shared by LR1121 TX config and USRP RX.",
            "Short capture duration (1-3 s) for the first test.",
            "Conservative LR1121 output power placeholder; do not assume max power.",
        ],
        "required_metadata_fields": [
            "run_id", "timestamp_utc", "hardware_stage", "lr1121_getversion_raw",
            "lr1121_pin_map", "usrp_serial", "center_frequency_hz", "sample_rate_sps",
            "gain_db", "duration_s", "attenuator_db", "cable_loss_db",
            "conducted_or_shielded", "packet_count", "modulation",
            "ota_validation_complete", "hil_validation_complete", "hardware_validation_complete",
        ],
        "go_no_go_checklist": [
            {"id": "conducted_path_confirmed", "item": "RF path is conducted/shielded with attenuator; no antenna attached.", "required": True},
            {"id": "attenuation_adequate", "item": "Total attenuation protects USRP front-end at chosen power.", "required": True},
            {"id": "frequency_agreed", "item": "LR1121 TX center freq == USRP RX center freq.", "required": True},
            {"id": "usrp_gain_conservative", "item": "USRP RX gain set conservative (<= 20 dB to start).", "required": True},
            {"id": "firmware_arm_gate", "item": "Packet-source firmware requires arm_tx + confirm token before any TX.", "required": True},
            {"id": "single_packet", "item": "First test sends exactly one packet (packet_count=1).", "required": True},
            {"id": "operator_rf_approval", "item": "Operator has explicitly approved enabling RF for a conducted test.", "required": True},
            {"id": "no_ota", "item": "No antenna / no OTA / legal conducted test only.", "required": True},
        ],
        "first_capture_parameters": {
            "center_frequency_hz": 915000000,
            "sample_rate_sps": 1000000,
            "gain_db": 20,
            "duration_s": 2,
            "packet_count": 1,
            "modulation": "lora_or_fsk_placeholder",
        },
        "expected_files": [
            "metadata.json", "capture_manifest.json", "planned_usrp_command.txt",
            "planned_serial_commands.txt", "serial_tx_log.txt", "controlled_capture.sc16",
            "extracted_observations.csv", "analysis_summary.json",
        ],
        "success_criteria": [
            "Conducted capture file present with expected sample count.",
            "Serial TX log shows exactly one packet with TX_EXECUTED=true after arm.",
            "A signal feature is visible in the capture at the configured frequency.",
            "Run metadata is complete and the run is repeatable.",
        ],
        "claim_allowed_after_h1c": [
            "A controlled conducted capture of an LR1121 packet was recorded (engineering milestone).",
            "Hardware-derived observations can begin to be compared to software diagnostics (qualitative).",
        ],
        "claim_still_forbidden_after_h1c": [
            "completed HIL validation (requires repeatable, metadata-complete, feature-extracted captures)",
            "real satellite OTA validation",
            "real satellite capture validated",
            "localization accuracy proven",
            "meter-level localization",
            "deployment-ready system",
        ],
        "next_gate": "H1C_actual_conducted_one_packet_capture_with_operator_rf_approval",
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "h1b_conducted_capture_plan.json"
    md_path = out_dir / "h1b_conducted_capture_plan.md"
    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# H1B Controlled Conducted Packet Capture Plan",
        "",
        "Planning only. No transmit, no capture, no flash, no hardware access.",
        "Conducted/shielded path only; OTA forbidden. Does not claim HIL/OTA/hardware validation.",
        "",
        f"- lr1121_confirmed: {report['lr1121_confirmed']}",
        f"- usrp_rx_ready: {report['usrp_rx_ready']} (serial {report['usrp_serial']})",
        f"- tx_currently_disabled: {report['tx_currently_disabled']}",
        f"- conducted_or_shielded_required: {report['conducted_or_shielded_required']}",
        f"- antenna_ota_forbidden: {report['antenna_ota_forbidden']}",
        f"- next_gate: {report['next_gate']}",
        "",
        "## Required Setup",
        "",
    ]
    md += [f"- {s}" for s in report["required_setup"]]
    md += ["", "## Go / No-Go Checklist", ""]
    for c in report["go_no_go_checklist"]:
        md.append(f"- [ ] {c['id']}: {c['item']}")
    md += ["", "## First Capture Parameters", ""]
    for k, v in report["first_capture_parameters"].items():
        md.append(f"- {k}: {v}")
    md += ["", "## Success Criteria", ""] + [f"- {s}" for s in report["success_criteria"]]
    md += ["", "## Claim Allowed After H1C", ""] + [f"- {s}" for s in report["claim_allowed_after_h1c"]]
    md += ["", "## Claim Still Forbidden After H1C", ""] + [f"- {s}" for s in report["claim_still_forbidden_after_h1c"]]
    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"next_gate: {report['next_gate']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    write_outputs(build_report(), args.output_dir)


if __name__ == "__main__":
    main()
