#!/usr/bin/env python3
"""C25: Paper readiness report from evidence + claim-safety artifacts.

This script does not edit paper/docs/README. It only reads prior diagnostic
artifacts and generates a readiness report for human review.

Purpose:
- summarize software-side evidence maturity
- summarize claim-safety state
- identify what can be said now
- identify what must wait for hardware/OTA/HIL experiments
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_paper_readiness_report"

C23 = ROOT / "experiments/results/research_consolidated_evidence_table/consolidated_evidence_table.json"
C24A = ROOT / "experiments/results/research_claim_audit_triage/claim_audit_triage.json"
C24B_ALT = ROOT / "experiments/results/research_claim_patch_proposal/claim_patch_proposal.json"


def run_cmd(args: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def ensure_inputs(generate_missing: bool) -> None:
    if C23.exists() and C24A.exists() and C24B_ALT.exists():
        return
    if not generate_missing:
        missing = [str(p.relative_to(ROOT)) for p in [C23, C24A, C24B_ALT] if not p.exists()]
        raise FileNotFoundError(f"Missing readiness inputs: {missing}")

    if not C23.exists():
        run_cmd(["scripts/research_consolidated_evidence_table.py", "--generate-missing", "--require-all"])
    if not C24A.exists():
        run_cmd(["scripts/research_claim_evidence_audit.py", "--include", "README.md", "docs", "paper"])
        run_cmd(["scripts/research_claim_audit_triage.py"])
    if not C24B_ALT.exists():
        run_cmd(["scripts/research_claim_patch_proposal.py"])


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def readiness_level(c23: dict[str, Any], c24a: dict[str, Any], c24b: dict[str, Any]) -> str:
    evidence = c23.get("overall_assessment", {})
    triage_counts = c24a.get("triage_counts", {})
    proposal = c24b.get("proposal_summary", {})

    if not evidence.get("ready_for_claim_table_sync", False):
        return "not_ready_evidence_incomplete"
    if triage_counts.get("likely_true_overclaim", 0) > 0:
        return "not_ready_until_true_overclaims_resolved_or_guarded"
    if proposal.get("selected_proposals", 0) > 0:
        return "conditionally_ready_after_human_wording_review"
    return "software_diagnostic_ready"


def build_report(c23: dict[str, Any], c24a: dict[str, Any], c24b: dict[str, Any]) -> dict[str, Any]:
    evidence = c23.get("overall_assessment", {})
    records = c23.get("evidence_records", [])
    triage_counts = c24a.get("triage_counts", {})
    doc_actions = c24a.get("recommended_doc_actions", [])
    proposal_summary = c24b.get("proposal_summary", {})

    software_evidence_status = {
        "orbit_parameter_sweep": "available" if any(r.get("phase") == "C19" and r.get("status") == "available" for r in records) else "missing",
        "baseline_comparison": "available" if any(r.get("phase") == "C20" and r.get("status") == "available" for r in records) else "missing",
        "oscillator_sensitivity": "available" if any(r.get("phase") == "C21" and r.get("status") == "available" for r in records) else "missing",
        "oscillator_strong_focus": "available" if any(r.get("phase") == "C21B" and r.get("status") == "available" for r in records) else "missing",
        "geometry_placement_robustness": "available" if any(r.get("phase") == "C22" and r.get("status") == "available" for r in records) else "missing",
    }

    now_supportable_claims = [
        "DTOI is supportable as a nuisance-aware observability diagnostic.",
        "The current evidence is software-side, orbit-driven, synthetic, and proxy-based.",
        "DTOI can be compared against naive Doppler/SNR and matched-filter proxy baselines.",
        "Oscillator/CFO sensitivity can be discussed only as a conservative proxy stress study.",
        "Geometry placement robustness can be discussed only as a conservative proxy study.",
        "Current results can motivate hardware experiments, but cannot replace them.",
    ]

    not_yet_supportable_claims = [
        "real satellite OTA validation",
        "completed HIL validation",
        "real LR1121/USRP IQ capture validation",
        "localization accuracy proven",
        "meter-level or sub-kilometer localization performance",
        "deployment-ready system",
        "hardware oscillator specification",
        "surveyed station placement validation",
    ]

    paper_risk_register = [
        {
            "risk": "Overclaiming software/proxy evidence as hardware validation",
            "severity": "high",
            "mitigation": "Keep all claims diagnostic-only until hardware capture is executed.",
        },
        {
            "risk": "Using localization-accuracy language before real timing/RF validation",
            "severity": "high",
            "mitigation": "Use observability, ROI-reduction, or diagnostic wording instead.",
        },
        {
            "risk": "HIL wording sounding completed instead of planned",
            "severity": "medium",
            "mitigation": "Use planned/pending HIL-validation workflow wording.",
        },
        {
            "risk": "Paper sections still contain manual-review wording",
            "severity": "medium",
            "mitigation": "Review C24B-alt proposal before submission.",
        },
    ]

    hardware_next_steps = [
        "Bring up LR1121/STM32 as a transmit-only characterized packet source.",
        "Capture controlled packets with USRP B210 in receive-only mode.",
        "Log packet timestamps, center frequency, packet duration, and hardware metadata.",
        "Run offline Doppler/CFO/delay injection or extraction pipeline.",
        "Compare hardware-derived observations against C19-C22 software diagnostics.",
        "Only after repeatable capture should HIL validation wording be upgraded from planned to executed.",
        "Real satellite OTA validation remains a later phase requiring live passes and regulatory planning.",
    ]

    section_review_queue = []
    for item in doc_actions:
        path = item.get("path", "")
        action = item.get("action", "")
        if path.startswith("paper/") or action in {"manually_rewrite_overclaim", "add_guarded_wording", "manual_review_required"}:
            section_review_queue.append(item)

    level = readiness_level(c23, c24a, c24b)

    if level == "conditionally_ready_after_human_wording_review":
        recommendation = (
            "Proceed to human review of C24B-alt wording proposals before paper submission; "
            "software evidence is organized, but hardware validation remains future work."
        )
    elif level == "software_diagnostic_ready":
        recommendation = (
            "Software diagnostic evidence is ready for paper-side use under strict diagnostic-only framing."
        )
    else:
        recommendation = "Do not prepare submission wording until evidence or overclaim issues are resolved."

    return {
        "metadata": {
            "generated_by": "research_paper_readiness_report.py",
            "phase": "C25",
            "inputs": {
                "C23": str(C23.relative_to(ROOT)),
                "C24A": str(C24A.relative_to(ROOT)),
                "C24B_alt": str(C24B_ALT.relative_to(ROOT)),
            },
            "source_files_modified": False,
        },
        "readiness_assessment": {
            "readiness_level": level,
            "c23_ready_for_claim_table_sync": evidence.get("ready_for_claim_table_sync", False),
            "c23_all_sources_available": evidence.get("all_sources_available", False),
            "c23_all_suspicious_flags_empty": evidence.get("all_suspicious_flags_empty", False),
            "c24a_triage_counts": triage_counts,
            "c24b_alt_selected_proposals": proposal_summary.get("selected_proposals", 0),
            "paper_ready_without_human_review": False,
            "software_diagnostic_chain_complete": all(v == "available" for v in software_evidence_status.values()),
            "hardware_validation_complete": False,
            "ota_validation_complete": False,
        },
        "software_evidence_status": software_evidence_status,
        "now_supportable_claims": now_supportable_claims,
        "not_yet_supportable_claims": not_yet_supportable_claims,
        "paper_risk_register": paper_risk_register,
        "section_review_queue": section_review_queue,
        "hardware_next_steps": hardware_next_steps,
        "long_roadmap": {
            "current_stage": "software-side diagnostic evidence and claim-safety preparation",
            "next_stage": "manual paper wording review under diagnostic-only framing",
            "hardware_stage": "LR1121/STM32 + USRP B210 controlled capture and HIL execution",
            "later_stage": "real satellite OTA planning and validation only after controlled HIL is repeatable",
        },
        "recommended_next_action": recommendation,
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "paper_readiness_report.json"
    md_path = out_dir / "paper_readiness_report.md"

    json_path.write_text(json.dumps(report, indent=2))

    md = [
        "# C25 Paper Readiness Report",
        "",
        "This report is generated from software-side evidence and claim-safety artifacts.",
        "It does not modify paper, docs, README, or workflow files.",
        "",
        "## Readiness Assessment",
        "",
    ]
    for k, v in report["readiness_assessment"].items():
        md.append(f"- {k}: {v}")

    md.extend(["", "## Software Evidence Status", ""])
    for k, v in report["software_evidence_status"].items():
        md.append(f"- {k}: {v}")

    md.extend(["", "## Claims Supportable Now", ""])
    for item in report["now_supportable_claims"]:
        md.append(f"- {item}")

    md.extend(["", "## Claims Not Yet Supportable", ""])
    for item in report["not_yet_supportable_claims"]:
        md.append(f"- {item}")

    md.extend(["", "## Paper Risk Register", ""])
    for item in report["paper_risk_register"]:
        md.append(f"- **{item['severity']}** — {item['risk']}: {item['mitigation']}")

    md.extend(["", "## Section Review Queue", ""])
    if report["section_review_queue"]:
        for item in report["section_review_queue"]:
            md.append(f"- {item.get('path')}: {item.get('action')} ({item.get('total_hits')} hits)")
    else:
        md.append("- None")

    md.extend(["", "## Hardware Next Steps", ""])
    for item in report["hardware_next_steps"]:
        md.append(f"- {item}")

    md.extend(["", "## Long Roadmap", ""])
    for k, v in report["long_roadmap"].items():
        md.append(f"- {k}: {v}")

    md.extend(["", "## Recommended Next Action", "", report["recommended_next_action"]])
    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Readiness level: {report['readiness_assessment']['readiness_level']}")
    print(f"Recommended next action: {report['recommended_next_action']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate-missing", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()

    ensure_inputs(args.generate_missing)
    report = build_report(load(C23), load(C24A), load(C24B_ALT))
    write_outputs(report, args.output_dir)


if __name__ == "__main__":
    main()
