#!/usr/bin/env python3
"""H1: USRP B210 receive-only capture readiness.

Prepares (and optionally exercises, receive-only) the USRP B210 path for future
controlled conducted/shielded capture. It NEVER transmits and NEVER triggers any
LR1121 packet TX. Default mode is a dry run: it only writes a readiness report
and (if --run-id given) a metadata-only run directory.

Gated actions:
  --allow-probe              run uhd_find_devices / uhd_usrp_probe (read-only)
  --allow-short-rx-capture   run a short RECEIVE-ONLY capture (no TX)

Read-only w.r.t. paper/docs/README. Does not claim HIL/OTA/hardware validation.
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
OUT = ROOT / "experiments/results/research_usrp_b210_rx_readiness"
DEFAULT_OUTPUT_ROOT = ROOT / "data/hil_runs"

LR1121_GETVERSION_RAW = "07 22 03 01 03"
UHD_COMMANDS = ["uhd_find_devices", "uhd_usrp_probe", "uhd_config_info"]
RX_CAPTURE_TOOL = "rx_samples_to_file"  # standard UHD receive-only example

# UHD ships rx_samples_to_file as an "example" binary, often not on PATH.
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


def uhd_availability() -> dict[str, bool]:
    avail = {c: shutil.which(c) is not None for c in UHD_COMMANDS}
    avail[RX_CAPTURE_TOOL] = resolve_rx_tool() is not None
    return avail


def run_probe(run_dir: Path | None) -> dict[str, Any]:
    """Read-only USRP discovery. Never transmits."""
    if shutil.which("uhd_find_devices") is None:
        return {"usrp_probe_executed": False, "usrp_detected": False, "probe_text": "uhd_find_devices_not_installed"}
    try:
        find = subprocess.run(["uhd_find_devices"], text=True, capture_output=True, timeout=30, check=False)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"usrp_probe_executed": True, "usrp_detected": False, "probe_text": f"probe_error:{exc}"}

    text = (find.stdout or "") + "\n" + (find.stderr or "")
    detected = ("B210" in text) or ("type: b200" in text.lower()) or ("found" in text.lower() and "no devices" not in text.lower())
    # Deeper read-only probe if a device is present.
    probe_text = text
    if detected and shutil.which("uhd_usrp_probe") is not None:
        try:
            probe = subprocess.run(["uhd_usrp_probe"], text=True, capture_output=True, timeout=60, check=False)
            probe_text += "\n==== uhd_usrp_probe ====\n" + (probe.stdout or "") + (probe.stderr or "")
        except (subprocess.TimeoutExpired, OSError) as exc:
            probe_text += f"\nuhd_usrp_probe_error:{exc}"

    if run_dir is not None:
        (run_dir / "usrp_probe.txt").write_text(probe_text)
    return {"usrp_probe_executed": True, "usrp_detected": bool(detected), "probe_text": probe_text}


def build_rx_command(freq: float, rate: float, gain: float, duration: float, out_file: Path) -> list[str]:
    # RECEIVE-ONLY. rx_samples_to_file only receives; it cannot transmit.
    return [
        resolve_rx_tool() or RX_CAPTURE_TOOL,
        "--freq", str(freq),
        "--rate", str(rate),
        "--gain", str(gain),
        "--duration", str(duration),
        "--type", "short",
        "--file", str(out_file),
    ]


def run_rx_capture(run_dir: Path, freq: float, rate: float, gain: float, duration: float) -> dict[str, Any]:
    """Short RECEIVE-ONLY capture. No transmission whatsoever."""
    out_file = run_dir / "noise_floor_capture.sc16"
    cmd = build_rx_command(freq, rate, gain, duration, out_file)
    (run_dir / "rx_command.txt").write_text(" ".join(cmd) + "\n")

    if resolve_rx_tool() is None:
        return {
            "rx_capture_executed": False,
            "capture_present": False,
            "capture_file_path": None,
            "reason": f"{RX_CAPTURE_TOOL}_not_installed",
        }
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=int(duration) + 60, check=False)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"rx_capture_executed": True, "capture_present": False, "capture_file_path": None, "reason": f"capture_error:{exc}"}

    present = out_file.exists() and out_file.stat().st_size > 0
    sample_count = None
    if present:
        # sc16 = 2 int16 per complex sample = 4 bytes/sample.
        sample_count = out_file.stat().st_size // 4
    (run_dir / "rx_capture_stdout.txt").write_text((proc.stdout or "") + "\n" + (proc.stderr or ""))
    return {
        "rx_capture_executed": True,
        "capture_present": present,
        "capture_file_path": str(out_file) if present else None,
        "sample_count": sample_count,
    }


def build_metadata(run_id: str, freq, rate, gain, duration, capture_type: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "hardware_stage": "H1_rx_only_readiness",
        "lr1121_device_confirmed": True,
        "lr1121_getversion_raw": LR1121_GETVERSION_RAW,
        "lr1121_tx_enabled": False,
        "usrp_role": "rx_only",
        "center_frequency_hz": freq,
        "sample_rate_sps": rate,
        "gain_db": gain,
        "duration_s": duration,
        "capture_type": capture_type,
        "no_packet_tx": True,
        "conducted_or_shielded": True,
        "ota_validation_complete": False,
        "hil_validation_complete": False,
        "hardware_validation_complete": False,
    }


def build_capture_manifest() -> dict[str, Any]:
    return {
        "expected_files": [
            "metadata.json", "capture_manifest.json", "rx_command.txt",
            "usrp_probe.txt", "noise_floor_capture.sc16", "analysis_summary.json",
        ],
        "rx_only": True,
        "no_packet_tx": True,
        "iq_capture_required_later": True,
        "claim_boundary": {
            "packet_detected": False,
            "feature_extraction_complete": False,
            "hil_validation_complete": False,
            "hardware_validation_complete": False,
            "localization_accuracy_proven": False,
        },
    }


def build_analysis(capture_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "capture_present": capture_info.get("capture_present", False),
        "sample_count": capture_info.get("sample_count"),
        "packet_detected": False,
        "feature_extraction_complete": False,
        "hil_validation_complete": False,
        "hardware_validation_complete": False,
        "note": "RX-only noise/dummy capture; no packet decoding attempted.",
    }


def build_report(args, probe_info, capture_info, freq, rate, gain, duration, run_dir) -> dict[str, Any]:
    capture_executed = capture_info.get("rx_capture_executed", False)
    next_gate = "H1B_controlled_conducted_packet_capture_planning"
    return {
        "metadata": {
            "phase": "H1",
            "generated_by": "research_usrp_b210_rx_readiness.py",
            "source_files_modified": False,
            "mode": "dry_run" if args.dry_run else "active_rx_only",
            "uhd_availability": uhd_availability(),
        },
        "usrp_role": "rx_only",
        "lr1121_role": "tx_only_but_tx_disabled",
        "lr1121_init_verified": True,
        "packet_transmission_executed": False,
        "rf_transmission_enabled": False,
        "usrp_probe_executed": probe_info.get("usrp_probe_executed", False),
        "usrp_detected": probe_info.get("usrp_detected", False),
        "rx_capture_executed": capture_executed,
        "rx_capture_duration_s": duration if capture_executed else None,
        "center_frequency_hz": freq,
        "sample_rate_sps": rate,
        "gain_db": gain,
        "capture_file_path": capture_info.get("capture_file_path"),
        "capture_metadata_path": str(run_dir / "metadata.json") if run_dir else None,
        "capture_analysis_status": (
            "rx_only_noise_capture_present" if capture_info.get("capture_present")
            else ("dry_run" if args.dry_run else "no_capture")
        ),
        "hardware_validation_complete": False,
        "hil_validation_complete": False,
        "ota_validation_complete": False,
        "localization_accuracy_proven": False,
        "rx_command_preview": " ".join(build_rx_command(freq, rate, gain, duration, Path("<run_dir>/noise_floor_capture.sc16"))),
        "next_gate": next_gate,
        "notes": [
            "USRP is RECEIVE-ONLY here; rx_samples_to_file cannot transmit.",
            "LR1121 remains TX-disabled; no packet TX is performed.",
            "RX-only noise/dummy capture is NOT HIL/OTA/hardware validation.",
            "Use a legal receive-only center frequency; do not transmit.",
        ],
    }


def write_run_dir(run_dir: Path, run_id, freq, rate, gain, duration, capture_type, capture_info) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metadata.json").write_text(json.dumps(build_metadata(run_id, freq, rate, gain, duration, capture_type), indent=2))
    (run_dir / "capture_manifest.json").write_text(json.dumps(build_capture_manifest(), indent=2))
    (run_dir / "analysis_summary.json").write_text(json.dumps(build_analysis(capture_info), indent=2))


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "usrp_b210_rx_readiness.json"
    md_path = out_dir / "usrp_b210_rx_readiness.md"
    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# H1 USRP B210 Rx-only Capture Readiness",
        "",
        "Receive-only USRP readiness. NEVER transmits; LR1121 stays TX-disabled.",
        "Does not claim HIL/OTA/hardware validation.",
        "",
        f"- mode: {report['metadata']['mode']}",
        f"- usrp_role: {report['usrp_role']}",
        f"- lr1121_role: {report['lr1121_role']}",
        f"- lr1121_init_verified: {report['lr1121_init_verified']}",
        f"- packet_transmission_executed: {report['packet_transmission_executed']}",
        f"- usrp_probe_executed: {report['usrp_probe_executed']}",
        f"- usrp_detected: {report['usrp_detected']}",
        f"- rx_capture_executed: {report['rx_capture_executed']}",
        f"- capture_file_path: {report['capture_file_path']}",
        f"- capture_metadata_path: {report['capture_metadata_path']}",
        f"- capture_analysis_status: {report['capture_analysis_status']}",
        f"- next_gate: {report['next_gate']}",
        "",
        "## Claim Flags (all false)",
        "",
        f"- rf_transmission_enabled: {report['rf_transmission_enabled']}",
        f"- hardware_validation_complete: {report['hardware_validation_complete']}",
        f"- hil_validation_complete: {report['hil_validation_complete']}",
        f"- ota_validation_complete: {report['ota_validation_complete']}",
        f"- localization_accuracy_proven: {report['localization_accuracy_proven']}",
        "",
        "## RX Command Preview (receive-only)",
        "",
        f"`{report['rx_command_preview']}`",
        "",
        "## UHD Availability",
        "",
    ]
    for k, v in report["metadata"]["uhd_availability"].items():
        md.append(f"- {k}: {'found' if v else 'missing'}")
    md += ["", "## Notes", ""] + [f"- {n}" for n in report["notes"]]
    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"usrp_detected: {report['usrp_detected']} | rx_capture_executed: {report['rx_capture_executed']} | next_gate: {report['next_gate']}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", default=None,
                   help="Safe default: no hardware. Implied unless --allow-probe/--allow-short-rx-capture.")
    p.add_argument("--run-id", default=None)
    p.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    p.add_argument("--output-dir", type=Path, default=OUT)
    p.add_argument("--allow-probe", action="store_true")
    p.add_argument("--allow-short-rx-capture", action="store_true")
    p.add_argument("--center-frequency-hz", type=float, default=915e6)
    p.add_argument("--sample-rate-sps", type=float, default=1e6)
    p.add_argument("--duration-s", type=float, default=1.0)
    p.add_argument("--gain-db", type=float, default=20.0)
    args = p.parse_args()

    # dry_run defaults true unless an explicit hardware action is allowed.
    if args.dry_run is None:
        args.dry_run = not (args.allow_probe or args.allow_short_rx_capture)

    freq, rate, gain, duration = args.center_frequency_hz, args.sample_rate_sps, args.gain_db, args.duration_s

    run_dir = (args.output_root / args.run_id) if args.run_id else None
    capture_type = "rx_only_noise_or_dummy"

    probe_info: dict[str, Any] = {"usrp_probe_executed": False, "usrp_detected": False}
    capture_info: dict[str, Any] = {"rx_capture_executed": False, "capture_present": False, "capture_file_path": None}

    if run_dir is not None:
        run_dir.mkdir(parents=True, exist_ok=True)

    if args.allow_probe and not args.dry_run:
        probe_info = run_probe(run_dir)

    if args.allow_short_rx_capture and not args.dry_run:
        if run_dir is None:
            raise SystemExit("--allow-short-rx-capture requires --run-id")
        # Print exact command first.
        cmd = build_rx_command(freq, rate, gain, duration, run_dir / "noise_floor_capture.sc16")
        print("RX-ONLY capture command:", " ".join(cmd))
        capture_info = run_rx_capture(run_dir, freq, rate, gain, duration)

    if run_dir is not None:
        write_run_dir(run_dir, args.run_id, freq, rate, gain, duration, capture_type, capture_info)

    report = build_report(args, probe_info, capture_info, freq, rate, gain, duration, run_dir)
    write_outputs(report, args.output_dir)


if __name__ == "__main__":
    main()
