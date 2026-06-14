#!/usr/bin/env python3
"""H0: Board discovery report (inspection-only, no flash, no serial open).

Runs `arduino-cli board list` (read-only) when arduino-cli is available and
records detected ports, candidate FQBNs, and whether the FQBN is ambiguous (a
hard gate before any upload). It does NOT open serial, does NOT flash, and does
NOT transmit. Degrades gracefully when arduino-cli or hardware is absent (so CI
runs without hardware).

Read-only w.r.t. paper/docs/README. Does not claim HIL/OTA/hardware validation.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_h0_board_discovery"


def arduino_board_list() -> dict[str, Any]:
    if shutil.which("arduino-cli") is None:
        return {"arduino_cli_present": False, "ports": [], "raw_available": False}
    try:
        result = subprocess.run(
            ["arduino-cli", "board", "list", "--json"],
            text=True, capture_output=True, check=False, timeout=20,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {"arduino_cli_present": True, "ports": [], "raw_available": False}

    if result.returncode != 0 or not result.stdout.strip():
        return {"arduino_cli_present": True, "ports": [], "raw_available": False}

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"arduino_cli_present": True, "ports": [], "raw_available": False}

    detected = data.get("detected_ports", data) if isinstance(data, dict) else data
    ports = []
    for entry in detected if isinstance(detected, list) else []:
        port = entry.get("port", {})
        matching = entry.get("matching_boards", []) or []
        fqbns = [b.get("fqbn") for b in matching if b.get("fqbn")]
        ports.append({
            "address": port.get("address"),
            "protocol": port.get("protocol"),
            "candidate_fqbns": fqbns,
            "fqbn_count": len(fqbns),
            "fqbn_ambiguous": len(fqbns) > 1,
            "fqbn_unknown": len(fqbns) == 0,
        })
    return {"arduino_cli_present": True, "ports": ports, "raw_available": True}


def build_report() -> dict[str, Any]:
    listing = arduino_board_list()
    usb_ports = [p for p in listing["ports"] if p.get("protocol") == "serial" and (p.get("address") or "").find("usb") != -1 or p.get("candidate_fqbns")]
    any_ambiguous = any(p["fqbn_ambiguous"] for p in listing["ports"])
    any_unique = any(p["fqbn_count"] == 1 for p in listing["ports"])

    if not listing["arduino_cli_present"]:
        upload_gate = "blocked_no_arduino_cli"
    elif not listing["ports"] or not (any_ambiguous or any_unique):
        upload_gate = "blocked_no_candidate_board"
    elif any_ambiguous and not any_unique:
        upload_gate = "blocked_fqbn_ambiguous_needs_operator_choice"
    elif any_unique:
        upload_gate = "fqbn_resolvable_but_upload_still_requires_firmware_source_and_operator_ok"
    else:
        upload_gate = "blocked_unknown"

    return {
        "metadata": {
            "phase": "H0",
            "generated_by": "research_h0_board_discovery.py",
            "source_files_modified": False,
            "mode": "inspection_only_no_flash_no_serial",
            "hardware_validation_complete": False,
            "hil_validation_complete": False,
            "ota_validation_complete": False,
            "localization_accuracy_proven": False,
        },
        "arduino_cli_present": listing["arduino_cli_present"],
        "detected_ports": listing["ports"],
        "candidate_ports_with_boards": usb_ports,
        "fqbn_ambiguous_detected": any_ambiguous,
        "fqbn_unique_detected": any_unique,
        "upload_gate": upload_gate,
        "stop_conditions": {
            "fqbn_ambiguous_would_risk_wrong_target": any_ambiguous and not any_unique,
            "no_firmware_source_in_repo": _no_firmware_in_repo(),
            "serial_not_opened": True,
            "no_flash_performed": True,
            "no_rf_transmission": True,
        },
        "claim_boundary": {
            "allowed_now": [
                "Board ports listed (read-only).",
                "FQBN ambiguity flagged as an upload gate.",
            ],
            "forbidden_now": [
                "completed HIL validation",
                "hardware validation complete",
                "localization accuracy proven",
            ],
        },
        "next_actions": [
            "Operator selects exact FQBN if ambiguous (e.g. STMicroelectronics:stm32:Nucleo_64 with board part number).",
            "Provide/locate LR1121 TX-disabled firmware source before any compile/upload.",
            "Only then compile; upload only with unique FQBN + clear port + operator OK.",
        ],
    }


def _no_firmware_in_repo() -> bool:
    for pat in ("*.ino", "*.hex", "*.bin", "*.elf"):
        for p in ROOT.rglob(pat):
            if ".git" not in p.parts:
                return False
    return True


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "h0_board_discovery.json"
    md_path = out_dir / "h0_board_discovery.md"

    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# H0 Board Discovery (inspection-only)",
        "",
        "Read-only `arduino-cli board list`. No serial open, no flash, no transmission.",
        "Does not claim HIL/OTA/hardware validation.",
        "",
        f"- arduino_cli_present: {report['arduino_cli_present']}",
        f"- fqbn_ambiguous_detected: {report['fqbn_ambiguous_detected']}",
        f"- upload_gate: {report['upload_gate']}",
        "",
        "## Detected Ports",
        "",
    ]
    if report["detected_ports"]:
        for p in report["detected_ports"]:
            md.append(f"- {p['address']} ({p['protocol']}): candidates={p['candidate_fqbns']} ambiguous={p['fqbn_ambiguous']}")
    else:
        md.append("- none (no hardware or arduino-cli unavailable)")
    md += ["", "## Stop Conditions", ""]
    for k, v in report["stop_conditions"].items():
        md.append(f"- {k}: {v}")
    md += ["", "## Next Actions", ""] + [f"- {c}" for c in report["next_actions"]]
    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"upload_gate: {report['upload_gate']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    write_outputs(build_report(), args.output_dir)


if __name__ == "__main__":
    main()
