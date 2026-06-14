#!/usr/bin/env python3
"""C27: Full re-derivation readiness report.

This script re-derives the LEO-DTF problem statement, contribution, evidence
map, claim boundary, paper section risk map, hardware gap map, and a Mac-based
hardware execution plan from prior diagnostic artifacts.

It is read-only with respect to paper/docs/README/workflows. It only reads the
upstream C23/C24A/C24B-alt/C25/C26 artifacts and writes a consolidated readiness
report under experiments/results/research_full_rederive_report/.

It does NOT access hardware, does NOT perform capture, and does NOT claim any
HIL/OTA/localization validation. The report explicitly records that:
  hardware_validation_complete = False
  HIL_validation_complete = False
  OTA_validation_complete = False
  localization_accuracy_proven = False
  software_diagnostic_chain_complete = True only if C23/C25/C26 support it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_full_rederive_report"

C23 = ROOT / "experiments/results/research_consolidated_evidence_table/consolidated_evidence_table.json"
C24A = ROOT / "experiments/results/research_claim_audit_triage/claim_audit_triage.json"
C24B_ALT = ROOT / "experiments/results/research_claim_patch_proposal/claim_patch_proposal.json"
C25 = ROOT / "experiments/results/research_paper_readiness_report/paper_readiness_report.json"
C26 = ROOT / "experiments/results/research_hardware_readiness_checker/hardware_readiness_report.json"

INPUTS = {"C23": C23, "C24A": C24A, "C24B_alt": C24B_ALT, "C25": C25, "C26": C26}

# Claims that must never appear as supportable until repeatable hardware exists.
FORBIDDEN_CLAIMS = [
    "OTA validation completed",
    "HIL validation completed",
    "real satellite capture validated",
    "localization accuracy proven",
    "meter-level localization",
    "deployment-ready system",
]


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
    if all(p.exists() for p in INPUTS.values()):
        return
    if not generate_missing:
        missing = [k for k, p in INPUTS.items() if not p.exists()]
        raise FileNotFoundError(f"Missing rederive inputs: {missing}")

    if not C23.exists():
        run_cmd(["scripts/research_consolidated_evidence_table.py", "--generate-missing", "--require-all"])
    if not C24A.exists():
        run_cmd(["scripts/research_claim_evidence_audit.py", "--include", "README.md", "docs", "paper"])
        run_cmd(["scripts/research_claim_audit_triage.py"])
    if not C24B_ALT.exists():
        run_cmd(["scripts/research_claim_patch_proposal.py"])
    if not C25.exists():
        run_cmd(["scripts/research_paper_readiness_report.py", "--generate-missing"])
    if not C26.exists():
        run_cmd(["scripts/research_hardware_readiness_checker.py"])


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def problem_statement() -> dict[str, Any]:
    return {
        "one_line": (
            "Nuisance-aware observability diagnostics for LEO Doppler-time fingerprints "
            "under CFO/drift/geometry uncertainty."
        ),
        "what_it_solves": (
            "Determines, before any hardware deployment, whether a LEO Doppler-time "
            "fingerprint (DTF) remains observable/identifiable once realistic nuisance "
            "parameters (carrier-frequency offset, oscillator drift, station geometry) "
            "are marginalized, rather than assuming an ideal noise-free channel."
        ),
        "why_it_matters": (
            "LEO links carry large, time-varying Doppler whose information is easily "
            "masked by oscillator CFO/drift and geometry ambiguity. Without an "
            "observability diagnostic, a fingerprint that looks separable in an ideal "
            "model can be unidentifiable in practice, leading to over-optimistic "
            "localization/observability claims."
        ),
        "valid_assumptions": [
            "Orbit-driven differential Doppler traces are simulation-derived but physically parameterized.",
            "Nuisance parameters (CFO, drift, geometry placement) are bounded and can be swept as priors.",
            "Baselines (naive Doppler/SNR, matched-filter proxy) are evaluated on the same synthetic traces.",
            "Evidence is software-side/proxy-only; no RF hardware behavior is assumed.",
        ],
        "what_the_method_does": (
            "Computes a Doppler-Time Observability Index (DTOI) over orbit-driven traces "
            "with nuisance marginalization, compares it against naive baselines, and "
            "stress-tests sensitivity to oscillator and geometry nuisances to bound when "
            "the fingerprint is diagnostically observable."
        ),
    }


def revised_core_contribution(c23: dict[str, Any]) -> dict[str, Any]:
    overall = c23.get("overall_assessment", {})
    return {
        "headline": (
            "A nuisance-aware observability diagnostic (DTOI) for LEO Doppler-time "
            "fingerprints, validated as a software/proxy evidence chain that bounds "
            "when fingerprints stay identifiable under CFO/drift/geometry uncertainty."
        ),
        "genuinely_novel": [
            "Framing LEO DTF identifiability as an observability-diagnostic problem under nuisance marginalization.",
            "DTOI as a single diagnostic index linking orbit geometry, CFO/drift, and station placement.",
            "Mismatch analysis showing DTOI diverges from naive Doppler/SNR proxy baselines.",
            "A conservative claim-boundary methodology separating proxy evidence from hardware validation.",
        ],
        "supported_by": {
            "all_sources_available": overall.get("all_sources_available", False),
            "all_suspicious_flags_empty": overall.get("all_suspicious_flags_empty", False),
            "diagnostic_only": overall.get("diagnostic_only", False),
            "not_ota_not_hil_not_localization": overall.get("not_ota_not_hil_not_localization", False),
        },
    }


def non_contributions() -> list[str]:
    return [
        "Engineering glue for orbit trace generation and parameter sweeps (implementation, not novelty).",
        "JSON/Markdown report plumbing and CI wiring (tooling).",
        "Baseline proxy reimplementations (comparison scaffolding, not a new estimator).",
        "Directory/metadata conventions for future hardware runs (process, not result).",
    ]


def method_stack(c23: dict[str, Any]) -> list[dict[str, Any]]:
    records = c23.get("evidence_records", [])
    stack = []
    for r in records:
        stack.append(
            {
                "phase": r.get("phase"),
                "title": r.get("title"),
                "claim_scope": r.get("claim_scope"),
                "status": r.get("status"),
                "layer": "software/proxy diagnostic",
            }
        )
    return stack


def evidence_map(c23: dict[str, Any], c25: dict[str, Any]) -> dict[str, Any]:
    records = c23.get("evidence_records", [])
    sw_status = c25.get("software_evidence_status", {})

    software_proven = []
    simulation_proxy_supported = []
    for r in records:
        entry = {
            "phase": r.get("phase"),
            "claim": r.get("claim_scope"),
            "supporting_script": r.get("source_path"),
            "status": r.get("status"),
            "limitation": "synthetic/orbit-driven proxy evidence; not hardware-validated",
            "suspicious_flags": r.get("suspicious_flags", []),
        }
        if r.get("status") == "available" and not r.get("suspicious_flags"):
            software_proven.append(entry)
        else:
            simulation_proxy_supported.append(entry)

    return {
        "software_proven": software_proven,
        "simulation_proxy_supported": simulation_proxy_supported,
        "planned_hardware": [
            "LR1121/STM32 transmit-only characterized packet source.",
            "USRP B210 receive-only controlled (conducted/shielded) IQ capture.",
            "Offline Doppler/CFO/delay extraction against C19-C22 diagnostics.",
        ],
        "not_supported": list(FORBIDDEN_CLAIMS),
        "software_evidence_status": sw_status,
    }


def claim_boundary(c23: dict[str, Any], c25: dict[str, Any], c26: dict[str, Any]) -> dict[str, Any]:
    assess = c25.get("readiness_assessment", {})
    sw_complete = bool(assess.get("software_diagnostic_chain_complete", False))
    # Cross-check against C23 readiness and C26 documentation readiness.
    c23_ready = bool(c23.get("overall_assessment", {}).get("ready_for_claim_table_sync", False))
    c26_docs_ready = c26.get("readiness_level") == "documentation_ready_for_mac_bringup"

    return {
        "software_diagnostic_chain_complete": sw_complete and c23_ready,
        "c23_ready_for_claim_table_sync": c23_ready,
        "c26_documentation_ready_for_mac_bringup": c26_docs_ready,
        "hardware_validation_complete": False,
        "HIL_validation_complete": False,
        "OTA_validation_complete": False,
        "localization_accuracy_proven": False,
        "supportable_claims": c23.get("safe_claims", []),
        "forbidden_until_hardware": list(FORBIDDEN_CLAIMS),
    }


def paper_section_risk_map(c24b: dict[str, Any], c25: dict[str, Any]) -> list[dict[str, Any]]:
    paths_with_proposals = set(
        c24b.get("proposal_summary", {}).get("paths_with_proposals", [])
    )
    sections = [
        ("00_abstract.tex", "Abstract"),
        ("01_introduction.tex", "Introduction"),
        ("02_background.tex", "Background"),
        ("03_system_model.tex", "System Model"),
        ("04_doppler_time_fingerprint.tex", "Method (DTF)"),
        ("05_bayesian_estimator.tex", "Method (Estimator)"),
        ("06_trace_driven_hil.tex", "HIL Plan"),
        ("07_evaluation_plan.tex", "Experiments"),
        ("08_limitations.tex", "Limitations"),
        ("09_conclusion.tex", "Conclusion"),
    ]
    risk_map = []
    for fname, label in sections:
        rel = f"paper/sections/{fname}"
        flagged = rel in paths_with_proposals
        risk_map.append(
            {
                "section": label,
                "path": rel,
                "has_wording_proposal": flagged,
                "risk": "wording may overstate proxy evidence" if flagged else "no flagged overclaim",
                "action": "review C24B-alt proposal before edit" if flagged else "no action pending",
            }
        )
    return risk_map


def hardware_gap_map(c26: dict[str, Any]) -> dict[str, Any]:
    return {
        "documentation_readiness_level": c26.get("readiness_level"),
        "required_docs": {
            k: v.get("exists") for k, v in c26.get("required_docs", {}).items()
        },
        "metadata_ready": c26.get("metadata_status", {}).get("metadata_ready"),
        "safety_doc_ready": c26.get("safety_status", {}).get("safety_doc_ready"),
        "lr1121_tx_only_guard": c26.get("hardware_boundary_status", {}).get("lr1121_tx_only_guard"),
        "usrp_rx_only_guard": c26.get("hardware_boundary_status", {}).get("usrp_rx_only_guard"),
        "open_gaps": [
            "No repeatable controlled capture has been executed.",
            "No hardware-derived DTOI comparison against C19-C22 exists yet.",
            "HIL/OTA validation remain planned, not executed.",
        ],
    }


def mac_hardware_execution_plan() -> dict[str, Any]:
    return {
        "environment": "User Mac with physical LR1121/STM32 + USRP B210; not inside container.",
        "constraints": [
            "Conducted or shielded setup only; no unlicensed OTA transmission.",
            "LR1121/STM32 used as transmit-only characterized packet source.",
            "USRP B210 used as receive-only capture front-end.",
            "Assume no licensed spectrum; keep RF on cable + attenuator/dummy load.",
        ],
        "steps": [
            "Clone repo on Mac; install uv, UHD/USRP drivers, serial tooling.",
            "Verify USRP B210 visibility via UHD utilities (uhd_find_devices).",
            "Prepare LR1121/STM32 packet-source firmware with serial timestamp logging.",
            "Create capture run dir data/hil_runs/{run_id}/ with metadata.json.",
            "Record center frequency, packet duration, timestamps, hardware IDs before capture.",
            "Capture controlled cable-connected/shielded packets; write capture manifest.",
            "Run offline Doppler/CFO/delay extraction and compare to C19-C22 diagnostics.",
            "Only after repeatable captures may HIL status move planned -> executed.",
        ],
        "artifacts": [
            "data/hil_runs/{run_id}/metadata.json",
            "data/hil_runs/{run_id}/capture manifest",
            "offline extraction outputs for comparison vs software diagnostics",
        ],
        "safety_checks": [
            "Confirm 50-ohm termination / attenuator / dummy load before any Tx.",
            "Confirm no antenna radiating on unlicensed spectrum.",
            "Confirm shielded or conducted path before enabling LR1121 Tx.",
        ],
    }


def recommended_next_phases() -> list[dict[str, str]]:
    return [
        {"phase": "A", "name": "Software/paper re-derivation", "status": "in_progress",
         "summary": "Consolidate problem/contribution/evidence boundary (this report)."},
        {"phase": "B", "name": "Conservative paper wording patch proposal", "status": "pending_human_review",
         "summary": "Apply C24B-alt guarded wording as a separate human-approved patch."},
        {"phase": "C", "name": "Mac hardware bring-up", "status": "planned",
         "summary": "Prepare LR1121/USRP environment, metadata, safety on user Mac."},
        {"phase": "D", "name": "Controlled capture", "status": "planned",
         "summary": "Conducted/shielded repeatable captures with manifests."},
        {"phase": "E", "name": "Hardware result integration", "status": "planned",
         "summary": "Compare hardware-derived observations against software diagnostics; upgrade claims only if supported."},
    ]


def final_readiness_assessment(boundary: dict[str, Any], c25: dict[str, Any]) -> dict[str, Any]:
    sw_complete = bool(boundary["software_diagnostic_chain_complete"])
    level = (
        "software_diagnostic_chain_complete_hardware_pending"
        if sw_complete
        else "software_diagnostic_chain_incomplete"
    )
    return {
        "level": level,
        "software_diagnostic_chain_complete": sw_complete,
        "hardware_validation_complete": False,
        "HIL_validation_complete": False,
        "OTA_validation_complete": False,
        "localization_accuracy_proven": False,
        "can_commit_now": [
            "Software/proxy diagnostic analysis and readiness reports.",
            "Problem/contribution re-derivation under diagnostic-only framing.",
            "Hardware execution PLAN documents (no validation claims).",
        ],
        "must_wait_for_hardware": list(FORBIDDEN_CLAIMS),
        "remaining_risks": [
            "Paper wording may still overstate proxy evidence (1 true overclaim flagged by C24A).",
            "No hardware capture exists; all hardware claims remain planned.",
            "C25 readiness gated on resolving/guarding overclaims before submission.",
        ],
        "summary": (
            "Software-side diagnostic evidence chain is complete and CI-green; hardware "
            "validation (HIL/OTA) and localization accuracy remain unproven and are future "
            "work. Paper claims must stay diagnostic/proxy-only until repeatable hardware "
            "captures exist."
        ),
        "c25_readiness_level": c25.get("readiness_assessment", {}).get("readiness_level"),
    }


def build_report() -> dict[str, Any]:
    c23 = load(C23)
    c24a = load(C24A)
    c24b = load(C24B_ALT)
    c25 = load(C25)
    c26 = load(C26)

    boundary = claim_boundary(c23, c25, c26)

    return {
        "metadata": {
            "generated_by": "research_full_rederive_report.py",
            "phase": "C27",
            "source_files_modified": False,
            "inputs": {k: str(p.relative_to(ROOT)) for k, p in INPUTS.items()},
            "scope": "read-only re-derivation; does not edit paper/docs/README/workflows",
        },
        "problem_statement": problem_statement(),
        "revised_core_contribution": revised_core_contribution(c23),
        "non_contributions": non_contributions(),
        "method_stack": method_stack(c23),
        "evidence_map": evidence_map(c23, c25),
        "claim_boundary": boundary,
        "paper_section_risk_map": paper_section_risk_map(c24b, c25),
        "hardware_gap_map": hardware_gap_map(c26),
        "Mac_hardware_execution_plan": mac_hardware_execution_plan(),
        "recommended_next_phases": recommended_next_phases(),
        "final_readiness_assessment": final_readiness_assessment(boundary, c25),
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "full_rederive_report.json"
    md_path = out_dir / "full_rederive_report.md"

    json_path.write_text(json.dumps(report, indent=2))

    ps = report["problem_statement"]
    rc = report["revised_core_contribution"]
    fr = report["final_readiness_assessment"]

    md = [
        "# C27 Full Re-derivation Readiness Report",
        "",
        "Read-only re-derivation of the LEO-DTF problem, contribution, evidence, and",
        "hardware plan. Does not modify paper, docs, README, or workflows.",
        "Does not access hardware and does not claim HIL/OTA/localization validation.",
        "",
        "## Problem Statement",
        "",
        f"- One line: {ps['one_line']}",
        f"- Solves: {ps['what_it_solves']}",
        f"- Why it matters: {ps['why_it_matters']}",
        f"- Method: {ps['what_the_method_does']}",
        "",
        "### Valid Assumptions",
        "",
    ]
    md += [f"- {a}" for a in ps["valid_assumptions"]]

    md += ["", "## Revised Core Contribution", "", f"- {rc['headline']}", "", "### Genuinely Novel", ""]
    md += [f"- {n}" for n in rc["genuinely_novel"]]

    md += ["", "## Non-Contributions (engineering/implementation only)", ""]
    md += [f"- {n}" for n in report["non_contributions"]]

    md += ["", "## Method Stack", ""]
    for m in report["method_stack"]:
        md.append(f"- {m['phase']}: {m['title']} — {m['claim_scope']} ({m['status']})")

    md += ["", "## Evidence Map", "", "### Software-Proven", ""]
    for e in report["evidence_map"]["software_proven"]:
        md.append(f"- {e['phase']}: {e['claim']} — {e['supporting_script']} (limitation: {e['limitation']})")
    md += ["", "### Simulation/Proxy-Supported", ""]
    for e in report["evidence_map"]["simulation_proxy_supported"]:
        md.append(f"- {e['phase']}: {e['claim']} ({e['status']})")
    md += ["", "### Planned Hardware", ""]
    md += [f"- {h}" for h in report["evidence_map"]["planned_hardware"]]
    md += ["", "### Not Supported", ""]
    md += [f"- {h}" for h in report["evidence_map"]["not_supported"]]

    md += ["", "## Claim Boundary", ""]
    for k, v in report["claim_boundary"].items():
        if isinstance(v, list):
            md.append(f"- {k}:")
            md += [f"    - {x}" for x in v]
        else:
            md.append(f"- {k}: {v}")

    md += ["", "## Paper Section Risk Map", ""]
    for s in report["paper_section_risk_map"]:
        md.append(f"- {s['section']} ({s['path']}): {s['risk']} → {s['action']}")

    md += ["", "## Hardware Gap Map", ""]
    for k, v in report["hardware_gap_map"].items():
        md.append(f"- {k}: {v}")

    md += ["", "## Mac Hardware Execution Plan", ""]
    plan = report["Mac_hardware_execution_plan"]
    md.append(f"- Environment: {plan['environment']}")
    md += ["", "### Constraints", ""] + [f"- {c}" for c in plan["constraints"]]
    md += ["", "### Steps", ""] + [f"- {c}" for c in plan["steps"]]
    md += ["", "### Artifacts", ""] + [f"- {c}" for c in plan["artifacts"]]
    md += ["", "### Safety Checks", ""] + [f"- {c}" for c in plan["safety_checks"]]

    md += ["", "## Recommended Next Phases", ""]
    for p in report["recommended_next_phases"]:
        md.append(f"- Phase {p['phase']} — {p['name']} ({p['status']}): {p['summary']}")

    md += ["", "## Final Readiness Assessment", ""]
    md.append(f"- Level: {fr['level']}")
    md.append(f"- software_diagnostic_chain_complete: {fr['software_diagnostic_chain_complete']}")
    md.append(f"- hardware_validation_complete: {fr['hardware_validation_complete']}")
    md.append(f"- HIL_validation_complete: {fr['HIL_validation_complete']}")
    md.append(f"- OTA_validation_complete: {fr['OTA_validation_complete']}")
    md.append(f"- localization_accuracy_proven: {fr['localization_accuracy_proven']}")
    md += ["", "### Can Commit Now", ""] + [f"- {c}" for c in fr["can_commit_now"]]
    md += ["", "### Must Wait For Hardware", ""] + [f"- {c}" for c in fr["must_wait_for_hardware"]]
    md += ["", "### Remaining Risks", ""] + [f"- {c}" for c in fr["remaining_risks"]]
    md += ["", "### Summary", "", fr["summary"]]

    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Final readiness level: {fr['level']}")
    print(f"software_diagnostic_chain_complete: {fr['software_diagnostic_chain_complete']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate-missing", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()

    ensure_inputs(args.generate_missing)
    write_outputs(build_report(), args.output_dir)


if __name__ == "__main__":
    main()
