#!/usr/bin/env python3
"""C28: Theory and experiment blueprint for the re-derived LEO-DTF paper.

New framing (clarified by user):
  GNSS-free coarse ROI localization / nuisance-aware DTOI observability for
  low-cost direct-to-satellite IoT.

This script is read-only with respect to paper/docs/README/workflows. It reads
prior diagnostic artifacts (C23/C24A/C24B-alt/C25/C26 and optionally C27) and
generates a consolidated theory + experiment + hardware blueprint for human
review before any paper rewrite.

It does NOT access hardware, does NOT perform capture, and does NOT claim any
HIL/OTA/localization validation. The report explicitly records:
  hardware_validation_complete = False
  hil_validation_complete = False
  ota_validation_complete = False
  localization_accuracy_proven = False
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/research_theory_experiment_blueprint"

C23 = ROOT / "experiments/results/research_consolidated_evidence_table/consolidated_evidence_table.json"
C24A = ROOT / "experiments/results/research_claim_audit_triage/claim_audit_triage.json"
C24B_ALT = ROOT / "experiments/results/research_claim_patch_proposal/claim_patch_proposal.json"
C25 = ROOT / "experiments/results/research_paper_readiness_report/paper_readiness_report.json"
C26 = ROOT / "experiments/results/research_hardware_readiness_checker/hardware_readiness_report.json"
C27 = ROOT / "experiments/results/research_full_rederive_report/full_rederive_report.json"

REQUIRED_INPUTS = {"C23": C23, "C24A": C24A, "C24B_alt": C24B_ALT, "C25": C25, "C26": C26}
OPTIONAL_INPUTS = {"C27": C27}

# Claims that must never appear as supportable. They may appear only inside
# non_contributions or as forbidden-claim fields of the experiment/claim tables.
FORBIDDEN_CLAIMS = [
    "GPS/GNSS replacement",
    "completed HIL validation",
    "real satellite OTA validation",
    "real satellite capture validated",
    "localization accuracy proven",
    "meter-level localization",
    "sub-kilometer performance claim",
    "deployment-ready system",
    "hardware oscillator specification derived",
    "surveyed station placement validation",
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
    if all(p.exists() for p in REQUIRED_INPUTS.values()):
        return
    if not generate_missing:
        missing = [k for k, p in REQUIRED_INPUTS.items() if not p.exists()]
        raise FileNotFoundError(f"Missing blueprint inputs: {missing}")

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
    # C27 is optional; only run it if its generator script is present.
    if not C27.exists() and (ROOT / "scripts/research_full_rederive_report.py").exists():
        run_cmd(["scripts/research_full_rederive_report.py"])


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_optional(path: Path) -> dict[str, Any] | None:
    return load(path) if path.exists() else None


# --------------------------------------------------------------------------- #
# Report sections
# --------------------------------------------------------------------------- #
def final_problem_statement() -> dict[str, Any]:
    return {
        "problem_context": (
            "Low-cost direct-to-satellite IoT endpoints transmit sparse uplink packets to "
            "LEO satellites and often lack a GNSS receiver due to power, cost, and antenna "
            "constraints. Their location must be inferred from the satellite link itself."
        ),
        "core_problem": (
            "Decide, from sparse LEO uplink packets modeled as Doppler-time fingerprints, "
            "whether Real-TLE satellite geometry provides enough observability to reduce the "
            "endpoint's location region (ROI), once oscillator and timing nuisance parameters "
            "are projected out."
        ),
        "why_existing_gps_or_gnss_is_not_assumed": (
            "Target endpoints are GNSS-free by design (cost/power/antenna limits); assuming a "
            "GNSS fix defeats the use case. LEO-DTF is a GNSS-free coarse ROI approach, NOT a "
            "GPS/GNSS replacement."
        ),
        "why_naive_doppler_is_insufficient": (
            "Naive Doppler/SNR ignores carrier-frequency offset (CFO), oscillator drift, and "
            "geometry ambiguity. Unmodeled nuisances mask or bias the fingerprint, so apparent "
            "separability in an ideal model does not imply real observability."
        ),
        "final_one_sentence_problem": (
            "LEO-DTF addresses GNSS-free coarse ROI localization for low-cost "
            "direct-to-satellite IoT by modeling sparse LEO uplink packets as Doppler-time "
            "fingerprints, projecting out oscillator and timing nuisance parameters, and "
            "quantifying when Real-TLE satellite geometry provides sufficient observability "
            "for ROI reduction."
        ),
    }


def revised_core_contributions() -> list[dict[str, str]]:
    return [
        {
            "id": "C1",
            "name": "Real-TLE Doppler-Time Fingerprint model",
            "summary": (
                "Model sparse LEO uplink packets as a Doppler-time fingerprint derived from "
                "Real-TLE/SGP4 satellite geometry, parameterized by endpoint location."
            ),
        },
        {
            "id": "C2",
            "name": "Nuisance-aware projection and posterior ROI reduction",
            "summary": (
                "Project out CFO/drift/clock nuisance parameters and perform posterior grid "
                "inference to reduce the candidate location region (ROI), not to claim a fix."
            ),
        },
        {
            "id": "C3",
            "name": "DTOI observability metric and evidence map",
            "summary": (
                "Define a Doppler-Time Observability Index (DTOI) that quantifies when "
                "geometry yields identifiable fingerprints, backed by a software/proxy evidence map."
            ),
        },
        {
            "id": "C4",
            "name": "Software-to-hardware validation roadmap for Mac-based controlled capture",
            "summary": (
                "Provide a staged roadmap from software/proxy evidence to Mac-based "
                "conducted/shielded LR1121/STM32 + USRP B210 controlled capture; hardware "
                "validation remains future work."
            ),
        },
    ]


def non_contributions() -> list[str]:
    return [
        "NOT a GNSS/GPS replacement.",
        "NOT meter-level localization.",
        "NOT completed HIL validation.",
        "NOT real satellite OTA validation.",
        "NOT a deployment-ready system.",
        "NOT a hardware oscillator specification derived from measurement.",
        "NOT surveyed/validated station placement.",
    ]


def mathematical_model() -> dict[str, Any]:
    return {
        "notation": (
            "x = endpoint state (lat, lon[, alt]); i indexes packets/epochs; "
            "eta = nuisance vector (CFO b, drift d, clock offset/drift); "
            "c = speed of light; f_c = carrier frequency."
        ),
        "equations": {
            "satellite_pv_from_tle_sgp4": "(p_i, v_i) = SGP4(TLE, t_i)   # ECEF satellite position and velocity at epoch t_i",
            "range": "rho_i(x) = || p_i - s(x) ||_2   # s(x) = endpoint ECEF position",
            "los_unit_vector": "u_i(x) = (p_i - s(x)) / || p_i - s(x) ||_2",
            "range_rate": "rho_dot_i(x) = u_i(x)^T (v_i - v_s(x))   # v_s(x) ~ 0 for static endpoint",
            "doppler": "f_D,i(x) = -(f_c / c) * rho_dot_i(x)",
            "frequency_observation": "y_f,i = f_D,i(x) + b + d * (t_i - t_0) + e_f,i   # b = CFO, d = oscillator drift",
            "timing_observation_optional": "y_t,i = rho_i(x)/c + tau_0 + tau_d * (t_i - t_0) + e_t,i   # tau_0 clock offset, tau_d clock drift",
            "stacked_model": "y = h(x) + A eta + epsilon   # h(x) geometry terms, A nuisance design matrix, epsilon ~ N(0, Sigma)",
            "nuisance_projection": "P_perp = I - A (A^T Sigma^-1 A)^-1 A^T Sigma^-1   # projector orthogonal to nuisance subspace",
            "projected_residual": "r(x) = P_perp (y - h(x))   # nuisance-marginalized residual",
            "jacobian": "J(x) = d h(x) / d x",
            "projected_fisher_information": "F(x) = J(x)^T P_perp^T Sigma^-1 P_perp J(x)",
            "dtoi_definition": (
                "DTOI(x) = lambda_min( F_normalized(x) )  or  log10( cond(F(x))^-1 )   "
                "# observability index after nuisance projection; higher = more observable"
            ),
            "posterior_grid_inference": (
                "p(x | y) ∝ exp( -1/2 * r(x)^T Sigma^-1 r(x) ) * p(x)   # evaluated over a location grid"
            ),
            "roi_reduction_metrics": (
                "ROI = { x : p(x|y) in HPD_alpha };  entropy H = -sum p log p;  "
                "ROI_reduction = 1 - area(HPD_alpha) / area(prior)"
            ),
        },
        "model_keywords": ["DTOI", "nuisance projection", "Real-TLE", "posterior ROI reduction"],
    }


def method_stack() -> list[dict[str, str]]:
    return [
        {"stage": "input_data", "detail": "Real-TLE elements + sparse uplink packet timestamps for a satellite pass."},
        {"stage": "real_tle_orbit_model", "detail": "SGP4 propagation to ECEF satellite position/velocity at packet epochs."},
        {"stage": "sparse_packet_schedule", "detail": "Few packets per pass; schedule drives sampling of the Doppler-time curve."},
        {"stage": "doppler_time_feature_construction", "detail": "Build per-packet Doppler (and optional timing) features f_D,i, y_t,i."},
        {"stage": "nuisance_matrix", "detail": "Assemble A for CFO b, drift d, clock offset/drift over epochs."},
        {"stage": "projection", "detail": "Apply P_perp to marginalize nuisances from residuals."},
        {"stage": "dtoi", "detail": "Compute projected Fisher information and DTOI observability index."},
        {"stage": "posterior_roi_reduction", "detail": "Grid posterior over location; report HPD/entropy/ROI reduction."},
        {"stage": "claim_safe_outputs", "detail": "Emit diagnostic-only metrics; no localization-accuracy or hardware claims."},
    ]


def experiment_matrix(c23: dict[str, Any]) -> list[dict[str, Any]]:
    records = {r.get("phase"): r for r in c23.get("evidence_records", [])}

    def src(phase: str) -> str:
        rec = records.get(phase)
        return rec.get("source_path") if rec else "none (planned)"

    return [
        {
            "id": "E1", "name": "Real-TLE observability sweep",
            "purpose": "Map DTOI over endpoint grid and orbit geometry from Real-TLE passes.",
            "variables": ["endpoint location grid", "pass geometry", "packet count/schedule"],
            "metrics": ["DTOI", "fraction_observable", "projected Fisher eigenvalues"],
            "expected_claim": "Geometry-dependent observability is quantifiable as a diagnostic.",
            "forbidden_claim": "localization accuracy proven",
            "current_evidence_source": src("C19"),
            "missing_work": "Confirm Real-TLE (not synthetic-only) driving across more passes.",
        },
        {
            "id": "E2", "name": "DTOI vs baseline comparison",
            "purpose": "Show DTOI diverges from naive Doppler/SNR and matched-filter proxy baselines.",
            "variables": ["estimator type", "nuisance level"],
            "metrics": ["DTOI", "baseline separability", "mismatch rate"],
            "expected_claim": "DTOI captures observability that naive baselines miss.",
            "forbidden_claim": "meter-level localization",
            "current_evidence_source": src("C20"),
            "missing_work": "Broaden baseline set; document proxy assumptions.",
        },
        {
            "id": "E3", "name": "Oscillator/CFO/drift sensitivity",
            "purpose": "Stress-test DTOI under CFO/drift nuisance as a conservative proxy study.",
            "variables": ["CFO magnitude", "drift rate", "sampling balance"],
            "metrics": ["DTOI degradation", "observable fraction", "threshold crossings"],
            "expected_claim": "Sensitivity bounds are a proxy stress study only.",
            "forbidden_claim": "hardware oscillator specification derived",
            "current_evidence_source": src("C21"),
            "missing_work": "Tie proxy ranges to (later) measured hardware once captured.",
        },
        {
            "id": "E4", "name": "Geometry/placement robustness",
            "purpose": "Assess DTOI robustness to station/endpoint placement as a proxy study.",
            "variables": ["placement offset", "geometry diversity"],
            "metrics": ["DTOI variance", "observable fraction"],
            "expected_claim": "Placement robustness is a proxy study only.",
            "forbidden_claim": "surveyed station placement validation",
            "current_evidence_source": src("C22"),
            "missing_work": "Add adversarial/degenerate geometries.",
        },
        {
            "id": "E5", "name": "Ablation study",
            "purpose": "Quantify contribution of nuisance projection and timing channel to DTOI/ROI.",
            "variables": ["with/without P_perp", "with/without timing obs", "packet count"],
            "metrics": ["DTOI delta", "ROI_reduction delta"],
            "expected_claim": "Each modeling component has measurable diagnostic effect.",
            "forbidden_claim": "deployment-ready system",
            "current_evidence_source": "none (planned)",
            "missing_work": "Implement ablation harness over existing sweeps.",
        },
        {
            "id": "E6", "name": "Posterior ROI reduction and ambiguity analysis",
            "purpose": "Report posterior HPD/entropy ROI reduction and multimodal ambiguity.",
            "variables": ["pass count", "nuisance prior width", "grid resolution"],
            "metrics": ["ROI_reduction", "posterior entropy", "number of modes"],
            "expected_claim": "Coarse ROI reduction is achievable as a diagnostic outcome.",
            "forbidden_claim": "sub-kilometer performance claim",
            "current_evidence_source": "none (planned)",
            "missing_work": "Implement posterior grid + HPD/entropy reporting.",
        },
    ]


def hardware_validation_roadmap() -> list[dict[str, Any]]:
    return [
        {
            "id": "H0", "name": "Board bring-up and correct firmware",
            "goal": "Burn correct firmware to the connected board; verify Tx packet source operation.",
            "required_hardware": ["LR1121/STM32 (Tx-only)", "Mac host", "serial/SWD programmer"],
            "required_metadata": ["firmware version/hash", "board ID", "serial log"],
            "success_criteria": "Reproducible packet emission with logged timestamps on serial.",
            "claim_allowed_after_completion": "Tx packet source is operational (engineering milestone).",
            "claim_still_forbidden": "completed HIL validation",
        },
        {
            "id": "H1", "name": "Conducted/shielded packet capture",
            "goal": "Capture packets over cable/attenuator or shielded path with USRP B210 (Rx-only).",
            "required_hardware": ["USRP B210 (Rx-only)", "attenuator/dummy load", "RF cabling"],
            "required_metadata": ["center frequency", "sample rate", "timestamps", "attenuation"],
            "success_criteria": "Repeatable IQ capture files with complete metadata.json.",
            "claim_allowed_after_completion": "Controlled conducted capture exists.",
            "claim_still_forbidden": "real satellite OTA validation",
        },
        {
            "id": "H2", "name": "IQ feature extraction",
            "goal": "Extract Doppler/CFO/delay features from captured IQ.",
            "required_hardware": ["captured IQ files"],
            "required_metadata": ["extraction config", "feature schema version"],
            "success_criteria": "Feature pipeline produces per-packet Doppler/timing estimates.",
            "claim_allowed_after_completion": "Hardware-derived features are extractable.",
            "claim_still_forbidden": "localization accuracy proven",
        },
        {
            "id": "H3", "name": "Hardware noise calibration against simulation assumptions",
            "goal": "Compare measured noise/CFO/drift ranges to simulation proxy assumptions.",
            "required_hardware": ["captured IQ + extracted features"],
            "required_metadata": ["measured noise stats", "CFO/drift estimates"],
            "success_criteria": "Documented match/mismatch between proxy ranges and measurement.",
            "claim_allowed_after_completion": "Proxy assumptions are calibrated against measurement.",
            "claim_still_forbidden": "hardware oscillator specification derived",
        },
        {
            "id": "H4", "name": "Controlled trace-driven HIL replay",
            "goal": "Replay Real-TLE traces through hardware path and compare to software diagnostics.",
            "required_hardware": ["full conducted/shielded setup", "trace replay tooling"],
            "required_metadata": ["run_id", "trace source", "comparison config"],
            "success_criteria": "Repeatable HIL runs agreeing with software DTOI trends.",
            "claim_allowed_after_completion": "Trace-driven HIL is demonstrated (controlled).",
            "claim_still_forbidden": "real satellite capture validated",
        },
        {
            "id": "H5", "name": "Real satellite OTA (later only)",
            "goal": "Plan live LEO passes only after controlled HIL is repeatable and licensed.",
            "required_hardware": ["licensed/authorized OTA setup", "antenna", "tracking"],
            "required_metadata": ["pass schedule", "regulatory authorization", "ground truth"],
            "success_criteria": "Authorized, repeatable OTA captures with ground-truth comparison.",
            "claim_allowed_after_completion": "OTA observability evidence (only if achieved).",
            "claim_still_forbidden": "deployment-ready system",
        },
    ]


def paper_outline() -> list[dict[str, Any]]:
    return [
        {"section": "Abstract", "section_goal": "State GNSS-free coarse ROI / DTOI observability framing.",
         "must_say": "GNSS-free coarse ROI; nuisance-aware; software/proxy evidence.",
         "must_not_say": "GPS replacement; localization accuracy proven.",
         "equations_or_figures_needed": ["none"]},
        {"section": "Introduction", "section_goal": "Motivate GNSS-free IoT localization need.",
         "must_say": "Direct-to-satellite IoT, GNSS-free constraint, observability question.",
         "must_not_say": "meter-level localization; deployment-ready.",
         "equations_or_figures_needed": ["system diagram"]},
        {"section": "Related Work", "section_goal": "Position vs Doppler localization and DTF prior art.",
         "must_say": "Distinction from completed-localization systems.",
         "must_not_say": "we outperform GNSS.",
         "equations_or_figures_needed": ["none"]},
        {"section": "System Model", "section_goal": "Define endpoint/satellite/link model.",
         "must_say": "Real-TLE/SGP4 geometry; sparse packets; static endpoint.",
         "must_not_say": "surveyed station placement validated.",
         "equations_or_figures_needed": ["range/range-rate/Doppler equations"]},
        {"section": "Doppler-Time Fingerprint Model", "section_goal": "Define DTF features.",
         "must_say": "Frequency (+optional timing) observation model with CFO/drift.",
         "must_not_say": "noise-free identifiability.",
         "equations_or_figures_needed": ["Doppler-time fingerprint figure", "stacked model eq"]},
        {"section": "Nuisance-Aware DTOI", "section_goal": "Define projection + DTOI.",
         "must_say": "P_perp projection; projected Fisher info; DTOI definition.",
         "must_not_say": "hardware oscillator spec derived.",
         "equations_or_figures_needed": ["nuisance projection geometry", "DTOI equation"]},
        {"section": "Real-TLE / PRGL scheduling context", "section_goal": "Explain Real-TLE driving and packet scheduling.",
         "must_say": "Real-TLE used; sparse schedule assumptions.",
         "must_not_say": "real satellite OTA validated.",
         "equations_or_figures_needed": ["pass/schedule figure"]},
        {"section": "Experiments", "section_goal": "Report E1-E6 software/proxy results.",
         "must_say": "diagnostic-only; proxy assumptions explicit.",
         "must_not_say": "localization accuracy proven; sub-kilometer performance.",
         "equations_or_figures_needed": ["DTOI vs baselines", "oscillator sensitivity", "geometry robustness", "posterior ROI reduction"]},
        {"section": "Trace-driven HIL Plan", "section_goal": "Describe planned Mac-based HIL (H0-H5).",
         "must_say": "planned/conducted/shielded; Tx-only/Rx-only; no OTA.",
         "must_not_say": "completed HIL validation.",
         "equations_or_figures_needed": ["hardware HIL plan diagram"]},
        {"section": "Limitations", "section_goal": "State software/proxy boundary explicitly.",
         "must_say": "no hardware validation; no OTA; coarse ROI only.",
         "must_not_say": "deployment-ready system.",
         "equations_or_figures_needed": ["evidence/claim boundary table"]},
        {"section": "Conclusion", "section_goal": "Summarize diagnostic contribution + roadmap.",
         "must_say": "DTOI observability diagnostic; hardware as future work.",
         "must_not_say": "GPS replacement achieved.",
         "equations_or_figures_needed": ["none"]},
    ]


def claim_boundary_table(c23: dict[str, Any]) -> list[dict[str, Any]]:
    safe = c23.get("safe_claims", [])
    rows = [
        {
            "claim": "GNSS-free coarse ROI reduction",
            "allowed_now": True,
            "evidence": "C19-C22 software/proxy sweeps + posterior plan (E6)",
            "required_future_evidence": "Hardware-calibrated noise (H3) for quantitative ROI claims",
            "safe_wording": "diagnostic coarse ROI reduction under proxy assumptions",
        },
        {
            "claim": "Nuisance-aware DTOI observability",
            "allowed_now": True,
            "evidence": "C20 baseline mismatch, C21/C21B sensitivity, C22 geometry",
            "required_future_evidence": "none for diagnostic framing",
            "safe_wording": "nuisance-aware observability diagnostic",
        },
        {
            "claim": "Real-TLE orbit-driven proxy experiments",
            "allowed_now": True,
            "evidence": "C19 orbit parameter sweep",
            "required_future_evidence": "Broader Real-TLE pass coverage",
            "safe_wording": "Real-TLE-driven software/proxy study",
        },
        {
            "claim": "completed HIL validation",
            "allowed_now": False,
            "evidence": "none",
            "required_future_evidence": "H0-H4 repeatable controlled capture",
            "safe_wording": "planned trace-driven HIL workflow",
        },
        {
            "claim": "real satellite OTA validation",
            "allowed_now": False,
            "evidence": "none",
            "required_future_evidence": "H5 authorized OTA passes with ground truth",
            "safe_wording": "future OTA validation (not performed)",
        },
        {
            "claim": "localization accuracy proven / meter-level / sub-kilometer",
            "allowed_now": False,
            "evidence": "none",
            "required_future_evidence": "Hardware-validated estimation with ground truth",
            "safe_wording": "coarse ROI reduction diagnostic only",
        },
        {
            "claim": "deployment-ready system",
            "allowed_now": False,
            "evidence": "none",
            "required_future_evidence": "Full HIL + OTA + field trials",
            "safe_wording": "research prototype / diagnostic study",
        },
    ]
    return {"safe_claims_from_c23": safe, "rows": rows}


def figure_table_plan() -> list[dict[str, str]]:
    return [
        {"id": "F1", "kind": "figure", "name": "system diagram", "purpose": "GNSS-free IoT + LEO uplink overview."},
        {"id": "F2", "kind": "figure", "name": "Doppler-time fingerprint model", "purpose": "Show DTF curve vs sparse packets."},
        {"id": "F3", "kind": "figure", "name": "nuisance projection geometry", "purpose": "Illustrate P_perp removing nuisance subspace."},
        {"id": "F4", "kind": "figure", "name": "DTOI vs baselines", "purpose": "E2 comparison plot."},
        {"id": "F5", "kind": "figure", "name": "oscillator sensitivity", "purpose": "E3 DTOI vs CFO/drift."},
        {"id": "F6", "kind": "figure", "name": "geometry robustness", "purpose": "E4 DTOI vs placement."},
        {"id": "F7", "kind": "figure", "name": "posterior ROI reduction", "purpose": "E6 HPD/entropy map."},
        {"id": "F8", "kind": "figure", "name": "hardware HIL plan diagram", "purpose": "H0-H5 conducted/shielded setup."},
        {"id": "T1", "kind": "table", "name": "evidence/claim boundary table", "purpose": "Map claims to evidence and safe wording."},
    ]


def implementation_plan() -> list[dict[str, str]]:
    return [
        {"item": "software_experiment_completion", "detail": "Implement E5 ablation and E6 posterior ROI harness."},
        {"item": "paper_rewrite_branch", "detail": "Separate branch for skeleton rewrite AFTER blueprint review (C29)."},
        {"item": "hardware_mac_bringup", "detail": "H0 firmware burn + Tx verification on Mac (not container)."},
        {"item": "feature_extraction_pipeline", "detail": "H2 IQ -> Doppler/CFO/delay extraction tooling."},
        {"item": "metadata_schema_validation", "detail": "Validate data/hil_runs/{run_id}/metadata.json schema."},
        {"item": "controlled_capture_comparison", "detail": "H4 compare hardware features vs software DTOI trends."},
    ]


def final_recommendation(c25: dict[str, Any]) -> dict[str, Any]:
    return {
        "do_not_rewrite_paper_until_blueprint_reviewed": True,
        "do_not_claim_hardware_validation_before_mac_captures": True,
        "next_recommended_phase": (
            "After C28, choose C29 paper skeleton rewrite proposal OR H0 Mac bring-up checklist, "
            "depending on user priority."
        ),
        "statements": [
            "Do not rewrite paper until blueprint reviewed.",
            "Do not claim hardware validation before Mac captures.",
            "Next recommended phase after C28 is either C29 paper skeleton rewrite proposal or H0 Mac bring-up checklist, depending on user priority.",
        ],
        "c25_readiness_level": c25.get("readiness_assessment", {}).get("readiness_level"),
    }


def build_report() -> dict[str, Any]:
    c23 = load(C23)
    c24a = load(C24A)
    c24b = load(C24B_ALT)
    c25 = load(C25)
    c26 = load(C26)
    c27 = load_optional(C27)

    return {
        "metadata": {
            "phase": "C28",
            "generated_by": "research_theory_experiment_blueprint.py",
            "source_files_modified": False,
            "framing": "GNSS-free coarse ROI localization / nuisance-aware DTOI observability for low-cost direct-to-satellite IoT.",
            "inputs": {
                **{k: str(p.relative_to(ROOT)) for k, p in REQUIRED_INPUTS.items()},
                "C27": str(C27.relative_to(ROOT)) if c27 is not None else "not_available",
            },
            "hardware_validation_complete": False,
            "hil_validation_complete": False,
            "ota_validation_complete": False,
            "localization_accuracy_proven": False,
        },
        "final_problem_statement": final_problem_statement(),
        "revised_core_contributions": revised_core_contributions(),
        "non_contributions": non_contributions(),
        "mathematical_model": mathematical_model(),
        "method_stack": method_stack(),
        "experiment_matrix": experiment_matrix(c23),
        "hardware_validation_roadmap": hardware_validation_roadmap(),
        "paper_outline": paper_outline(),
        "claim_boundary_table": claim_boundary_table(c23),
        "figure_table_plan": figure_table_plan(),
        "implementation_plan": implementation_plan(),
        "final_recommendation": final_recommendation(c25),
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "theory_experiment_blueprint.json"
    md_path = out_dir / "theory_experiment_blueprint.md"

    json_path.write_text(json.dumps(report, indent=2))

    fps = report["final_problem_statement"]
    md = [
        "# C28 Theory and Experiment Blueprint",
        "",
        "Read-only re-derivation blueprint. Does not modify paper, docs, README, or workflows.",
        "Does not access hardware and does not claim HIL/OTA/localization validation.",
        "",
        "Framing: GNSS-free coarse ROI localization / nuisance-aware DTOI observability "
        "for low-cost direct-to-satellite IoT.",
        "",
        "## Final Problem Statement",
        "",
        f"- Context: {fps['problem_context']}",
        f"- Core problem: {fps['core_problem']}",
        f"- Why not GNSS: {fps['why_existing_gps_or_gnss_is_not_assumed']}",
        f"- Why naive Doppler insufficient: {fps['why_naive_doppler_is_insufficient']}",
        f"- One sentence: {fps['final_one_sentence_problem']}",
        "",
        "## Revised Core Contributions",
        "",
    ]
    for c in report["revised_core_contributions"]:
        md.append(f"- {c['id']} {c['name']}: {c['summary']}")

    md += ["", "## Non-Contributions", ""] + [f"- {n}" for n in report["non_contributions"]]

    md += ["", "## Mathematical Model", "", f"- Notation: {report['mathematical_model']['notation']}", ""]
    for k, v in report["mathematical_model"]["equations"].items():
        md.append(f"- `{k}`: {v}")

    md += ["", "## Method Stack", ""]
    for s in report["method_stack"]:
        md.append(f"- {s['stage']}: {s['detail']}")

    md += ["", "## Experiment Matrix", ""]
    for e in report["experiment_matrix"]:
        md.append(
            f"- {e['id']} {e['name']}: purpose={e['purpose']} | metrics={e['metrics']} | "
            f"expected={e['expected_claim']} | forbidden={e['forbidden_claim']} | "
            f"evidence={e['current_evidence_source']} | missing={e['missing_work']}"
        )

    md += ["", "## Hardware Validation Roadmap", ""]
    for h in report["hardware_validation_roadmap"]:
        md.append(
            f"- {h['id']} {h['name']}: goal={h['goal']} | success={h['success_criteria']} | "
            f"allowed_after={h['claim_allowed_after_completion']} | still_forbidden={h['claim_still_forbidden']}"
        )

    md += ["", "## Paper Outline", ""]
    for s in report["paper_outline"]:
        md.append(
            f"- {s['section']}: goal={s['section_goal']} | must_say={s['must_say']} | "
            f"must_not_say={s['must_not_say']} | needs={s['equations_or_figures_needed']}"
        )

    md += ["", "## Claim Boundary Table", "", "| claim | allowed_now | evidence | required_future_evidence | safe_wording |", "|---|---|---|---|---|"]
    for r in report["claim_boundary_table"]["rows"]:
        md.append(f"| {r['claim']} | {r['allowed_now']} | {r['evidence']} | {r['required_future_evidence']} | {r['safe_wording']} |")

    md += ["", "## Figure / Table Plan", ""]
    for f in report["figure_table_plan"]:
        md.append(f"- {f['id']} ({f['kind']}) {f['name']}: {f['purpose']}")

    md += ["", "## Implementation Plan", ""]
    for i in report["implementation_plan"]:
        md.append(f"- {i['item']}: {i['detail']}")

    md += ["", "## Final Recommendation", ""]
    for s in report["final_recommendation"]["statements"]:
        md.append(f"- {s}")

    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print("phase: C28 | hardware_validation_complete: False | hil: False | ota: False | localization_accuracy_proven: False")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate-missing", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()

    ensure_inputs(args.generate_missing)
    write_outputs(build_report(), args.output_dir)


if __name__ == "__main__":
    main()
