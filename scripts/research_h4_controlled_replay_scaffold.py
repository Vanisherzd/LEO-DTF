#!/usr/bin/env python3
"""H4: Controlled trace-driven HIL replay scaffold (software-only, no hardware).

Defines how (later) conducted/shielded hardware-derived observations will be
compared against software DTOI diagnostics (C19-C22). With no hardware runs, it
emits the replay/comparison contract and marks replay pending.

Does NOT capture, transmit, replay over RF, or access hardware. Read-only w.r.t.
paper/docs/README. Does not claim HIL/OTA/hardware validation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_h4_controlled_replay_scaffold"

REPLAY_STEPS = [
    {"step": "select_trace", "detail": "Pick a Real-TLE-driven trace used in C19/E1."},
    {"step": "conducted_shielded_emit", "detail": "Emit packets over conducted/shielded path ONLY (manual-gated; no OTA)."},
    {"step": "rx_capture", "detail": "USRP B210 Rx-only capture to SigMF (manual-gated)."},
    {"step": "h2_extract", "detail": "Run H2 extraction to per-packet observations."},
    {"step": "align_to_software", "detail": "Align hardware observations to software DTOI predictions for the same geometry."},
    {"step": "compare_metrics", "detail": "Compare DTOI trend, observable fraction, residual distribution."},
    {"step": "report", "detail": "Emit agreement report; upgrade claims ONLY if repeatable agreement holds."},
]


def build_report(run_dir: Path | None) -> dict[str, Any]:
    hw_obs_present = run_dir is not None and (run_dir / "extracted_observations.csv").exists()
    return {
        "metadata": {
            "phase": "H4",
            "generated_by": "research_h4_controlled_replay_scaffold.py",
            "source_files_modified": False,
            "mode": "software_only_scaffold",
            "hardware_validation_complete": False,
            "hil_validation_complete": False,
            "ota_validation_complete": False,
            "localization_accuracy_proven": False,
        },
        "replay_status": "ready_to_compare" if hw_obs_present else "pending_hardware_runs",
        "run_dir": str(run_dir) if run_dir else None,
        "replay_steps": REPLAY_STEPS,
        "comparison_contract": {
            "software_reference": "C19-C22 DTOI diagnostics (E1-E4)",
            "hardware_input": "extracted_observations.csv from H2",
            "metrics": ["dtoi_trend_agreement", "observable_fraction_delta", "residual_ks_distance"],
            "repeatability_required": True,
            "min_runs_for_claim_upgrade": 3,
        },
        "rf_safety": {
            "ota_allowed": False,
            "conducted_or_shielded_required": True,
            "manual_gate_required_before_emit": True,
            "manual_gate_required_before_rx_gain_freq_change": True,
        },
        "claim_boundary": {
            "allowed_now": [
                "Replay/comparison contract defined (software-only).",
                "Repeatability threshold for any future claim upgrade documented.",
            ],
            "forbidden_now": [
                "completed HIL validation",
                "real satellite OTA validation",
                "real satellite capture validated",
                "localization accuracy proven",
            ],
        },
        "next_actions": [
            "Complete H0/H1 (firmware TX-disabled boot + Rx-only readiness) under manual gates.",
            "Run conducted/shielded replay only after explicit operator approval.",
            "Aggregate >= min_runs_for_claim_upgrade repeatable runs before any wording upgrade.",
        ],
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "h4_controlled_replay_scaffold.json"
    md_path = out_dir / "h4_controlled_replay_scaffold.md"

    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# H4 Controlled Trace-driven HIL Replay Scaffold (software-only)",
        "",
        "Defines hardware-vs-software comparison contract. No emit, no capture, no OTA.",
        "Does not claim HIL/OTA/hardware validation.",
        "",
        f"- replay_status: {report['replay_status']}",
        "",
        "## Replay Steps",
        "",
    ]
    for s in report["replay_steps"]:
        md.append(f"- {s['step']}: {s['detail']}")
    md += ["", "## Comparison Contract", ""]
    for k, v in report["comparison_contract"].items():
        md.append(f"- {k}: {v}")
    md += ["", "## RF Safety", ""]
    for k, v in report["rf_safety"].items():
        md.append(f"- {k}: {v}")
    md += ["", "## Claim Boundary — Allowed Now", ""] + [f"- {c}" for c in report["claim_boundary"]["allowed_now"]]
    md += ["", "## Claim Boundary — Forbidden Now", ""] + [f"- {c}" for c in report["claim_boundary"]["forbidden_now"]]
    md += ["", "## Next Actions", ""] + [f"- {c}" for c in report["next_actions"]]
    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"replay_status: {report['replay_status']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    write_outputs(build_report(args.run_dir), args.output_dir)


if __name__ == "__main__":
    main()
