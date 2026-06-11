#!/usr/bin/env python3
"""C24B-alt: generate conservative doc patch proposal without editing docs/paper."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRIAGE = ROOT / "experiments/results/research_claim_audit_triage/claim_audit_triage.json"
DEFAULT_OUT = ROOT / "experiments/results/research_claim_patch_proposal"


PROPOSALS = {
    ("paper/sections/08_limitations.tex", "localization_accuracy_proven"): {
        "priority": "must_fix_before_submission",
        "reason": "Triage classified this as the only likely true overclaim.",
        "old_hint": "sub-kilometer localization accuracy requires timestamp precision",
        "suggested_rewrite": (
            "The current evidence supports DTOI observability and ROI-reduction "
            "diagnostics only. Fine-grained position-resolution or localization-"
            "performance claims would require additional timing, RF, and hardware "
            "validation beyond the current synthetic and trace-driven proxy evidence."
        ),
    },
    ("docs/hardware/hil_plan.md", "hil_validation_completed"): {
        "priority": "guarded_wording",
        "reason": "Avoid phrasing planned HIL work as completed validation.",
        "old_hint": "Before any HIL validation claim is made",
        "suggested_rewrite": (
            "Before any completed HIL-validation claim is made in the manuscript, "
            "the planned HIL workflow must first satisfy the following checklist."
        ),
    },
    ("docs/hardware/hil_plan.md", "localization_accuracy_proven"): {
        "priority": "guarded_wording",
        "reason": "Keep localization accuracy listed as not claimed.",
        "old_hint": "Meter-level or centimeter-level localization accuracy",
        "suggested_rewrite": "Meter-level or centimeter-level localization-accuracy claims.",
    },
    ("docs/hardware/lr1121_stm32_packet_source.md", "hil_validation_completed"): {
        "priority": "guarded_wording",
        "reason": "LR1121 packet source is design/planned workflow, not completed HIL validation.",
        "old_hint": "for LEO-DTF HIL validation",
        "suggested_rewrite": (
            "for the planned LEO-DTF trace-driven HIL-validation workflow."
        ),
    },
    ("docs/hardware/rf_safety_checklist.md", "hil_validation_completed"): {
        "priority": "guarded_wording",
        "reason": "Safety checklist should describe planned HIL-validation activity.",
        "old_hint": "conducting HIL validation",
        "suggested_rewrite": "conducting any planned HIL-validation activity",
    },
    ("docs/hardware/usrp_b210_capture_protocol.md", "hil_validation_completed"): {
        "priority": "guarded_wording",
        "reason": "USRP B210 protocol is part of planned workflow, not completed validation.",
        "old_hint": "in the LEO-DTF HIL validation plan",
        "suggested_rewrite": "in the planned LEO-DTF HIL-validation workflow",
    },
}


def load_triage(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing triage JSON: {path}. Run scripts/research_claim_audit_triage.py first."
        )
    return json.loads(path.read_text())


def fallback_proposal(record: dict[str, Any]) -> dict[str, str]:
    pid = record.get("pattern_id", "")
    if "ota" in pid:
        rewrite = "Use: diagnostic/proxy evidence only; no OTA validation is claimed."
    elif "hil" in pid:
        rewrite = "Use: planned/pending HIL-validation workflow; no completed HIL validation is claimed."
    elif "localization" in pid or "meter" in pid:
        rewrite = "Use: DTOI observability diagnostic; no localization accuracy is claimed."
    else:
        rewrite = "Review manually and keep diagnostic-only/proxy-only wording."

    return {
        "priority": "manual_review",
        "reason": "No file-specific proposal rule; manual review required.",
        "old_hint": record.get("matched_text", ""),
        "suggested_rewrite": rewrite,
    }


def proposal_for(record: dict[str, Any]) -> dict[str, Any]:
    key = (record["path"], record["pattern_id"])
    p = PROPOSALS.get(key, fallback_proposal(record))
    return {
        "path": record["path"],
        "line": record["line"],
        "pattern_id": record["pattern_id"],
        "matched_text": record["matched_text"],
        "triage_category": record["triage_category"],
        "priority": p["priority"],
        "reason": p["reason"],
        "old_hint": p["old_hint"],
        "context_line": record.get("context_line", ""),
        "suggested_rewrite": p["suggested_rewrite"],
        "source_is_not_modified": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--triage", type=Path, default=DEFAULT_TRIAGE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    triage = load_triage(args.triage)
    records = triage.get("triage_records", [])

    target_categories = {
        "likely_true_overclaim",
        "hardware_protocol_context_needs_guarded_wording",
        "planned_or_future_work_context",
        "needs_manual_review",
    }

    selected = [
        r for r in records
        if r.get("triage_category") in target_categories
        and (
            r.get("triage_category") == "likely_true_overclaim"
            or r.get("path", "").startswith("docs/hardware/")
            or r.get("path", "").startswith("paper/sections/")
        )
    ]

    proposals = [proposal_for(r) for r in selected]

    by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in proposals:
        by_path[p["path"]].append(p)

    priority_counts: dict[str, int] = defaultdict(int)
    category_counts: dict[str, int] = defaultdict(int)
    for p in proposals:
        priority_counts[p["priority"]] += 1
        category_counts[p["triage_category"]] += 1

    manual_apply_notes = [
        "This phase intentionally does not modify docs/ or paper/ files.",
        "Apply proposals manually only after reviewing context.",
        "Any applied wording must remain diagnostic-only and proxy-only.",
        "Do not convert planned HIL/OTA work into completed validation claims.",
        "Do not introduce localization accuracy, meter-level localization, deployment-ready, OTA, or HIL claims.",
    ]

    summary = {
        "metadata": {
            "generated_by": "research_claim_patch_proposal.py",
            "phase": "C24B-alt",
            "triage_input": str(args.triage),
            "source_files_modified": False,
        },
        "proposal_summary": {
            "total_triage_records": len(records),
            "selected_proposals": len(proposals),
            "priority_counts": dict(priority_counts),
            "category_counts": dict(category_counts),
            "paths_with_proposals": sorted(by_path.keys()),
        },
        "safe_claim_boundary": {
            "diagnostic_only": True,
            "proxy_evidence_only": True,
            "no_OTA_validation": True,
            "no_HIL_validation": True,
            "no_real_satellite_capture": True,
            "no_localization_accuracy": True,
            "no_meter_level_localization": True,
            "no_deployment_ready": True,
        },
        "patch_proposals": proposals,
        "manual_apply_notes": manual_apply_notes,
        "recommended_next_action": (
            "Review proposed wording manually; if accepted, apply as a separate human-approved docs/paper patch."
        ),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "claim_patch_proposal.json"
    md_path = args.output_dir / "claim_patch_proposal.md"

    json_path.write_text(json.dumps(summary, indent=2))

    md = [
        "# C24B-alt Conservative Claim Patch Proposal",
        "",
        "This report proposes wording changes only. It does not modify docs or paper files.",
        "",
        "## Summary",
        "",
        f"- Selected proposals: {len(proposals)}",
        f"- Priority counts: {dict(priority_counts)}",
        f"- Category counts: {dict(category_counts)}",
        "",
        "## Safe Claim Boundary",
        "",
    ]
    for k, v in summary["safe_claim_boundary"].items():
        md.append(f"- {k}: {v}")

    md.extend(["", "## Patch Proposals by File", ""])
    for path in sorted(by_path):
        md.append(f"### {path}")
        md.append("")
        for p in by_path[path]:
            md.extend([
                f"- Line: {p['line']}",
                f"- Pattern: `{p['pattern_id']}` / matched `{p['matched_text']}`",
                f"- Triage: {p['triage_category']}",
                f"- Priority: {p['priority']}",
                f"- Reason: {p['reason']}",
                f"- Old hint: `{p['old_hint']}`",
                "- Suggested rewrite:",
                "",
                f"> {p['suggested_rewrite']}",
                "",
            ])

    md.extend(["## Manual Apply Notes", ""])
    for note in manual_apply_notes:
        md.append(f"- {note}")

    md.extend(["", "## Recommended Next Action", "", summary["recommended_next_action"]])
    md_path.write_text("\n".join(md) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Selected proposals: {len(proposals)}")
    print(f"Priority counts: {dict(priority_counts)}")
    print(f"Recommended next action: {summary['recommended_next_action']}")


if __name__ == "__main__":
    main()
