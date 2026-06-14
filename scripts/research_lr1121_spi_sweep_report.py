#!/usr/bin/env python3
"""H0.5B: LR1121 read-only SPI pin-map/protocol sweep report.

Documents the read-only SPI diagnostic sweep (candidate pin maps x SPI settings
x command framing variants) and, if a serial sweep log is provided, parses the
RESULT lines to pick the best (plausible) candidate. It does NOT compile, flash,
open serial, or transmit. The firmware sweep itself is READ-ONLY (no TX/send).

Read-only w.r.t. paper/docs/README. Does not claim HIL/OTA/hardware validation.
SPI_PROBE_PLAUSIBLE only means a chip-like response was seen; it does NOT mean
LR1121 init/validation is confirmed.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_lr1121_spi_sweep_report"

FIRMWARE_REL = "firmware/lr1121_tx_disabled_init/lr1121_tx_disabled_init.ino"
BOARD = "NUCLEO_L476RG"
PORT = "/dev/cu.usbmodem1303"
FQBN = "STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_L476RG"

CANDIDATE_PIN_MAPS = {
    "map_current": {"NSS": "D10", "BUSY": "D8", "RESET": "D9", "DIO": "D3"},
    "map_alt_shield": {"NSS": "D7", "BUSY": "D3", "RESET": "A0", "DIO": "D5"},
    "map_alt_reset_d9": {"NSS": "D7", "BUSY": "D3", "RESET": "D9", "DIO": "D5"},
    "map_alt_busy_d8": {"NSS": "D7", "BUSY": "D8", "RESET": "A0", "DIO": "D5"},
    "map_cs_d10_busy_d3_reset_a0": {"NSS": "D10", "BUSY": "D3", "RESET": "A0", "DIO": "D5"},
}
SPI_SETTINGS = [
    {"mode": 0, "hz": 125000},
    {"mode": 0, "hz": 500000},
    {"mode": 0, "hz": 1000000},
    {"mode": 0, "hz": 4000000},
    {"mode": 3, "hz": 500000},
]
COMMAND_VARIANTS = ["variant_raw_0101", "variant_status_prefixed", "variant_dummy_before_read"]

# Active radio TX/send API call tokens that must NOT appear in firmware.
FORBIDDEN_TX_TOKENS = ["startTransmit", "beginTransmit", "setTx(", "SetTx(", ".transmit(", "sendPacket", "startTx"]
EXPECTED_PRESENT = [
    "TX_DEFAULT_DISABLED",
    "RF_TRANSMISSION_ENABLED",
    "PACKET_TRANSMISSION_EXECUTED",
    "HIL_VALIDATION_COMPLETE",
    "TX command blocked in this firmware build",
    "SPI_PROBE_PLAUSIBLE",
]

PLAUSIBLE_SCORES = {"changing_nonzero", "repeated_nonzero"}


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


def parse_sweep_log(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "sweep_log": None,
            "result_count": 0,
            "score_counts": {},
            "best_candidate": None,
            "best_response_hex": None,
            "spi_probe_plausible": False,
        }
    text = path.read_text(errors="ignore")
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.startswith("RESULT,"):
            continue
        parts = line.split(",")
        # RESULT,map,spi_mode,spi_hz,busy_before,busy_after,variant,response_hex,score,interpretation
        if len(parts) < 10:
            continue
        rows.append({
            "map": parts[1],
            "spi_mode": parts[2],
            "spi_hz": parts[3],
            "busy_before": parts[4],
            "busy_after": parts[5],
            "variant": parts[6],
            "response_hex": parts[7],
            "score": parts[8],
            "interpretation": parts[9],
        })

    score_counts: dict[str, int] = {}
    for r in rows:
        score_counts[r["score"]] = score_counts.get(r["score"], 0) + 1

    # Best: prefer changing_nonzero, then repeated_nonzero. Take the first such.
    best = None
    for want in ("changing_nonzero", "repeated_nonzero"):
        for r in rows:
            if r["score"] == want:
                best = r
                break
        if best:
            break

    plausible_flag = re.search(r"SPI_PROBE_PLAUSIBLE=(\w+)", text)
    spi_probe_plausible = (plausible_flag.group(1) == "true") if plausible_flag else bool(best)

    return {
        "sweep_log": str(path),
        "result_count": len(rows),
        "score_counts": score_counts,
        "best_candidate": best["map"] if best else None,
        "best_candidate_detail": best,
        "best_response_hex": best["response_hex"] if best else None,
        "spi_probe_plausible": spi_probe_plausible,
    }


def determine_next_gate(parsed: dict[str, Any]) -> str:
    counts = parsed["score_counts"]
    if parsed["spi_probe_plausible"] and parsed["best_candidate"]:
        return "plausible_response_implement_vendor_confirmed_getversion_parser"
    if counts.get("all_zero", 0) and not counts.get("all_ff", 0):
        return "all_zero_inspect_power_wiring_miso_nss"
    if counts.get("all_ff", 0) and not counts.get("changing_nonzero", 0):
        return "all_ff_inspect_cs_miso_pullup_floating_wiring"
    return "no_log_or_inconclusive_rerun_sweep_with_hardware"


def build_report(sweep_log: Path | None) -> dict[str, Any]:
    scan = firmware_safety_scan()
    parsed = parse_sweep_log(sweep_log)
    # Conservative: a plausible SPI response does NOT confirm LR1121 init.
    lr1121_init_verified = False
    return {
        "metadata": {
            "phase": "H0.5B",
            "generated_by": "research_lr1121_spi_sweep_report.py",
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
        "previous_result": "fail_no_plausible_response_all_zero",
        "candidate_pin_maps": CANDIDATE_PIN_MAPS,
        "spi_settings": SPI_SETTINGS,
        "command_variants": COMMAND_VARIANTS,
        "best_candidate": parsed["best_candidate"],
        "best_candidate_detail": parsed.get("best_candidate_detail"),
        "best_response_hex": parsed["best_response_hex"],
        "score_counts": parsed["score_counts"],
        "result_count": parsed["result_count"],
        "spi_probe_plausible": parsed["spi_probe_plausible"],
        "lr1121_init_verified": lr1121_init_verified,
        "rf_transmission_enabled": False,
        "packet_transmission_executed": False,
        "hardware_validation_complete": False,
        "hil_validation_complete": False,
        "ota_validation_complete": False,
        "firmware_safety_scan": scan,
        "firmware_tx_safe_by_static_scan": (
            scan.get("firmware_present", False)
            and scan.get("all_expected_markers_present", False)
            and scan.get("no_forbidden_tx_tokens", False)
        ),
        "next_gate": determine_next_gate(parsed),
        "notes": [
            "Sweep is READ-ONLY (LR1121 GetVersion opcode only); no TX/send API is invoked.",
            "SPI_PROBE_PLAUSIBLE=true means a chip-like response was observed, NOT that "
            "LR1121 init/validation is confirmed.",
            "all_zero rows indicate power/wiring/MISO issues; all_ff rows indicate floating "
            "MISO or CS-not-selected on that candidate map.",
            "Do not advance to H1 conducted capture until a vendor-confirmed GetVersion parse "
            "validates the response.",
        ],
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lr1121_spi_sweep_report.json"
    md_path = out_dir / "lr1121_spi_sweep_report.md"

    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# H0.5B LR1121 Read-only SPI Sweep Report",
        "",
        "Documents the read-only SPI pin-map/protocol sweep. No flash/serial/transmit here.",
        "Sweep firmware is READ-ONLY; does not claim HIL/OTA/hardware validation.",
        "",
        f"- board: {report['board']}",
        f"- port: {report['port']}",
        f"- fqbn: {report['fqbn']}",
        f"- previous_result: {report['previous_result']}",
        f"- result_count: {report['result_count']}",
        f"- score_counts: {report['score_counts']}",
        f"- best_candidate: {report['best_candidate']}",
        f"- best_response_hex: {report['best_response_hex']}",
        f"- spi_probe_plausible: {report['spi_probe_plausible']}",
        f"- lr1121_init_verified: {report['lr1121_init_verified']}",
        f"- firmware_tx_safe_by_static_scan: {report['firmware_tx_safe_by_static_scan']}",
        f"- next_gate: {report['next_gate']}",
        "",
        "## Candidate Pin Maps",
        "",
    ]
    for name, pins in report["candidate_pin_maps"].items():
        md.append(f"- {name}: {pins}")
    md += ["", "## SPI Settings", ""]
    for s in report["spi_settings"]:
        md.append(f"- mode {s['mode']}, {s['hz']} Hz")
    md += ["", "## Command Variants", ""] + [f"- {v}" for v in report["command_variants"]]
    if report.get("best_candidate_detail"):
        md += ["", "## Best Candidate Detail", ""]
        for k, v in report["best_candidate_detail"].items():
            md.append(f"- {k}: {v}")
    md += ["", "## Firmware Safety Scan", ""]
    for k, v in report["firmware_safety_scan"].items():
        md.append(f"- {k}: {v}")
    md += ["", "## Notes", ""] + [f"- {n}" for n in report["notes"]]
    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"best_candidate: {report['best_candidate']} | plausible: {report['spi_probe_plausible']} | next_gate: {report['next_gate']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep-log", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    write_outputs(build_report(args.sweep_log), args.output_dir)


if __name__ == "__main__":
    main()
