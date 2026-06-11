#!/usr/bin/env python3
"""C24A: Triage claim/evidence audit findings without modifying docs."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "experiments/results/research_claim_evidence_audit/claim_evidence_audit.json"
DEFAULT_OUT = ROOT / "experiments/results/research_claim_audit_triage"

FORBIDDEN_HINTS = [
    "forbidden", "unsafe", "do not claim", "cannot claim", "not claimable",
    "prohibited", "overclaim", "risk", "absent", "must not", "should not",
]
PLANNED_HINTS = [
    "plan", "planned", "future", "todo", "pending", "not yet",
    "roadmap", "proposed", "next step", "will be",
]
HARDWARE_HINTS = [
    "protocol", "checklist", "bring-up", "bringup", "capture", "hil",
    "safety", "validation plan", "hardware",
]
TRUE_OVERCLAIM_HINTS = [
    "validated", "completed", "confirmed", "demonstrated",
    "achieved", "shows", "proves", "we have",
]

REWRITE_RULES = {
    "OTA validation": "planned OTA/HIL validation or no OTA validation claimed",
    "HIL validation": "planned/pending HIL validation or no HIL validation claimed",
    "localization accuracy": "DTOI observability diagnostic; no localization accuracy claimed",
    "meter-level localization": "do not use; replace with observability characterization",
    "deployment-ready": "research diagnostic prototype only",
    "hardware oscillator specification": "proxy threshold only, not hardware spec",
    "surveyed station placement": "geometry proxy only",
}


def run_audit_if_missing(input_path: Path) -> None:
    if input_path.exists():
        return
    cmd = [
        sys.executable,
        str(ROOT / "scripts/research_claim_evidence_audit.py"),
        "--include",
        "README.md",
        "docs",
        "paper",
    ]
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)


def read_context(base_dir: Path, rel_path: str, line: int) -> tuple[list[str], str, list[str]]:
    path = base_dir / rel_path
    if not path.exists():
        return [], f"[missing file: {rel_path}]", []
    lines = path.read_text(errors="ignore").splitlines()
    idx = max(0, line - 1)
    before = lines[max(0, idx - 2):idx]
    center = lines[idx] if idx < len(lines) else "[line out of range]"
    after = lines[idx + 1:idx + 3]
    return before, center, after


def contains_any(text: str, hints: list[str]) -> bool:
    low = text.lower()
    return any(h in low for h in hints)


def suggested_rewrite(hit: dict[str, Any], category: str) -> str:
    pid = hit.get("pattern_id", "")
    if "ota" in pid:
        return "Replace with: diagnostic/proxy evidence only; no OTA validation is claimed."
    if "hil" in pid:
        return "Replace with: HIL validation is planned/pending, not completed."
    if "localization" in pid:
        return "Replace with: DTOI observability diagnostic; no localization accuracy is claimed."
    if "meter" in pid:
        return "Replace with: observability characterization; do not use meter-level localization wording."
    if "deployment" in pid:
        return "Replace with: research diagnostic prototype only; not deployment-ready."
    if "oscillator" in pid:
        return "Replace with: oscillator proxy threshold only; not a hardware oscillator specification."
    if "station" in pid:
        return "Replace with: geometry proxy robustness; not surveyed station placement validation."
    return f"Review manually under category: {category}."


def classify(hit: dict[str, Any], before: list[str], center: str, after: list[str]) -> tuple[str, str]:
    context = "\n".join(before + [center] + after)
    path = hit.get("path", "")

    if contains_any(context, FORBIDDEN_HINTS):
        return "likely_false_positive_forbidden_list", "Context appears to list forbidden/unsafe claims rather than assert them."
    if contains_any(context, PLANNED_HINTS):
        return "planned_or_future_work_context", "Context appears planned, pending, proposed, or future work."
    if path.startswith("docs/hardware/") and contains_any(context, HARDWARE_HINTS):
        return "hardware_protocol_context_needs_guarded_wording", "Hardware/protocol context should use guarded planned/pending wording."
    if contains_any(context, TRUE_OVERCLAIM_HINTS):
        return "likely_true_overclaim", "Context contains positive completion/validation/proof wording."
    return "needs_manual_review", "No strong false-positive or planned-work cue was detected."


def action_for_path(categories: set[str]) -> str:
    if categories <= {"likely_false_positive_forbidden_list"}:
        return "no_edit_likely_needed_for_forbidden_list"
    if "likely_true_overclaim" in categories:
        return "manually_rewrite_overclaim"
    if "hardware_protocol_context_needs_guarded_wording" in categories:
        return "add_guarded_wording"
    return "manual_review_required"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--base-dir", type=Path, default=ROOT)
    args = parser.parse_args()

    run_audit_if_missing(args.input)
    audit = json.loads(args.input.read_text())
    hits = audit.get("unsafe_hits", [])

    records = []
    for hit in hits:
        before, center, after = read_context(args.base_dir, hit["path"], int(hit["line"]))
        category, rationale = classify(hit, before, center, after)
        records.append({
            "path": hit["path"],
            "line": hit["line"],
            "pattern_id": hit["pattern_id"],
            "matched_text": hit["matched_text"],
            "severity": hit["severity"],
            "triage_category": category,
            "context_before": "\n".join(before),
            "context_line": center,
            "context_after": "\n".join(after),
            "rationale": rationale,
            "suggested_safe_rewrite": suggested_rewrite(hit, category),
        })

    counts = dict(Counter(r["triage_category"] for r in records))

    by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_path[record["path"]].append(record)

    recommended_doc_actions = []
    for path, rs in sorted(by_path.items()):
        categories = {r["triage_category"] for r in rs}
        recommended_doc_actions.append({
            "path": path,
            "total_hits": len(rs),
            "categories": sorted(categories),
            "action": action_for_path(categories),
        })

    safe_claim_boundary = {
        "diagnostic_only": True,
        "no_OTA_validation": True,
        "no_HIL_validation": True,
        "no_real_satellite_capture": True,
        "no_localization_accuracy": True,
        "no_deployment_ready": True,
        "proxy_evidence_only": True,
    }

    true_count = counts.get("likely_true_overclaim", 0)
    manual_count = counts.get("needs_manual_review", 0)
    false_count = counts.get("likely_false_positive_forbidden_list", 0)
    if true_count > 0:
        next_action = "Recommend C24B conservative doc wording patch for likely true overclaims and guarded hardware wording."
    elif false_count == len(records):
        next_action = "Recommend improving C24 scanner negation/context heuristics before editing docs."
    elif manual_count > 0:
        next_action = "Recommend manual review before editing docs."
    else:
        next_action = "Proceed to conservative doc cleanup only where guarded wording is clearly needed."

    summary = {
        "metadata": {
            "generated_by": "research_claim_audit_triage.py",
            "phase": "C24A",
            "input_audit_path": str(args.input),
            "base_dir": str(args.base_dir),
        },
        "input_audit_path": str(args.input),
        "total_hits": len(records),
        "triage_counts": counts,
        "triage_records": records,
        "recommended_doc_actions": recommended_doc_actions,
        "conservative_rewrite_rules": REWRITE_RULES,
        "safe_claim_boundary": safe_claim_boundary,
        "recommended_next_action": next_action,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "claim_audit_triage.json"
    csv_path = args.output_dir / "claim_audit_triage.csv"
    md_path = args.output_dir / "claim_audit_triage.md"

    json_path.write_text(json.dumps(summary, indent=2))

    with csv_path.open("w", newline="") as f:
        fieldnames = [
            "path", "line", "pattern_id", "matched_text", "severity",
            "triage_category", "rationale", "suggested_safe_rewrite",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({k: record.get(k) for k in fieldnames})

    md_lines = [
        "# C24A Claim Audit Triage",
        "",
        f"- Total hits: {len(records)}",
        f"- Triage counts: {counts}",
        "",
        "## Recommended Doc Actions",
        "",
    ]
    for item in recommended_doc_actions:
        md_lines.append(f"- {item['path']}: {item['action']} ({item['total_hits']} hits; {item['categories']})")
    md_lines.extend(["", "## Conservative Rewrite Rules", ""])
    for k, v in REWRITE_RULES.items():
        md_lines.append(f"- {k}: {v}")
    md_lines.extend(["", "## Safe Claim Boundary", ""])
    for k, v in safe_claim_boundary.items():
        md_lines.append(f"- {k}: {v}")
    md_lines.extend(["", "## Recommended Next Action", "", next_action])
    md_path.write_text("\n".join(md_lines) + "\n")

    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Total hits: {len(records)}")
    print(f"Triage counts: {counts}")
    print(f"Recommended next action: {next_action}")


if __name__ == "__main__":
    main()
