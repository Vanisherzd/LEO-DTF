#!/usr/bin/env python3
"""C26: Hardware experiment readiness checker.

This script checks whether the repository contains enough documentation and
metadata structure to prepare a later Mac-based LR1121/STM32 + USRP B210
hardware bring-up.

It does not access hardware, does not perform capture, and does not claim
HIL/OTA validation.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_hardware_readiness_checker"

REQUIRED_DOCS = {
    "hil_plan": "docs/hardware/hil_plan.md",
    "lr1121_packet_source": "docs/hardware/lr1121_stm32_packet_source.md",
    "usrp_b210_capture_protocol": "docs/hardware/usrp_b210_capture_protocol.md",
    "rf_safety_checklist": "docs/hardware/rf_safety_checklist.md",
}

EXPECTED_METADATA_TERMS = [
    "metadata.json",
    "capture_IQ",
    "sigmf",
    "frequency",
    "timestamp",
    "packet",
    "duration",
]

SAFETY_TERMS = [
    "no unlicensed OTA",
    "conducted",
    "shielded",
    "attenuator",
    "dummy load",
    "50-ohm",
]

BOUNDARY_TERMS = [
    "transmit-only",
    "Tx-only",
    "receive-only",
    "not used as a receiver",
    "does not transmit",
]


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(errors="ignore")


def contains_any(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return any(term.lower() in low for term in terms)


def count_terms(text: str, terms: list[str]) -> dict[str, bool]:
    low = text.lower()
    return {term: term.lower() in low for term in terms}


def doc_status() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, rel in REQUIRED_DOCS.items():
        path = ROOT / rel
        text = read_text(path)
        out[name] = {
            "path": rel,
            "exists": path.exists(),
            "line_count": len(text.splitlines()) if text else 0,
            "has_design_or_plan_status": contains_any(text, ["design only", "planned", "plan", "not yet", "no captures", "no transmissions"]),
        }
    return out


def metadata_status() -> dict[str, Any]:
    combined = "\n".join(read_text(ROOT / rel) for rel in REQUIRED_DOCS.values())
    term_hits = count_terms(combined, EXPECTED_METADATA_TERMS)
    return {
        "expected_metadata_terms": term_hits,
        "metadata_ready": all(term_hits.values()),
        "capture_directory_convention_found": "data/hil_runs" in combined or "hil_runs" in combined,
    }


def safety_status() -> dict[str, Any]:
    text = read_text(ROOT / REQUIRED_DOCS["rf_safety_checklist"])
    term_hits = count_terms(text, SAFETY_TERMS)
    return {
        "safety_terms": term_hits,
        "safety_doc_ready": (ROOT / REQUIRED_DOCS["rf_safety_checklist"]).exists() and sum(term_hits.values()) >= 4,
        "no_ota_guard_found": contains_any(text, ["does not authorize over-the-air", "no unlicensed ota", "all ota experiments require"]),
    }


def hardware_boundary_status() -> dict[str, Any]:
    lr = read_text(ROOT / REQUIRED_DOCS["lr1121_packet_source"])
    usrp = read_text(ROOT / REQUIRED_DOCS["usrp_b210_capture_protocol"])
    combined = lr + "\n" + usrp
    return {
        "lr1121_tx_only_guard": contains_any(lr, ["transmit-only", "tx-only", "not used as a receiver"]),
        "usrp_rx_only_guard": contains_any(usrp, ["receive-only", "does not transmit"]),
        "boundary_terms": count_terms(combined, BOUNDARY_TERMS),
    }


def claim_boundary_status() -> dict[str, Any]:
    combined = "\n".join(read_text(ROOT / rel) for rel in REQUIRED_DOCS.values())
    return {
        "hardware_validation_complete": False,
        "hil_validation_complete": False,
        "ota_validation_complete": False,
        "real_satellite_capture_complete": False,
        "explicit_not_claimed_terms_found": contains_any(
            combined,
            ["not claimed", "not yet executed", "no captures have been performed", "no transmissions have been performed"],
        ),
    }


def readiness_level(report: dict[str, Any]) -> str:
    docs_ok = all(x["exists"] for x in report["required_docs"].values())
    meta_ok = report["metadata_status"]["metadata_ready"]
    safety_ok = report["safety_status"]["safety_doc_ready"] and report["safety_status"]["no_ota_guard_found"]
    boundary_ok = report["hardware_boundary_status"]["lr1121_tx_only_guard"] and report["hardware_boundary_status"]["usrp_rx_only_guard"]

    if docs_ok and meta_ok and safety_ok and boundary_ok:
        return "documentation_ready_for_mac_bringup"
    if docs_ok and safety_ok:
        return "partial_readiness_needs_metadata_or_boundary_cleanup"
    return "not_ready_for_hardware_bringup"


def build_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "metadata": {
            "generated_by": "research_hardware_readiness_checker.py",
            "phase": "C26",
            "source_files_modified": False,
            "intended_hardware_execution_environment": "user Mac with physical LR1121/STM32/USRP B210 access",
        },
        "required_docs": doc_status(),
        "metadata_status": metadata_status(),
        "safety_status": safety_status(),
        "hardware_boundary_status": hardware_boundary_status(),
        "claim_boundary_status": claim_boundary_status(),
        "mac_bringup_notes": [
            "Clone the repository on the Mac that has physical hardware access.",
            "Do not run hardware capture inside the Hermes/container environment.",
            "Use conducted or shielded setup first; do not perform unlicensed OTA transmission.",
            "Treat LR1121 as transmit-only packet source unless a separate receiver configuration is implemented.",
            "Treat USRP B210 as receive-only capture front-end for this workflow.",
            "Record all capture metadata before using results in paper claims.",
        ],
        "hardware_next_steps": [
            "Clone repo on Mac and install uv/UHD/USRP dependencies.",
            "Verify USRP B210 visibility with UHD tools on Mac.",
            "Prepare LR1121/STM32 packet-source firmware and serial logging.",
            "Create a capture run directory under data/hil_runs/{run_id}/.",
            "Record metadata.json before capture.",
            "Capture controlled cable-connected or shielded packets.",
            "Only after repeatable capture should HIL status move from planned to executed.",
        ],
        "forbidden_claims_until_hardware_done": [
            "completed HIL validation",
            "real satellite OTA validation",
            "real satellite capture validated",
            "localization accuracy proven",
            "meter-level localization",
            "deployment-ready system",
        ],
    }
    report["readiness_level"] = readiness_level(report)
    report["recommended_next_action"] = (
        "Proceed to Mac hardware bring-up preparation only; keep validation claims planned/pending until captures exist."
        if report["readiness_level"] == "documentation_ready_for_mac_bringup"
        else "Resolve missing documentation, metadata, safety, or hardware-boundary items before Mac bring-up."
    )
    return report


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hardware_readiness_report.json"
    md_path = out_dir / "hardware_readiness_report.md"

    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# C26 Hardware Experiment Readiness Checker",
        "",
        "This report checks repository readiness for later Mac-based hardware bring-up.",
        "It does not access hardware and does not claim HIL/OTA validation.",
        "",
        f"- Readiness level: {report['readiness_level']}",
        f"- Recommended next action: {report['recommended_next_action']}",
        "",
        "## Required Docs",
        "",
    ]
    for name, item in report["required_docs"].items():
        md.append(f"- {name}: exists={item['exists']}, lines={item['line_count']}, path={item['path']}")

    md.extend(["", "## Metadata Status", ""])
    for k, v in report["metadata_status"].items():
        md.append(f"- {k}: {v}")

    md.extend(["", "## Safety Status", ""])
    for k, v in report["safety_status"].items():
        md.append(f"- {k}: {v}")

    md.extend(["", "## Hardware Boundary Status", ""])
    for k, v in report["hardware_boundary_status"].items():
        md.append(f"- {k}: {v}")

    md.extend(["", "## Claim Boundary Status", ""])
    for k, v in report["claim_boundary_status"].items():
        md.append(f"- {k}: {v}")

    md.extend(["", "## Mac Bring-up Notes", ""])
    for item in report["mac_bringup_notes"]:
        md.append(f"- {item}")

    md.extend(["", "## Hardware Next Steps", ""])
    for item in report["hardware_next_steps"]:
        md.append(f"- {item}")

    md.extend(["", "## Forbidden Claims Until Hardware Is Done", ""])
    for item in report["forbidden_claims_until_hardware_done"]:
        md.append(f"- {item}")

    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Readiness level: {report['readiness_level']}")
    print(f"Recommended next action: {report['recommended_next_action']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    write_outputs(build_report(), args.output_dir)


if __name__ == "__main__":
    main()
