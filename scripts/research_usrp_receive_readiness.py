#!/usr/bin/env python3
"""H1: USRP B210 Rx-only receive readiness (dry-run by default).

Default mode checks ONLY for UHD command availability via shutil.which. It does
NOT probe hardware, does NOT capture, and does NOT transmit. Deep hardware
probing (uhd_find_devices) requires --probe AND explicit operator approval and
is gated off by default.

Read-only with respect to paper/docs/README. Does not claim HIL/OTA/hardware
validation.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_usrp_receive_readiness"

UHD_COMMANDS = ["uhd_find_devices", "uhd_usrp_probe", "uhd_config_info"]


def command_availability() -> dict[str, bool]:
    return {cmd: shutil.which(cmd) is not None for cmd in UHD_COMMANDS}


def build_report(probe_requested: bool) -> dict[str, Any]:
    avail = command_availability()
    return {
        "metadata": {
            "phase": "H1",
            "generated_by": "research_usrp_receive_readiness.py",
            "source_files_modified": False,
            "mode": "dry_run_command_availability_only",
            "hardware_validation_complete": False,
            "hil_validation_complete": False,
            "ota_validation_complete": False,
        },
        "usrp_role": "rx_only",
        "transmit_forbidden": True,
        "ota_allowed": False,
        "conducted_or_shielded_required": True,
        "uhd_command_availability": avail,
        "uhd_tools_present": all(avail.values()),
        "probe_requested": probe_requested,
        "probe_executed": False,
        "manual_gates": [
            "Operator must approve before deep hardware probe (uhd_find_devices).",
            "Operator must approve before changing USRP RF gain/frequency.",
            "Operator must approve before connecting antennas.",
            "No OTA; conducted/shielded only.",
        ],
        "claim_boundary": {
            "allowed_now": [
                "UHD tool availability checked (no hardware accessed).",
                "Rx-only capture readiness prepared (not capturing).",
            ],
            "forbidden_now": [
                "real satellite capture validated",
                "completed HIL validation",
                "localization accuracy proven",
            ],
        },
        "recommended_next_action": (
            "If UHD tools are missing, install UHD on the Mac. Do not probe or capture "
            "until operator approves the manual gates."
        ),
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "usrp_receive_readiness.json"
    md_path = out_dir / "usrp_receive_readiness.md"

    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# H1 USRP B210 Rx-only Receive Readiness (dry-run)",
        "",
        "Default mode checks UHD command availability only. No hardware probe, no capture, no transmit.",
        "Does not claim HIL/OTA/hardware validation.",
        "",
        f"- usrp_role: {report['usrp_role']}",
        f"- transmit_forbidden: {report['transmit_forbidden']}",
        f"- ota_allowed: {report['ota_allowed']}",
        f"- uhd_tools_present: {report['uhd_tools_present']}",
        f"- probe_executed: {report['probe_executed']}",
        "",
        "## UHD Command Availability",
        "",
    ]
    for cmd, present in report["uhd_command_availability"].items():
        md.append(f"- {cmd}: {'found' if present else 'missing'}")

    md += ["", "## Manual Gates", ""]
    for g in report["manual_gates"]:
        md.append(f"- {g}")

    md += ["", "## Claim Boundary", "", "### Allowed Now", ""]
    for c in report["claim_boundary"]["allowed_now"]:
        md.append(f"- {c}")
    md += ["", "### Forbidden Now", ""]
    for c in report["claim_boundary"]["forbidden_now"]:
        md.append(f"- {c}")

    md += ["", "## Recommended Next Action", "", report["recommended_next_action"]]
    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"uhd_tools_present: {report['uhd_tools_present']} | probe_executed: {report['probe_executed']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Request deep hardware probe. Still gated: requires explicit operator approval; not run by this script.",
    )
    args = parser.parse_args()
    # Note: even with --probe, this script does not execute hardware probing.
    # It only records that a probe was requested, leaving execution to a manual,
    # operator-approved step.
    write_outputs(build_report(probe_requested=args.probe), args.output_dir)


if __name__ == "__main__":
    main()
