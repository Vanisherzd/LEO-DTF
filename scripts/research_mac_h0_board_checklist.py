#!/usr/bin/env python3
"""H0: Mac board / firmware / serial / Tx-only readiness checklist.

This script generates a pre-flight checklist for LR1121/STM32 board bring-up on
the user's Mac. It does NOT flash firmware, does NOT enable RF transmission, and
does NOT access the board. Every gated action defaults to a manual-confirmation
requirement.

It is read-only with respect to paper/docs/README/workflows and does not claim
any HIL/OTA/hardware validation.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_mac_h0_board_checklist"

# Toolchain commands that may be needed for H0 (availability check only; never run).
TOOLCHAIN_COMMANDS = ["python3", "git", "uv"]
OPTIONAL_FLASH_TOOLS = ["STM32_Programmer_CLI", "st-flash", "openocd", "dfu-util"]
OPTIONAL_SERIAL_TOOLS = ["screen", "minicom"]


def tool_availability(commands: list[str]) -> dict[str, bool]:
    return {cmd: shutil.which(cmd) is not None for cmd in commands}


def build_report() -> dict[str, Any]:
    return {
        "metadata": {
            "phase": "H0",
            "generated_by": "research_mac_h0_board_checklist.py",
            "source_files_modified": False,
            "intended_environment": "User Mac with physical LR1121/STM32 board; not inside container.",
            "hardware_validation_complete": False,
            "hil_validation_complete": False,
            "ota_validation_complete": False,
            "localization_accuracy_proven": False,
        },
        "board": {
            "board_id": "unknown",
            "second_board_connected": True,
            "second_board_correct_firmware": False,
            "firmware_status": "not_confirmed",
            "firmware_hash": "unknown",
            "serial_port": "unknown",
            "serial_port_required": True,
        },
        "roles_and_safety": {
            "lr1121_tx_only": True,
            "lr1121_rx_claim_forbidden": True,
            "usrp_role_reference": "rx_only (see H1 capture readiness)",
            "rf_transmission_enabled": False,
            "ota_allowed": False,
            "conducted_or_shielded_required": True,
            "manual_gate_required_before_flashing": True,
            "manual_gate_required_before_tx": True,
        },
        "checklist": [
            {"id": "identify_board", "item": "Identify board (LR1121/STM32 dev kit) and record board_id.", "done": False},
            {"id": "confirm_firmware_target", "item": "Confirm correct firmware target/image for the second board.", "done": False},
            {"id": "confirm_flashing_toolchain", "item": "Confirm flashing toolchain present (e.g. STM32_Programmer_CLI / openocd / dfu-util).", "done": False},
            {"id": "confirm_serial_log", "item": "Confirm serial monitor and tx_log.csv logging path.", "done": False},
            {"id": "confirm_lr1121_config", "item": "Confirm LR1121 config (center frequency, bandwidth, packet interval/duration, modulation).", "done": False},
            {"id": "confirm_no_antenna_setup", "item": "Confirm NO antenna / shielded enclosure / attenuator + dummy load (conducted only).", "done": False},
            {"id": "confirm_tx_log_format", "item": "Confirm tx_log.csv format matches the H1 template header.", "done": False},
            {"id": "confirm_no_tx_until_gate", "item": "Confirm board does NOT transmit until explicit manual gate is approved.", "done": False},
        ],
        "manual_gates": {
            "before_flashing": [
                "Operator must confirm exact firmware image + target board.",
                "Operator must explicitly approve flashing; script will NOT flash.",
            ],
            "before_rf_transmission": [
                "Confirm conducted/shielded path with attenuator/dummy load (no antenna).",
                "Confirm no unlicensed OTA.",
                "Operator must explicitly approve enabling Tx; script will NOT enable RF.",
            ],
        },
        "tool_availability": {
            "core": tool_availability(TOOLCHAIN_COMMANDS),
            "optional_flash_tools": tool_availability(OPTIONAL_FLASH_TOOLS),
            "optional_serial_tools": tool_availability(OPTIONAL_SERIAL_TOOLS),
        },
        "claim_boundary": {
            "allowed_after_h0": [
                "Board identified and firmware target confirmed (engineering milestone).",
                "Tx packet-source configuration prepared (not yet transmitting).",
            ],
            "still_forbidden_after_h0": [
                "completed HIL validation",
                "real satellite OTA validation",
                "localization accuracy proven",
                "hardware oscillator specification derived",
            ],
        },
        "recommended_next_action": (
            "Complete H0 checklist items manually; do not flash or transmit. "
            "When ready, run H1 manifest init (metadata-only) and request manual gate approvals."
        ),
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "mac_h0_board_checklist.json"
    md_path = out_dir / "mac_h0_board_checklist.md"

    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# H0 Mac Board / Firmware / Serial / Tx-only Checklist",
        "",
        "This checklist prepares LR1121/STM32 bring-up on the Mac.",
        "It does NOT flash firmware, does NOT enable RF transmission, and does NOT access the board.",
        "It does not claim HIL/OTA/hardware validation.",
        "",
        "## Board",
        "",
    ]
    for k, v in report["board"].items():
        md.append(f"- {k}: {v}")

    md += ["", "## Roles and Safety", ""]
    for k, v in report["roles_and_safety"].items():
        md.append(f"- {k}: {v}")

    md += ["", "## Checklist", ""]
    for item in report["checklist"]:
        md.append(f"- [ ] {item['id']}: {item['item']}")

    md += ["", "## Manual Gates — Before Flashing", ""]
    for g in report["manual_gates"]["before_flashing"]:
        md.append(f"- {g}")
    md += ["", "## Manual Gates — Before RF Transmission", ""]
    for g in report["manual_gates"]["before_rf_transmission"]:
        md.append(f"- {g}")

    md += ["", "## Tool Availability (check only; nothing executed)", ""]
    for group, tools in report["tool_availability"].items():
        md.append(f"- {group}:")
        for cmd, present in tools.items():
            md.append(f"    - {cmd}: {'found' if present else 'missing'}")

    md += ["", "## Claim Boundary", "", "### Allowed After H0", ""]
    for c in report["claim_boundary"]["allowed_after_h0"]:
        md.append(f"- {c}")
    md += ["", "### Still Forbidden After H0", ""]
    for c in report["claim_boundary"]["still_forbidden_after_h0"]:
        md.append(f"- {c}")

    md += ["", "## Recommended Next Action", "", report["recommended_next_action"]]

    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print("phase: H0 | firmware_status: not_confirmed | rf_transmission_enabled: False | ota_allowed: False")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    write_outputs(build_report(), args.output_dir)


if __name__ == "__main__":
    main()
