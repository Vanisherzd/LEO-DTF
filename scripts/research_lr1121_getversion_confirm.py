#!/usr/bin/env python3
"""H0.5C: LR1121 GetVersion confirmation report (read-only, locked pin map).

Documents the locked LR1121 pin map and the vendor-confirmed GetVersion result.
If a serial boot log is provided, parses the GetVersion raw/decoded fields and
the init-verified flag. It does NOT compile, flash, open serial, or transmit.

The firmware GetVersion path is READ-ONLY and its framing is confirmed against
the RadioLib LR11x0 driver (GET_VERSION=0x0101; reply hw,device,major,minor;
DEVICE_LR1121=0x03). lr1121_init_verified is only true when parser_confidence is
vendor_confirmed AND decoded device==0x03.

Read-only w.r.t. paper/docs/README. Does not claim HIL/OTA/hardware validation.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_lr1121_getversion_confirm"

FIRMWARE_REL = "firmware/lr1121_tx_disabled_init/lr1121_tx_disabled_init.ino"
BOARD = "NUCLEO_L476RG"
PORT = "/dev/cu.usbmodem1303"
FQBN = "STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_L476RG"

LOCKED_PIN_MAP = {"nss": "D7", "busy": "D3", "reset": "D9", "dio": "D5", "spi_mode": 0}
LR_DEVICE_LR1121 = 0x03

FORBIDDEN_TX_TOKENS = ["startTransmit", "beginTransmit", "setTx(", "SetTx(", ".transmit(", "sendPacket", "startTx"]
EXPECTED_PRESENT = [
    "TX_DEFAULT_DISABLED",
    "RF_TRANSMISSION_ENABLED",
    "PACKET_TRANSMISSION_EXECUTED",
    "HIL_VALIDATION_COMPLETE",
    "TX command blocked in this firmware build",
    "LR1121_GETVERSION_RAW",
    "LR1121_INIT_VERIFIED",
]


def firmware_safety_scan() -> dict[str, Any]:
    fw = ROOT / FIRMWARE_REL
    if not fw.exists():
        return {"firmware_present": False}
    text = fw.read_text(errors="ignore")
    present = {tok: (tok in text) for tok in EXPECTED_PRESENT}
    forbidden = {tok: (tok in text) for tok in FORBIDDEN_TX_TOKENS}
    # Verify locked pin constants in source.
    nss = re.search(r"PIN_LR_NSS\s*=\s*(D\d+|A\d+)", text)
    busy = re.search(r"PIN_LR_BUSY\s*=\s*(D\d+|A\d+)", text)
    reset = re.search(r"PIN_LR_RESET\s*=\s*(D\d+|A\d+)", text)
    dio = re.search(r"PIN_LR_DIO\s*=\s*(D\d+|A\d+)", text)
    locked = {
        "nss": nss.group(1) if nss else None,
        "busy": busy.group(1) if busy else None,
        "reset": reset.group(1) if reset else None,
        "dio": dio.group(1) if dio else None,
    }
    pin_map_locked = (
        locked["nss"] == "D7" and locked["busy"] == "D3"
        and locked["reset"] == "D9" and locked["dio"] == "D5"
    )
    return {
        "firmware_present": True,
        "expected_markers_present": present,
        "all_expected_markers_present": all(present.values()),
        "forbidden_tx_tokens_found": {k: v for k, v in forbidden.items() if v},
        "no_forbidden_tx_tokens": not any(forbidden.values()),
        "locked_pins_in_source": locked,
        "pin_map_locked": pin_map_locked,
    }


def parse_boot_log(path: Path | None) -> dict[str, Any]:
    default = {
        "boot_log": None,
        "raw_response": None,
        "decoded_response": None,
        "parser_confidence": "not_read_offline",
        "spi_probe_plausible": False,
        "lr1121_init_verified": False,
    }
    if path is None or not path.exists():
        return default
    text = path.read_text(errors="ignore")
    raw = re.search(r"LR1121_GETVERSION_RAW=([0-9A-Fa-f ]+)", text)
    dec = re.search(r"LR1121_GETVERSION_DECODED=([^\r\n]+)", text)
    conf = re.search(r"parser_confidence=(\w+)", text)
    plaus = re.search(r"SPI_PROBE_PLAUSIBLE=(\w+)", text)
    verified = re.search(r"LR1121_INIT_VERIFIED=(\w+)", text)

    decoded = None
    if dec:
        decoded = {}
        for kv in dec.group(1).split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                decoded[k.strip()] = v.strip()

    return {
        "boot_log": str(path),
        "raw_response": raw.group(1).strip() if raw else None,
        "decoded_response": decoded,
        "parser_confidence": conf.group(1) if conf else "unverified",
        "spi_probe_plausible": (plaus.group(1) == "true") if plaus else False,
        "lr1121_init_verified": (verified.group(1) == "true") if verified else False,
    }


def build_report(boot_log: Path | None) -> dict[str, Any]:
    scan = firmware_safety_scan()
    parsed = parse_boot_log(boot_log)

    # Independent re-check: only accept verified when vendor_confirmed + device 0x03.
    device_ok = False
    if parsed["decoded_response"] and "device" in parsed["decoded_response"]:
        try:
            device_ok = int(parsed["decoded_response"]["device"], 16) == LR_DEVICE_LR1121
        except (ValueError, TypeError):
            device_ok = False
    lr1121_init_verified = bool(
        parsed["lr1121_init_verified"]
        and parsed["parser_confidence"] == "vendor_confirmed"
        and device_ok
    )

    next_gate = (
        "lr1121_confirmed_proceed_to_h1_conducted_capture_readiness_review"
        if lr1121_init_verified
        else "rerun_getversion_with_hardware_or_confirm_framing"
    )

    return {
        "metadata": {
            "phase": "H0.5C",
            "generated_by": "research_lr1121_getversion_confirm.py",
            "source_files_modified": False,
            "mode": "documentation_only_no_flash_no_serial",
            "vendor_framing_source": "RadioLib LR11x0 driver (GET_VERSION=0x0101, device LR1121=0x03)",
            "hardware_validation_complete": False,
            "hil_validation_complete": False,
            "ota_validation_complete": False,
            "localization_accuracy_proven": False,
        },
        "board": BOARD,
        "port": PORT,
        "fqbn": FQBN,
        "pin_map_locked": scan.get("pin_map_locked", False),
        "nss": LOCKED_PIN_MAP["nss"],
        "busy": LOCKED_PIN_MAP["busy"],
        "reset": LOCKED_PIN_MAP["reset"],
        "dio": LOCKED_PIN_MAP["dio"],
        "spi_mode": LOCKED_PIN_MAP["spi_mode"],
        "raw_response": parsed["raw_response"],
        "decoded_response": parsed["decoded_response"],
        "parser_confidence": parsed["parser_confidence"],
        "spi_probe_plausible": parsed["spi_probe_plausible"],
        "lr1121_init_verified": lr1121_init_verified,
        "rf_transmission_enabled": False,
        "packet_transmission_executed": False,
        "hardware_validation_complete": False,
        "hil_validation_complete": False,
        "ota_validation_complete": False,
        "localization_accuracy_proven": False,
        "firmware_safety_scan": scan,
        "firmware_tx_safe_by_static_scan": (
            scan.get("firmware_present", False)
            and scan.get("all_expected_markers_present", False)
            and scan.get("no_forbidden_tx_tokens", False)
            and scan.get("pin_map_locked", False)
        ),
        "next_gate": next_gate,
        "notes": [
            "GetVersion path is READ-ONLY; no TX/send API is invoked.",
            "parser_confidence=vendor_confirmed means framing matches the RadioLib LR11x0 driver.",
            "lr1121_init_verified=true requires vendor_confirmed framing AND decoded device==0x03 (LR1121).",
            "Confirming the chip does NOT constitute HIL/OTA/hardware validation; those remain future work.",
        ],
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lr1121_getversion_confirm.json"
    md_path = out_dir / "lr1121_getversion_confirm.md"

    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# H0.5C LR1121 GetVersion Confirmation Report",
        "",
        "Documents locked pin map and vendor-confirmed read-only GetVersion result.",
        "No flash/serial/transmit here. Does not claim HIL/OTA/hardware validation.",
        "",
        f"- board: {report['board']}",
        f"- port: {report['port']}",
        f"- fqbn: {report['fqbn']}",
        f"- pin_map_locked: {report['pin_map_locked']}",
        f"- NSS={report['nss']} BUSY={report['busy']} RESET={report['reset']} DIO={report['dio']} SPI_MODE={report['spi_mode']}",
        f"- raw_response: {report['raw_response']}",
        f"- decoded_response: {report['decoded_response']}",
        f"- parser_confidence: {report['parser_confidence']}",
        f"- spi_probe_plausible: {report['spi_probe_plausible']}",
        f"- lr1121_init_verified: {report['lr1121_init_verified']}",
        f"- firmware_tx_safe_by_static_scan: {report['firmware_tx_safe_by_static_scan']}",
        f"- next_gate: {report['next_gate']}",
        "",
        "## Claim Flags (all false)",
        "",
        f"- rf_transmission_enabled: {report['rf_transmission_enabled']}",
        f"- packet_transmission_executed: {report['packet_transmission_executed']}",
        f"- hardware_validation_complete: {report['hardware_validation_complete']}",
        f"- hil_validation_complete: {report['hil_validation_complete']}",
        f"- ota_validation_complete: {report['ota_validation_complete']}",
        f"- localization_accuracy_proven: {report['localization_accuracy_proven']}",
        "",
        "## Firmware Safety Scan",
        "",
    ]
    for k, v in report["firmware_safety_scan"].items():
        md.append(f"- {k}: {v}")
    md += ["", "## Notes", ""] + [f"- {n}" for n in report["notes"]]
    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"lr1121_init_verified: {report['lr1121_init_verified']} | confidence: {report['parser_confidence']} | next_gate: {report['next_gate']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boot-log", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    write_outputs(build_report(args.boot_log), args.output_dir)


if __name__ == "__main__":
    main()
