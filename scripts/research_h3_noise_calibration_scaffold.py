#!/usr/bin/env python3
"""H3: Hardware noise calibration scaffold (software-only, no hardware).

Defines how (later) measured noise / CFO / drift statistics will be compared to
the simulation proxy assumptions used in C19-C22. With no hardware measurement
available, it emits the proxy assumption table and marks calibration pending.

Does NOT capture, transmit, or access hardware. Read-only w.r.t.
paper/docs/README. Does not claim HIL/OTA/hardware validation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_h3_noise_calibration_scaffold"

# Proxy assumptions used by software experiments. These are SOFTWARE assumptions,
# NOT measured hardware specifications.
PROXY_ASSUMPTIONS = [
    {"parameter": "cfo_hz", "proxy_range": "software sweep range (see C21)", "source": "C21/C21A/C21B proxy study", "measured": None},
    {"parameter": "drift_hz_per_s", "proxy_range": "software sweep range (see C21)", "source": "C21 proxy study", "measured": None},
    {"parameter": "snr_db", "proxy_range": "software baseline range (see C20)", "source": "C20 baseline proxy", "measured": None},
    {"parameter": "timing_jitter_s", "proxy_range": "software assumption", "source": "model assumption", "measured": None},
]


def build_report(measurement_path: Path | None) -> dict[str, Any]:
    measurement_available = measurement_path is not None and measurement_path.exists()
    return {
        "metadata": {
            "phase": "H3",
            "generated_by": "research_h3_noise_calibration_scaffold.py",
            "source_files_modified": False,
            "mode": "software_only_scaffold",
            "hardware_validation_complete": False,
            "hil_validation_complete": False,
            "ota_validation_complete": False,
            "localization_accuracy_proven": False,
        },
        "calibration_status": "ready_to_compare" if measurement_available else "pending_measurement",
        "measurement_path": str(measurement_path) if measurement_path else None,
        "proxy_assumptions": PROXY_ASSUMPTIONS,
        "comparison_contract": {
            "compute_per_parameter": ["measured_mean", "measured_std", "proxy_range", "within_proxy_range"],
            "decision": "If measured stats fall outside proxy ranges, software claims must be re-scoped, not upgraded.",
        },
        "claim_boundary": {
            "allowed_now": [
                "Proxy assumption table documented (software-only).",
                "Calibration comparison contract defined (no measurement performed).",
            ],
            "forbidden_now": [
                "hardware oscillator specification derived",
                "completed HIL validation",
                "localization accuracy proven",
            ],
        },
        "next_actions": [
            "After H2 extraction on approved captures, aggregate measured noise/CFO/drift stats.",
            "Re-run with --measurement to compare against proxy ranges.",
            "Document match/mismatch; keep proxy claims conservative until calibrated.",
        ],
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "h3_noise_calibration_scaffold.json"
    md_path = out_dir / "h3_noise_calibration_scaffold.md"

    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# H3 Hardware Noise Calibration Scaffold (software-only)",
        "",
        "Defines how measured noise/CFO/drift will be compared to simulation proxy assumptions.",
        "No measurement performed. Does not claim HIL/OTA/hardware validation.",
        "",
        f"- calibration_status: {report['calibration_status']}",
        "",
        "## Proxy Assumptions (software, NOT measured hardware spec)",
        "",
        "| parameter | proxy_range | source | measured |",
        "|---|---|---|---|",
    ]
    for p in report["proxy_assumptions"]:
        md.append(f"| {p['parameter']} | {p['proxy_range']} | {p['source']} | {p['measured']} |")
    md += ["", "## Comparison Contract", ""]
    md.append(f"- compute_per_parameter: {report['comparison_contract']['compute_per_parameter']}")
    md.append(f"- decision: {report['comparison_contract']['decision']}")
    md += ["", "## Claim Boundary — Allowed Now", ""] + [f"- {c}" for c in report["claim_boundary"]["allowed_now"]]
    md += ["", "## Claim Boundary — Forbidden Now", ""] + [f"- {c}" for c in report["claim_boundary"]["forbidden_now"]]
    md += ["", "## Next Actions", ""] + [f"- {c}" for c in report["next_actions"]]
    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"calibration_status: {report['calibration_status']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--measurement", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    write_outputs(build_report(args.measurement), args.output_dir)


if __name__ == "__main__":
    main()
