#!/usr/bin/env python3
"""H0: Arduino/STM32 firmware bring-up plan and TX-safety record.

Records the resolved flash target, FQBN, firmware path, and the TX-safety
contract for the LR1121 TX-disabled init firmware. It does NOT compile, flash,
open serial, or transmit. It only documents the bring-up state for review.

Read-only w.r.t. paper/docs/README. Does not claim HIL/OTA/hardware validation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_arduino_firmware_bringup_plan"

FIRMWARE_REL = "firmware/lr1121_tx_disabled_init/lr1121_tx_disabled_init.ino"
TARGET_PORT = "/dev/cu.usbmodem1303"
FQBN_CANDIDATE = "STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_L476RG"

# Source-level TX-safety markers expected to be present / absent in the firmware.
EXPECTED_PRESENT = [
    "TX_DEFAULT_DISABLED",
    "RF_TRANSMISSION_ENABLED",
    "PACKET_TRANSMISSION_EXECUTED",
    "HIL_VALIDATION_COMPLETE",
    "TX command blocked in this firmware build",
]
FORBIDDEN_TX_TOKENS = ["startTransmit", "setTx(", ".transmit(", "beginTransmit"]


def firmware_safety_scan() -> dict[str, Any]:
    fw = ROOT / FIRMWARE_REL
    if not fw.exists():
        return {"firmware_present": False}
    text = fw.read_text(errors="ignore")
    present = {tok: (tok in text) for tok in EXPECTED_PRESENT}
    forbidden = {tok: (tok in text) for tok in FORBIDDEN_TX_TOKENS}
    return {
        "firmware_present": True,
        "expected_markers_present": present,
        "all_expected_markers_present": all(present.values()),
        "forbidden_tx_tokens_found": {k: v for k, v in forbidden.items() if v},
        "no_forbidden_tx_tokens": not any(forbidden.values()),
    }


def build_report() -> dict[str, Any]:
    scan = firmware_safety_scan()
    tx_safe = scan.get("firmware_present", False) and scan.get(
        "all_expected_markers_present", False
    ) and scan.get("no_forbidden_tx_tokens", False)
    return {
        "metadata": {
            "phase": "H0",
            "generated_by": "research_arduino_firmware_bringup_plan.py",
            "source_files_modified": False,
            "mode": "documentation_only_no_flash_no_serial",
            "hardware_validation_complete": False,
            "hil_validation_complete": False,
            "ota_validation_complete": False,
            "localization_accuracy_proven": False,
        },
        "target_port": TARGET_PORT,
        "fqbn_candidate": FQBN_CANDIDATE,
        "firmware_path": FIRMWARE_REL,
        "firmware_tx_default_disabled": True,
        "auto_transmit_on_boot": False,
        "rf_transmission_enabled": False,
        "packet_transmission_executed": False,
        "hardware_validation_complete": False,
        "hil_validation_complete": False,
        "ota_validation_complete": False,
        "firmware_safety_scan": scan,
        "firmware_tx_safe_by_static_scan": tx_safe,
        "bringup_commands": {
            "discovery": [
                "arduino-cli board list",
                "arduino-cli board listall | grep -i nucleo",
                "arduino-cli core list",
            ],
            "compile": f"arduino-cli compile --fqbn {FQBN_CANDIDATE} firmware/lr1121_tx_disabled_init",
            "upload": f"arduino-cli upload -p {TARGET_PORT} --fqbn {FQBN_CANDIDATE} firmware/lr1121_tx_disabled_init",
            "serial_read": f"read {TARGET_PORT} at 115200 (send: status | init); tx is blocked",
        },
        "allowed_now": [
            "arduino-cli board list / listall / core list",
            "arduino-cli compile",
            "arduino-cli upload (unique FQBN + clear port + TX-safe firmware)",
            "serial boot log read after upload",
        ],
        "still_forbidden": [
            "actual packet TX",
            "RF transmit",
            "OTA",
            "completed HIL validation",
            "localization accuracy proven",
        ],
        "recommended_next_action": (
            "Confirm board silk label matches NUCLEO_L476RG. With TX-safe firmware flashed, "
            "verify serial shows RF_TRANSMISSION_ENABLED=false before any further work. "
            "Do not enable RF; do not claim hardware validation."
        ),
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "arduino_firmware_bringup_plan.json"
    md_path = out_dir / "arduino_firmware_bringup_plan.md"

    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# H0 Arduino/STM32 Firmware Bring-up Plan",
        "",
        "Documents flash target, FQBN, firmware path, and TX-safety contract.",
        "Does not compile/flash/transmit. Does not claim HIL/OTA/hardware validation.",
        "",
        f"- target_port: {report['target_port']}",
        f"- fqbn_candidate: {report['fqbn_candidate']}",
        f"- firmware_path: {report['firmware_path']}",
        f"- firmware_tx_default_disabled: {report['firmware_tx_default_disabled']}",
        f"- auto_transmit_on_boot: {report['auto_transmit_on_boot']}",
        f"- rf_transmission_enabled: {report['rf_transmission_enabled']}",
        f"- packet_transmission_executed: {report['packet_transmission_executed']}",
        f"- hardware_validation_complete: {report['hardware_validation_complete']}",
        f"- firmware_tx_safe_by_static_scan: {report['firmware_tx_safe_by_static_scan']}",
        "",
        "## Firmware Safety Scan",
        "",
    ]
    for k, v in report["firmware_safety_scan"].items():
        md.append(f"- {k}: {v}")
    md += ["", "## Bring-up Commands", "",
           f"- compile: `{report['bringup_commands']['compile']}`",
           f"- upload: `{report['bringup_commands']['upload']}`",
           f"- serial_read: {report['bringup_commands']['serial_read']}"]
    md += ["", "## Allowed Now", ""] + [f"- {c}" for c in report["allowed_now"]]
    md += ["", "## Still Forbidden", ""] + [f"- {c}" for c in report["still_forbidden"]]
    md += ["", "## Recommended Next Action", "", report["recommended_next_action"]]
    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"firmware_tx_safe_by_static_scan: {report['firmware_tx_safe_by_static_scan']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    write_outputs(build_report(), args.output_dir)


if __name__ == "__main__":
    main()
