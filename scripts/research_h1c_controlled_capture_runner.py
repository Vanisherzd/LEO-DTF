#!/usr/bin/env python3
"""H1C: controlled conducted capture runner (dry-run by default).

Generates the run scaffold (metadata + planned commands) for a controlled
CONDUCTED/SHIELDED capture, and can optionally execute a RECEIVE-ONLY USRP
capture and/or send gated serial commands to the controlled packet-source
firmware. Default mode is dry-run: nothing is transmitted or captured.

Gated actions (must be passed explicitly AND with --no-dry-run effect):
  --allow-usrp-capture       run a receive-only USRP capture
  --allow-serial-tx-command  send gated serial arm_tx + send_test_packet

Even with --allow-serial-tx-command, the default packet-source firmware build
performs NO RF (ENABLE_REAL_TX=0). Read-only w.r.t. paper/docs/README. Does not
claim HIL/OTA/hardware validation.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_h1c_controlled_capture_runner"
DEFAULT_OUTPUT_ROOT = ROOT / "data/hil_runs"

LR1121_GETVERSION_RAW = "07 22 03 01 03"
LR1121_PIN_MAP = {"nss": "D7", "busy": "D3", "reset": "D9", "dio": "D5", "spi_mode": 0}
USRP_SERIAL = "8000304"
SERIAL_PORT = "/dev/cu.usbmodem1303"

RX_CAPTURE_TOOL = "rx_samples_to_file"
UHD_EXAMPLE_DIRS = [
    "/opt/homebrew/lib/uhd/examples",
    "/usr/local/lib/uhd/examples",
    "/usr/lib/uhd/examples",
]


def resolve_rx_tool() -> str | None:
    found = shutil.which(RX_CAPTURE_TOOL)
    if found:
        return found
    for d in UHD_EXAMPLE_DIRS:
        cand = Path(d) / RX_CAPTURE_TOOL
        if cand.exists():
            return str(cand)
    return None


def usrp_command(freq, rate, gain, duration, out_file: Path) -> list[str]:
    return [
        resolve_rx_tool() or RX_CAPTURE_TOOL,
        "--freq", str(freq), "--rate", str(rate), "--gain", str(gain),
        "--duration", str(duration), "--type", "short", "--file", str(out_file),
    ]


def planned_serial_commands() -> list[str]:
    # Gated single-packet sequence. Default firmware build emits NO RF.
    return [
        "status",
        "getversion",
        "config",
        "arm_tx CONFIRM_CONDUCTED_TEST",
        "send_test_packet",
        "disarm_tx",
        "status",
    ]


def build_metadata(run_id, freq, rate, gain, duration, tx_executed, rx_executed) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "hardware_stage": "H1C_controlled_conducted_capture",
        "lr1121_getversion_raw": LR1121_GETVERSION_RAW,
        "lr1121_device_confirmed": True,
        "lr1121_pin_map": LR1121_PIN_MAP,
        "usrp_serial": USRP_SERIAL,
        "center_frequency_hz": freq,
        "sample_rate_sps": rate,
        "gain_db": gain,
        "duration_s": duration,
        "conducted_or_shielded": True,
        "ota_validation_complete": False,
        "hil_validation_complete": False,
        "hardware_validation_complete": False,
        "packet_transmission_executed": tx_executed,
        "rx_capture_executed": rx_executed,
        "claim_boundary": {
            "ota_validation_complete": False,
            "hil_validation_complete": False,
            "hardware_validation_complete": False,
            "localization_accuracy_proven": False,
        },
    }


def build_capture_manifest() -> dict[str, Any]:
    return {
        "expected_files": [
            "metadata.json", "capture_manifest.json", "planned_usrp_command.txt",
            "planned_serial_commands.txt", "serial_tx_log.txt", "controlled_capture.sc16",
            "extracted_observations.csv", "analysis_summary.json",
        ],
        "conducted_or_shielded": True,
        "no_ota": True,
        "default_packet_count": 1,
        "claim_boundary": {
            "hil_validation_complete": False,
            "hardware_validation_complete": False,
            "localization_accuracy_proven": False,
        },
    }


def build_analysis(rx_executed, capture_file: Path | None) -> dict[str, Any]:
    present = bool(capture_file and capture_file.exists() and capture_file.stat().st_size > 0)
    return {
        "capture_present": present,
        "sample_count": (capture_file.stat().st_size // 4) if present else None,
        "packet_detected": False,
        "feature_extraction_complete": False,
        "hil_validation_complete": False,
        "hardware_validation_complete": False,
        "note": "Controlled conducted capture scaffold; no automated packet decoding here.",
    }


def run_usrp_capture(run_dir: Path, freq, rate, gain, duration) -> dict[str, Any]:
    out_file = run_dir / "controlled_capture.sc16"
    cmd = usrp_command(freq, rate, gain, duration, out_file)
    print("RX-ONLY capture command:", " ".join(cmd))
    if resolve_rx_tool() is None:
        return {"rx_executed": False, "capture_file": None, "reason": "rx_tool_not_installed"}
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=int(duration) + 60, check=False)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"rx_executed": True, "capture_file": None, "reason": f"capture_error:{exc}"}
    (run_dir / "rx_capture_stdout.txt").write_text((proc.stdout or "") + "\n" + (proc.stderr or ""))
    return {"rx_executed": True, "capture_file": out_file if out_file.exists() else None}


def send_serial_commands(run_dir: Path) -> dict[str, Any]:
    """Send gated serial commands. Requires pyserial. Default firmware emits no RF."""
    try:
        import serial  # type: ignore
    except ImportError:
        return {"tx_commands_sent": False, "reason": "pyserial_not_installed"}
    log_lines: list[str] = []
    try:
        with serial.Serial(SERIAL_PORT, 115200, timeout=2) as s:
            for cmd in planned_serial_commands():
                s.write((cmd + "\n").encode()); s.flush()
                import time as _t; _t.sleep(0.4)
                while s.in_waiting:
                    log_lines.append(s.readline().decode("utf-8", "replace").rstrip())
    except Exception as exc:  # noqa: BLE001 - hardware I/O best-effort
        return {"tx_commands_sent": False, "reason": f"serial_error:{exc}"}
    (run_dir / "serial_tx_log.txt").write_text("\n".join(log_lines) + "\n")
    tx_executed = any("TX_EXECUTED=true" in ln for ln in log_lines)
    return {"tx_commands_sent": True, "tx_executed": tx_executed}


def build_report(args, run_dir, tx_executed, rx_executed, capture_file) -> dict[str, Any]:
    return {
        "metadata": {
            "phase": "H1C",
            "generated_by": "research_h1c_controlled_capture_runner.py",
            "source_files_modified": False,
            "mode": "dry_run" if args.dry_run else "active",
        },
        "run_dir": str(run_dir) if run_dir else None,
        "center_frequency_hz": args.center_frequency_hz,
        "sample_rate_sps": args.sample_rate_sps,
        "gain_db": args.gain_db,
        "duration_s": args.duration_s,
        "planned_usrp_command": " ".join(
            usrp_command(args.center_frequency_hz, args.sample_rate_sps, args.gain_db,
                         args.duration_s, Path("<run_dir>/controlled_capture.sc16"))
        ),
        "planned_serial_commands": planned_serial_commands(),
        "packet_transmission_executed": tx_executed,
        "rx_capture_executed": rx_executed,
        "capture_file_path": str(capture_file) if capture_file else None,
        "conducted_or_shielded": True,
        "ota_validation_complete": False,
        "hil_validation_complete": False,
        "hardware_validation_complete": False,
        "localization_accuracy_proven": False,
        "next_gate": "H1C_actual_conducted_one_packet_capture",
        "notes": [
            "Dry-run performs NO transmit and NO capture.",
            "USRP path is receive-only (rx_samples_to_file cannot transmit).",
            "Default packet-source firmware build emits NO RF (ENABLE_REAL_TX=0).",
            "Conducted/shielded only; OTA forbidden; not HIL/OTA/hardware validation.",
        ],
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "h1c_controlled_capture_runner.json").write_text(json.dumps(report, indent=2))
    md = [
        "# H1C Controlled Conducted Capture Runner",
        "",
        "Dry-run by default: no transmit, no capture. USRP receive-only.",
        "Default packet-source firmware emits no RF. Not HIL/OTA/hardware validation.",
        "",
        f"- mode: {report['metadata']['mode']}",
        f"- run_dir: {report['run_dir']}",
        f"- packet_transmission_executed: {report['packet_transmission_executed']}",
        f"- rx_capture_executed: {report['rx_capture_executed']}",
        f"- capture_file_path: {report['capture_file_path']}",
        f"- next_gate: {report['next_gate']}",
        "",
        "## Planned USRP Command (receive-only)",
        "",
        f"`{report['planned_usrp_command']}`",
        "",
        "## Planned Serial Commands (gated)",
        "",
    ]
    md += [f"- {c}" for c in report["planned_serial_commands"]]
    md += ["", "## Claim Flags (all false)", "",
           f"- ota_validation_complete: {report['ota_validation_complete']}",
           f"- hil_validation_complete: {report['hil_validation_complete']}",
           f"- hardware_validation_complete: {report['hardware_validation_complete']}",
           f"- localization_accuracy_proven: {report['localization_accuracy_proven']}"]
    md += ["", "## Notes", ""] + [f"- {n}" for n in report["notes"]]
    (out_dir / "h1c_controlled_capture_runner.md").write_text("\n".join(md) + "\n")

    print(f"Wrote {out_dir / 'h1c_controlled_capture_runner.json'}")
    print(f"mode: {report['metadata']['mode']} | tx_executed: {report['packet_transmission_executed']} | rx_executed: {report['rx_capture_executed']}")


def write_run_dir(run_dir: Path, args, tx_executed, rx_executed, capture_file) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metadata.json").write_text(json.dumps(
        build_metadata(args.run_id, args.center_frequency_hz, args.sample_rate_sps,
                       args.gain_db, args.duration_s, tx_executed, rx_executed), indent=2))
    (run_dir / "capture_manifest.json").write_text(json.dumps(build_capture_manifest(), indent=2))
    (run_dir / "planned_usrp_command.txt").write_text(" ".join(
        usrp_command(args.center_frequency_hz, args.sample_rate_sps, args.gain_db,
                     args.duration_s, run_dir / "controlled_capture.sc16")) + "\n")
    (run_dir / "planned_serial_commands.txt").write_text("\n".join(planned_serial_commands()) + "\n")
    (run_dir / "analysis_summary.json").write_text(json.dumps(build_analysis(rx_executed, capture_file), indent=2))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", default=None)
    p.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    p.add_argument("--output-dir", type=Path, default=OUT)
    p.add_argument("--center-frequency-hz", type=float, default=915e6)
    p.add_argument("--sample-rate-sps", type=float, default=1e6)
    p.add_argument("--gain-db", type=float, default=20.0)
    p.add_argument("--duration-s", type=float, default=2.0)
    p.add_argument("--dry-run", action="store_true", default=None)
    p.add_argument("--allow-usrp-capture", action="store_true")
    p.add_argument("--allow-serial-tx-command", action="store_true")
    args = p.parse_args()

    if args.dry_run is None:
        args.dry_run = not (args.allow_usrp_capture or args.allow_serial_tx_command)

    run_dir = (args.output_root / args.run_id) if args.run_id else None
    tx_executed = False
    rx_executed = False
    capture_file = None

    if run_dir is not None:
        run_dir.mkdir(parents=True, exist_ok=True)

    if not args.dry_run and args.allow_usrp_capture:
        if run_dir is None:
            raise SystemExit("--allow-usrp-capture requires --run-id")
        res = run_usrp_capture(run_dir, args.center_frequency_hz, args.sample_rate_sps, args.gain_db, args.duration_s)
        rx_executed = res.get("rx_executed", False)
        capture_file = res.get("capture_file")

    if not args.dry_run and args.allow_serial_tx_command:
        if run_dir is None:
            raise SystemExit("--allow-serial-tx-command requires --run-id")
        res = send_serial_commands(run_dir)
        tx_executed = res.get("tx_executed", False)

    if run_dir is not None:
        write_run_dir(run_dir, args, tx_executed, rx_executed, capture_file)

    write_outputs(build_report(args, run_dir, tx_executed, rx_executed, capture_file), args.output_dir)


if __name__ == "__main__":
    main()
