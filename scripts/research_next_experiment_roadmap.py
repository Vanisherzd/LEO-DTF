#!/usr/bin/env python3
"""
LEO-DTF Next Experiment Roadmap Generator (C18)

This script reads the postfix results table and claim boundary map to generate
a prioritized roadmap of candidate experiments for the next phases.

It does not modify any existing scripts or run new experiments.
"""

import json
import os
import csv
from pathlib import Path
from typing import Dict, List, Any, Optional

def read_json_file(path: Path) -> Optional[Dict]:
    """Read a JSON file and return its content, or None if missing/unreadable."""
    if not path.exists():
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to read JSON file {path}: {e}")
        return None

def main():
    base_dir = Path(__file__).parent.parent
    results_dir = base_dir / "experiments" / "results"
    output_dir = results_dir / "research_next_experiment_roadmap"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Input files
    postfix_results_path = results_dir / "research_postfix_results_table" / "postfix_results_table.json"
    claim_boundary_path = results_dir / "research_claim_boundary_map" / "claim_boundary_map.json"

    postfix_data = read_json_file(postfix_results_path)
    claim_boundary_data = read_json_file(claim_boundary_path)

    evidence_sources = []
    missing_inputs = []
    if postfix_data is not None:
        evidence_sources.append(str(postfix_results_path.relative_to(base_dir)))
    else:
        missing_inputs.append(str(postfix_results_path))
    if claim_boundary_data is not None:
        evidence_sources.append(str(claim_boundary_path.relative_to(base_dir)))
    else:
        missing_inputs.append(str(claim_boundary_path))

    # Define candidate experiments as per the task
    candidate_experiments = [
        {
            "id": "E1",
            "title": "Full TLE/SGP4 orbit-driven parameter sweep beyond quick mode",
            "category": "simulation",
            "question": "Does the post-fix orbit DTOI ≈ 3.04 remain stable across more carriers, offsets, durations, and seeds?",
            "why_it_matters": "Tests robustness of the orbit-driven diagnostic under varied synthetic conditions, increasing confidence in the diagnostic value.",
            "expected_artifacts": ["json", "md", "csv"],
            "paper_impact_score": 5,
            "claim_derisk_score": 5,
            "implementation_cost_score": 2,  # Low cost: just extend existing simulation scripts
            "ci_runtime_risk_score": 2,    # Low risk: similar to existing quick mode, just longer
            "interpretability_score": 5,
            "claim_boundary_effect": "Helps orbit-driven diagnostic robustness (conditional to safe).",
            "safe_constraints": "Must remain diagnostic-only; not to be construed as localization accuracy."
        },
        {
            "id": "E2",
            "title": "Oscillator phase-noise / CFO drift sensitivity sweep",
            "category": "sensitivity",
            "question": "How robust is the nuisance-aware DTOI under stronger or more realistic oscillator phase-noise and CFO drift models?",
            "why_it_matters": "Tests the limits of the nuisance projection under realistic error sources, which is critical for the diagnostic's credibility.",
            "expected_artifacts": ["json", "md", "csv"],
            "paper_impact_score": 5,
            "claim_derisk_score": 4,
            "implementation_cost_score": 3,  # Moderate: need to implement or import oscillator models
            "ci_runtime_risk_score": 3,    # Moderate: may increase runtime or numerical instability
            "interpretability_score": 4,
            "claim_boundary_effect": "Helps nuisance model robustness (supports safe claims about CFO/drift projection).",
            "safe_constraints": "Must remain diagnostic-only; not to be construed as validation of oscillator models."
        },
        {
            "id": "E3",
            "title": "Baseline comparison against naive Doppler estimator and simple matched-filter statistic",
            "category": "baseline",
            "question": "Does the DTOI diagnostic add value beyond simple Doppler magnitude or SNR-based methods?",
            "why_it_matters": "Establishes the novelty and utility of the DTOI approach compared to simpler, well-known methods.",
            "expected_artifacts": ["json", "md", "csv"],
            "paper_impact_score": 4,
            "claim_derisk_score": 5,
            "implementation_cost_score": 2,  # Low: implement naive estimators and compare
            "ci_runtime_risk_score": 2,    # Low: similar to existing diagnostics
            "interpretability_score": 5,
            "claim_boundary_effect": "Helps method comparison / baseline credibility (supports safe claims about diagnostic value).",
            "safe_constraints": "Must remain diagnostic-only; not to be construed as proving superiority in localization."
        },
        {
            "id": "E4",
            "title": "Receiver geometry and station placement robustness",
            "category": "simulation",
            "question": "How does the DTOI diagnostic respond to different ground station latitudes/longitudes, east/north offsets, and elevation windows?",
            "why_it_matters": "Tests the generality of the diagnostic across different geometries, which is important for real-world applicability.",
            "expected_artifacts": ["json", "md", "csv"],
            "paper_impact_score": 4,
            "claim_derisk_score": 4,
            "implementation_cost_score": 3,  # Moderate: need to loop over geometry parameters
            "ci_runtime_risk_score": 3,    # Moderate: more simulations
            "interpretability_score": 4,
            "claim_boundary_effect": "Helps geometry generality (supports safe claims about geometry diversity improving DTOI).",
            "safe_constraints": "Must remain diagnostic-only; not to be construed as proving real-world geometry robustness."
        },
        {
            "id": "E5",
            "title": "Packet sparsity and observation duration joint sweep",
            "category": "diagnostic",
            "question": "How do packet count and observation duration jointly affect DTOI in the orbit-driven differential Doppler diagnostic?",
            "why_it_matters": "Connects the packet budget diagnostic (C4) with the orbit-driven diagnostic, showing interplay between resources and observability.",
            "expected_artifacts": ["json", "md", "csv"],
            "paper_impact_score": 3,
            "claim_derisk_score": 3,
            "implementation_cost_score": 3,  # Moderate: nested loops over packet count and duration
            "ci_runtime_risk_score": 3,    # Moderate: more simulations
            "interpretability_score": 4,
            "claim_boundary_effect": "Helps packet budget realism (supports safe claims about carrier frequency and observation duration influencing DTOI).",
            "safe_constraints": "Must remain diagnostic-only; not to be construed as proving real-world packet scheduling benefits."
        },
        {
            "id": "E6",
            "title": "Real SDR capture or recorded RF trace validation",
            "category": "hardware_dependent",
            "question": "Can the DTOI diagnostic be applied to real satellite signals captured by an SDR or from recorded RF traces?",
            "why_it_matters": "Moves the diagnostic from synthetic to real-world signals, a critical step toward OTA validation.",
            "expected_artifacts": ["json", "md", "csv"],
            "paper_impact_score": 5,
            "claim_derisk_score": 5,
            "implementation_cost_score": 5,  # High: requires hardware, software, and real signal processing
            "ci_runtime_risk_score": 4,    # High: hardware setup may be unreliable, long runtime for capture and processing
            "interpretability_score": 4,
            "claim_boundary_effect": "Helps OTA validation but requires real RF trace (moves needs_next_experiment toward safe/conditional).",
            "safe_constraints": "Must be clearly labeled as experimental/validation; not to be construed as proven OTA capability without statistical significance."
        },
        {
            "id": "E7",
            "title": "Hardware-in-the-loop validation",
            "category": "hardware_dependent",
            "question": "Does the end-to-end hardware path (antenna, receiver, processing) produce DTOI diagnostics consistent with simulations?",
            "why_it_matters": "Validates the real hardware implementation, which is necessary for any claim of practical utility.",
            "expected_artifacts": ["json", "md", "csv"],
            "paper_impact_score": 5,
            "claim_derisk_score": 5,
            "implementation_cost_score": 5,  # High: requires HIL setup
            "ci_runtime_risk_score": 5,    # High: HIL tests can be unpredictable and slow
            "interpretability_score": 4,
            "claim_boundary_effect": "Helps HIL but requires hardware pipeline (moves needs_next_experiment toward safe/conditional).",
            "safe_constraints": "Must be clearly labeled as validation; not to be construed as proven hardware readiness without repeatable results."
        },
        {
            "id": "E8",
            "title": "Localization estimator accuracy experiment",
            "category": "simulation",
            "question": "Can an estimator using DTOI as a feature achieve localization accuracy under simulated conditions?",
            "why_it_matters": "Explores whether the DTOI diagnostic can be used as a basis for localization, moving from observability to estimation.",
            "expected_artifacts": ["json", "md", "csv"],
            "paper_impact_score": 4,
            "claim_derisk_score": 3,  # This experiment risks moving toward localization claims, which must be carefully framed
            "implementation_cost_score": 4,  # High: need to design and implement an estimator
            "ci_runtime_risk_score": 4,    # High: estimator may not converge, long runtime
            "interpretability_score": 3,
            "claim_boundary_effect": "Helps localization accuracy but requires estimator design and ground truth (moves needs_next_experiment toward conditional, but with caution).",
            "safe_constraints": "Must be clearly labeled as exploratory and diagnostic-only; not to be construed as proving localization accuracy without rigorous validation."
        }
    ]

    # Calculate overall priority score for each candidate
    for exp in candidate_experiments:
        paper_impact = exp["paper_impact_score"]
        claim_derisk = exp["claim_derisk_score"]
        interpretability = exp["interpretability_score"]
        impl_cost = exp["implementation_cost_score"]
        ci_risk = exp["ci_runtime_risk_score"]
        overall = (0.30 * paper_impact) + (0.30 * claim_derisk) + (0.20 * interpretability) - (0.10 * impl_cost) - (0.10 * ci_risk)
        exp["overall_priority_score"] = round(overall, 2)

        # Determine recommended phase based on score and category
        # Assign deterministic roadmap phases.
    # C18 is the roadmap generator itself, so the next executable experiment
    # should start at C19. Hardware-dependent or accuracy-claim experiments
    # remain deferred/blocked until the required evidence path exists.
    phase_map = {
        "E1": "C19",
        "E3": "C20",
        "E2": "C21",
        "E4": "C22",
        "E5": "C23",
        "E6": "deferred",
        "E7": "blocked",
        "E8": "deferred",
    }
    for exp in candidate_experiments:
        exp["recommended_phase"] = phase_map.get(exp["id"], "deferred")

    # Sort by overall_priority_score descending after deterministic phase assignment.
    priority_ranking = sorted(
        candidate_experiments,
        key=lambda x: x["overall_priority_score"],
        reverse=True,
    )

    # Determine immediate next phase: C18 is the roadmap generator, so the next
    # executable experiment starts at C19.
    # Since we sorted, the first element is the highest.
    immediate_next_phase = "C19"

    # Recommended sequence: we'll take the top 5 experiments in order for the sequence.
    recommended_sequence = [exp["id"] for exp in priority_ranking[:5]]

    # Deferred experiments: those that are hardware_dependent or have high cost/risk and are not top priority.
    # Specifically, we know E6 (SDR), E7 (HIL), and E8 (localization estimator) should be deferred unless hardware exists.
    # We'll mark as deferred if category is hardware_dependent or if the title matches E8.
    deferred_experiments = []
    blocked_experiments = []
    for exp in candidate_experiments:
        if exp["category"] == "hardware_dependent":
            # HIL (E7) is blocked unless we have a hardware pipeline (we don't, per the project's stance)
            if exp["id"] == "E7":
                blocked_experiments.append(exp["id"])
            else:
                deferred_experiments.append(exp["id"])
        elif exp["id"] == "E8":
            deferred_experiments.append(exp["id"])

    # Claim de-risking map: map each experiment ID to its claim_boundary_effect
    claim_de_risking_map = {exp["id"]: exp["claim_boundary_effect"] for exp in candidate_experiments}

    # CI safety notes
    ci_safety_notes = [
        "Keep quick smoke tests separate from long experiments to avoid CI timeouts.",
        "Ensure that any new simulation scripts are added to the existing test suite with appropriate markers.",
        "Monitor resource usage (memory, CPU) for parameter sweeps.",
        "Do not modify the core estimator or forbidden scripts when adding new experiments."
    ]

    # Assemble the final JSON
    output_json = {
        "metadata": {
            "generated_by": "research_next_experiment_roadmap.py",
            "base_dir": str(base_dir),
            "results_dir": str(results_dir),
            "output_dir": str(output_dir)
        },
        "evidence_sources": evidence_sources,
        "candidate_experiments": candidate_experiments,
        "priority_ranking": priority_ranking,
        "recommended_sequence": recommended_sequence,
        "immediate_next_phase": immediate_next_phase,
        "deferred_experiments": deferred_experiments,
        "blocked_experiments": blocked_experiments,
        "claim_de_risking_map": claim_de_risking_map,
        "ci_safety_notes": ci_safety_notes,
        "missing_inputs": missing_inputs
    }

    # Write JSON
    json_out = output_dir / "next_experiment_roadmap.json"
    with open(json_out, 'w') as f:
        json.dump(output_json, f, indent=2)
    print(f"JSON roadmap written to: {json_out}")

    # Write Markdown
    md_out = output_dir / "next_experiment_roadmap.md"
    with open(md_out, 'w') as f:
        f.write("# LEO-DTF Next Experiment Roadmap (C18)\\n\\n")
        f.write("## Evidence Sources\\n\\n")
        for src in evidence_sources:
            f.write(f"- {src}\\n")
        if missing_inputs:
            f.write("\\n## Missing Inputs\\n\\n")
            for missing in missing_inputs:
                f.write(f"- {missing}\\n")
        f.write("\\n")
        f.write("## Candidate Experiments\\n\\n")
        f.write("| ID | Title | Category | Question | Paper Impact | Claim Derisk | Implement Cost | CI Runtime Risk | Interpretability | Overall Priority |\\n")
        f.write("|----|-------|----------|----------|--------------|--------------|----------------|-----------------|------------------|------------------|\\n")
        for exp in candidate_experiments:
            f.write(f"| {exp['id']} | {exp['title']} | {exp['category']} | {exp['question']} | {exp['paper_impact_score']} | {exp['claim_derisk_score']} | {exp['implementation_cost_score']} | {exp['ci_runtime_risk_score']} | {exp['interpretability_score']} | {exp['overall_priority_score']} |\\n")
        f.write("\\n")
        f.write("## Priority Ranking (Highest to Lowest)\\n\\n")
        for i, exp in enumerate(priority_ranking, 1):
            f.write(f"{i}. **{exp['id']}**: {exp['title']} (Score: {exp['overall_priority_score']})\\n")
        f.write("\\n")
        f.write("## Recommended Sequence\\n\\n")
        f.write("The recommended sequence of phases to run, based on priority:\\n\\n")
        for phase_id in recommended_sequence:
            # Find the experiment with this id
            exp = next((e for e in candidate_experiments if e["id"] == phase_id), None)
            if exp:
                f.write(f"- **Phase {exp['recommended_phase']}**: {exp['title']}\\n")
        f.write("\\n")
        f.write("## Immediate Next Phase\\n\\n")
        f.write(f"The immediate next phase should be **{immediate_next_phase}**, starting with the highest priority experiment: **{priority_ranking[0]['id']}** - {priority_ranking[0]['title']}.\\n\\n")
        f.write("## Deferred Experiments\\n\\n")
        f.write("These experiments are deferred due to hardware dependencies, high cost, or the need for careful framing:\\n\\n")
        for exp_id in deferred_experiments:
            exp = next((e for e in candidate_experiments if e["id"] == exp_id), None)
            if exp:
                f.write(f"- {exp['id']}: {exp['title']}\\n")
        f.write("\\n")
        f.write("## Blocked Experiments\\n\\n")
        f.write("These experiments are blocked until the necessary infrastructure or pipeline is available:\\n\\n")
        for exp_id in blocked_experiments:
            exp = next((e for e in candidate_experiments if e["id"] == exp_id), None)
            if exp:
                f.write(f"- {exp['id']}: {exp['title']}\\n")
        f.write("\\n")
        f.write("## Claim De-Risking Map\\n\\n")
        for exp_id, effect in claim_de_risking_map.items():
            f.write(f"- **{exp_id}**: {effect}\\n")
        f.write("\\n")
        f.write("## CI Safety Notes\\n\\n")
        for note in ci_safety_notes:
            f.write(f"- {note}\\n")
        f.write("\\n")
        f.write("## Conservative Warning\\n\\n")
        f.write("This roadmap does not create OTA, HIL, or localization evidence by itself. All experiments must be framed as diagnostic or sensitivity studies unless otherwise validated.\\n")
    print(f"Markdown roadmap written to: {md_out}")

    # Write CSV
    csv_out = output_dir / "next_experiment_roadmap.csv"
    with open(csv_out, 'w', newline='') as f:
        # We'll write the candidate experiments with the calculated overall_priority_score and recommended_phase
        fieldnames = ["id", "title", "category", "question", "why_it_matters", "expected_artifacts",
                      "paper_impact_score", "claim_derisk_score", "implementation_cost_score",
                      "ci_runtime_risk_score", "interpretability_score", "overall_priority_score",
                      "claim_boundary_effect", "safe_constraints", "recommended_phase"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for exp in candidate_experiments:
            row = exp.copy()
            # Convert list to string for CSV
            row["expected_artifacts"] = ", ".join(row["expected_artifacts"])
            writer.writerow(row)
    print(f"CSV roadmap written to: {csv_out}")

if __name__ == "__main__":
    main()