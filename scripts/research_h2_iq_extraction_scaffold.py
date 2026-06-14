#!/usr/bin/env python3
"""H2: IQ feature-extraction scaffold (software-only, no hardware).

Defines the contract for turning a captured IQ file (SigMF) into per-packet
Doppler/CFO/delay observations. It does NOT capture, does NOT transmit, and does
NOT require hardware. If a run directory is given, it reports whether the
expected IQ + metadata files exist; otherwise it emits the pipeline contract and
marks extraction status pending.

Read-only with respect to paper/docs/README. Does not claim HIL/OTA/hardware
validation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_h2_iq_extraction_scaffold"

EXTRACTED_OBS_HEADER = (
    "packet_index,timestamp_s,est_doppler_hz,est_cfo_hz,est_delay_s,snr_db,quality_flag"
)

PIPELINE_STAGES = [
    {"stage": "load_sigmf", "detail": "Read capture_IQ.sigmf-meta + capture_IQ.sigmf-data; validate sample_rate/center_freq."},
    {"stage": "packet_segmentation", "detail": "Align IQ to tx_log.csv packet windows (packet_index, timestamp_ms)."},
    {"stage": "coarse_doppler_estimate", "detail": "Per-packet coarse frequency offset via FFT peak / phase slope."},
    {"stage": "cfo_drift_separation", "detail": "Separate oscillator CFO/drift from geometry Doppler using nuisance model A."},
    {"stage": "delay_estimate", "detail": "Optional matched-filter / correlation delay vs known preamble."},
    {"stage": "quality_flags", "detail": "Flag low-SNR / clipped / dropped packets."},
    {"stage": "write_observations", "detail": "Emit extracted_observations.csv with the defined header."},
]


def scan_run_dir(run_dir: Path | None) -> dict[str, Any]:
    if run_dir is None:
        return {"run_dir": None, "status": "no_run_dir_provided"}
    files = {
        "metadata.json": (run_dir / "metadata.json").exists(),
        "tx_log.csv": (run_dir / "tx_log.csv").exists(),
        "serial_tx_log.txt": (run_dir / "serial_tx_log.txt").exists(),
        "capture_IQ.sigmf-meta": (run_dir / "capture_IQ.sigmf-meta").exists(),
        "capture_IQ.sigmf-data": (run_dir / "capture_IQ.sigmf-data").exists(),
        "controlled_capture.sc16": (run_dir / "controlled_capture.sc16").exists(),
        "noise_floor_capture.sc16": (run_dir / "noise_floor_capture.sc16").exists(),
    }
    # IQ available either as a SigMF pair or a raw .sc16 capture (H1/H1C output).
    sigmf_present = files["capture_IQ.sigmf-meta"] and files["capture_IQ.sigmf-data"]
    sc16_present = files["controlled_capture.sc16"] or files["noise_floor_capture.sc16"]
    iq_present = sigmf_present or sc16_present
    return {
        "run_dir": str(run_dir),
        "files_present": files,
        "sigmf_present": sigmf_present,
        "sc16_present": sc16_present,
        "iq_present": iq_present,
        "status": "ready_for_extraction" if iq_present else "pending_capture",
    }


def emit_extraction_stub(run_dir: Path) -> dict[str, Any]:
    """Write a contract-shaped (empty) extracted_observations.csv + analysis stub.

    No real estimator is run yet; rows are intentionally empty until a
    vendor/bench-reviewed extractor is implemented. Keeps claims conservative.
    """
    obs = run_dir / "extracted_observations.csv"
    obs.write_text(EXTRACTED_OBS_HEADER + "\n")
    analysis = {
        "extraction_attempted": True,
        "rows_written": 0,
        "packet_detected": False,
        "feature_extraction_complete": False,
        "hil_validation_complete": False,
        "hardware_validation_complete": False,
        "note": "Extraction contract emitted; estimator not yet implemented (no rows).",
    }
    (run_dir / "analysis_summary.json").write_text(json.dumps(analysis, indent=2))
    return {"emitted": True, "extracted_observations": str(obs)}


def build_report(run_dir: Path | None) -> dict[str, Any]:
    scan = scan_run_dir(run_dir)
    return {
        "metadata": {
            "phase": "H2",
            "generated_by": "research_h2_iq_extraction_scaffold.py",
            "source_files_modified": False,
            "mode": "software_only_scaffold",
            "hardware_validation_complete": False,
            "hil_validation_complete": False,
            "ota_validation_complete": False,
            "localization_accuracy_proven": False,
        },
        "pipeline_stages": PIPELINE_STAGES,
        "input_contract": {
            "required": ["capture_IQ.sigmf-meta", "capture_IQ.sigmf-data", "tx_log.csv", "metadata.json"],
            "sigmf_meta_fields": ["core:sample_rate", "core:frequency", "core:datatype", "core:version"],
        },
        "output_contract": {
            "file": "extracted_observations.csv",
            "header": EXTRACTED_OBS_HEADER,
            "one_row_per": "packet",
        },
        "run_scan": scan,
        "extraction_status": scan.get("status", "pending_capture"),
        "claim_boundary": {
            "allowed_now": [
                "IQ extraction contract/pipeline defined (software-only).",
                "Run-directory readiness reported (no capture performed).",
            ],
            "forbidden_now": [
                "real satellite capture validated",
                "completed HIL validation",
                "localization accuracy proven",
            ],
        },
        "next_actions": [
            "After approved conducted/shielded capture, place capture_IQ.sigmf-* in the run dir.",
            "Re-run with --run-dir to confirm extraction readiness.",
            "Implement estimators behind this contract only against captured/synthetic IQ.",
        ],
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "h2_iq_extraction_scaffold.json"
    md_path = out_dir / "h2_iq_extraction_scaffold.md"

    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# H2 IQ Feature-Extraction Scaffold (software-only)",
        "",
        "Defines the IQ -> per-packet observation contract. No capture, no transmit, no hardware.",
        "Does not claim HIL/OTA/hardware validation.",
        "",
        f"- extraction_status: {report['extraction_status']}",
        "",
        "## Pipeline Stages",
        "",
    ]
    for s in report["pipeline_stages"]:
        md.append(f"- {s['stage']}: {s['detail']}")
    md += ["", "## Output Contract", "", f"- file: {report['output_contract']['file']}",
           f"- header: `{report['output_contract']['header']}`"]
    md += ["", "## Run Scan", ""]
    for k, v in report["run_scan"].items():
        md.append(f"- {k}: {v}")
    md += ["", "## Claim Boundary — Allowed Now", ""] + [f"- {c}" for c in report["claim_boundary"]["allowed_now"]]
    md += ["", "## Claim Boundary — Forbidden Now", ""] + [f"- {c}" for c in report["claim_boundary"]["forbidden_now"]]
    md += ["", "## Next Actions", ""] + [f"- {c}" for c in report["next_actions"]]
    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"extraction_status: {report['extraction_status']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--emit", action="store_true",
                        help="If run-dir IQ is present, write contract-shaped extracted_observations.csv + analysis stub.")
    args = parser.parse_args()
    report = build_report(args.run_dir)
    if args.emit and args.run_dir is not None and report["run_scan"].get("iq_present"):
        report["emit_result"] = emit_extraction_stub(args.run_dir)
    write_outputs(report, args.output_dir)


if __name__ == "__main__":
    main()
