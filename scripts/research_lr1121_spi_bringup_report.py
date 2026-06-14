#!/usr/bin/env python3
"""H0.5: LR1121 read-only SPI bring-up report.

Records the read-only LR1121 SPI probe (GetVersion) configuration and, if a
serial boot log is provided, the observed probe result. It does NOT compile,
flash, open serial, or transmit. It only documents bring-up state for review.

Read-only w.r.t. paper/docs/README. Does not claim HIL/OTA/hardware validation.
The LR1121 probe in the firmware is READ-ONLY (no TX/send API).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_lr1121_spi_bringup_report"

FIRMWARE_REL = "firmware/lr1121_tx_disabled_init/lr1121_tx_disabled_init.ino"
BOARD = "NUCLEO_L476RG"
PORT = "/dev/cu.usbmodem1303"
FQBN = "STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_L476RG"

# Pin map mirrors the firmware #defines (configurable wiring).
PIN_MAP = {
    "LR1121_NSS": "D10",
    "LR1121_BUSY": "D8",
    "LR1121_RESET": "D9",
    "LR1121_DIO": "D3",
    "SPI_MOSI": "D11",
    "SPI_MISO": "D12",
    "SPI_SCK": "D13",
}

EXPECTED_PRESENT = [
    "TX_DEFAULT_DISABLED",
    "RF_TRANSMISSION_ENABLED",
    "PACKET_TRANSMISSION_EXECUTED",
    "HIL_VALIDATION_COMPLETE",
    "TX command blocked in this firmware build",
    "LR1121_SPI_PROBE_ATTEMPTED",
]
# Active radio TX/send API call tokens that must NOT appear in the firmware.
FORBIDDEN_TX_TOKENS = ["startTransmit", "beginTransmit", "setTx(", "SetTx(", ".transmit(", "sendPacket"]


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


def parse_boot_log(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "boot_log": None,
            "spi_probe_attempted": None,
            "spi_probe_result": "not_read_offline",
            "lr1121_version_raw": None,
        }
    text = path.read_text(errors="ignore")
    attempted = re.search(r"LR1121_SPI_PROBE_ATTEMPTED=(\w+)", text)
    result = re.search(r"LR1121_SPI_PROBE_RESULT=([^\r\n]+)", text)
    raw = re.search(r"LR1121_VERSION_RAW=([0-9A-Fa-f ]+)", text)
    return {
        "boot_log": str(path),
        "spi_probe_attempted": (attempted.group(1) == "true") if attempted else None,
        "spi_probe_result": result.group(1).strip() if result else "unknown",
        "lr1121_version_raw": raw.group(1).strip() if raw else None,
    }


def build_report(boot_log: Path | None) -> dict[str, Any]:
    scan = firmware_safety_scan()
    parsed = parse_boot_log(boot_log)
    init_verified = parsed["spi_probe_result"] == "ok"
    next_gate = (
        "H1_conducted_packet_capture_only_after_readonly_spi_ok"
        if init_verified
        else "readonly_spi_probe_not_yet_ok_remain_h0_5"
    )
    return {
        "metadata": {
            "phase": "H0.5",
            "generated_by": "research_lr1121_spi_bringup_report.py",
            "source_files_modified": False,
            "mode": "documentation_only_no_flash_no_serial",
            "hardware_validation_complete": False,
            "hil_validation_complete": False,
            "ota_validation_complete": False,
            "localization_accuracy_proven": False,
        },
        "board": BOARD,
        "port": PORT,
        "fqbn": FQBN,
        "pin_map": PIN_MAP,
        "firmware_path": FIRMWARE_REL,
        "firmware_tx_default_disabled": True,
        "rf_transmission_enabled": False,
        "packet_transmission_executed": False,
        "spi_probe_attempted": parsed["spi_probe_attempted"],
        "spi_probe_result": parsed["spi_probe_result"],
        "lr1121_version_raw": parsed["lr1121_version_raw"],
        "lr1121_init_verified": init_verified,
        "hardware_validation_complete": False,
        "hil_validation_complete": False,
        "ota_validation_complete": False,
        "firmware_safety_scan": scan,
        "firmware_tx_safe_by_static_scan": (
            scan.get("firmware_present", False)
            and scan.get("all_expected_markers_present", False)
            and scan.get("no_forbidden_tx_tokens", False)
        ),
        "next_gate": next_gate,
        "notes": [
            "Probe is READ-ONLY (LR1121 GetVersion); no TX/send API is invoked.",
            "All-zero or all-0xFF version_raw indicates no plausible chip response "
            "(check NSS/SCK/MISO wiring, BUSY pin, module power) — not a transmit issue.",
            "Do not advance to H1 conducted capture until read-only SPI probe returns ok.",
        ],
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lr1121_spi_bringup_report.json"
    md_path = out_dir / "lr1121_spi_bringup_report.md"

    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# H0.5 LR1121 Read-only SPI Bring-up Report",
        "",
        "Documents the read-only LR1121 SPI probe (GetVersion). No flash/serial/transmit here.",
        "Probe firmware is READ-ONLY; does not claim HIL/OTA/hardware validation.",
        "",
        f"- board: {report['board']}",
        f"- port: {report['port']}",
        f"- fqbn: {report['fqbn']}",
        f"- firmware_tx_default_disabled: {report['firmware_tx_default_disabled']}",
        f"- rf_transmission_enabled: {report['rf_transmission_enabled']}",
        f"- spi_probe_attempted: {report['spi_probe_attempted']}",
        f"- spi_probe_result: {report['spi_probe_result']}",
        f"- lr1121_version_raw: {report['lr1121_version_raw']}",
        f"- lr1121_init_verified: {report['lr1121_init_verified']}",
        f"- firmware_tx_safe_by_static_scan: {report['firmware_tx_safe_by_static_scan']}",
        f"- next_gate: {report['next_gate']}",
        "",
        "## Pin Map",
        "",
    ]
    for k, v in report["pin_map"].items():
        md.append(f"- {k}: {v}")
    md += ["", "## Firmware Safety Scan", ""]
    for k, v in report["firmware_safety_scan"].items():
        md.append(f"- {k}: {v}")
    md += ["", "## Notes", ""] + [f"- {n}" for n in report["notes"]]
    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"spi_probe_result: {report['spi_probe_result']} | next_gate: {report['next_gate']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boot-log", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    write_outputs(build_report(args.boot_log), args.output_dir)


if __name__ == "__main__":
    main()
