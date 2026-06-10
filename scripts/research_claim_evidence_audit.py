#!/usr/bin/env python3
"""
C24: Claim/evidence audit scanner.

This script scans manuscript-facing text surfaces for overclaim wording and
maps them to the consolidated diagnostic-only evidence boundary.

It does not modify paper/docs/README. It only emits JSON/CSV/MD reports.

Safe framing:
- nuisance-aware DTOI observability diagnostic
- simulation/proxy evidence
- orbit-driven / oscillator-proxy / geometry-proxy diagnostics

Unsafe framing:
- OTA validation completed
- HIL validation completed
- real satellite capture validated
- localization accuracy proven
- meter-level localization proven
- deployment-ready system
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SCAN_TARGETS = [
    ROOT / "README.md",
    ROOT / "docs",
    ROOT / "paper",
]

EXCLUDE_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "experiments",
    "outputs",
    "results",
    "paper/figures",
    "paper/tables",
}

TEXT_SUFFIXES = {
    ".md",
    ".tex",
    ".txt",
    ".rst",
    ".bib",
}

NEGATION_HINTS = [
    "not ",
    "no ",
    "without ",
    "does not ",
    "do not ",
    "never ",
    "forbidden ",
    "unsafe ",
    "not claim",
    "cannot claim",
    "not evidence",
]


@dataclass(frozen=True)
class PatternSpec:
    pattern_id: str
    regex: str
    severity: str
    unsafe_claim: str
    safe_replacement: str


FORBIDDEN_PATTERNS = [
    PatternSpec(
        "ota_validation_completed",
        r"\bOTA validation(?:\s+(?:completed|validated|confirmed|done))?\b",
        "high",
        "OTA validation completed",
        "diagnostic/proxy evaluation only; no OTA validation",
    ),
    PatternSpec(
        "hil_validation_completed",
        r"\bHIL validation(?:\s+(?:completed|validated|confirmed|done))?\b",
        "high",
        "HIL validation completed",
        "diagnostic/proxy evaluation only; no HIL validation",
    ),
    PatternSpec(
        "real_satellite_capture_validated",
        r"\b(?:real\s+)?satellite capture(?:\s+(?:validated|confirmed|completed))?\b",
        "high",
        "real satellite capture validated",
        "orbit-driven simulation/proxy evidence only",
    ),
    PatternSpec(
        "localization_accuracy_proven",
        r"\blocalization accuracy(?:\s+(?:proven|validated|confirmed|demonstrated))?\b",
        "high",
        "localization accuracy proven",
        "observability diagnostic only; no localization-accuracy claim",
    ),
    PatternSpec(
        "meter_level_localization",
        r"\b(?:meter-level|meter level|sub-meter|sub meter)\s+localization\b",
        "high",
        "meter-level localization proven",
        "DTOI observability characterization only",
    ),
    PatternSpec(
        "deployment_ready",
        r"\bdeployment[- ]ready\b|\bready for deployment\b",
        "high",
        "deployment-ready system",
        "research diagnostic prototype only; not deployment-ready",
    ),
    PatternSpec(
        "hardware_oscillator_spec",
        r"\bhardware oscillator specification\b|\boscillator spec(?:ification)?\b",
        "medium",
        "hardware oscillator specification derived",
        "oscillator proxy sensitivity only; not hardware specification",
    ),
    PatternSpec(
        "surveyed_station_validation",
        r"\bsurveyed station placement(?:\s+(?:validated|confirmed|completed))?\b",
        "medium",
        "surveyed station placement validated",
        "geometry placement proxy only; not surveyed-station validation",
    ),
]

SAFE_PATTERNS = [
    r"nuisance-aware",
    r"observability diagnostic",
    r"diagnostic-only",
    r"simulation/proxy",
    r"proxy evidence",
    r"orbit-driven",
    r"oscillator proxy",
    r"geometry proxy",
    r"not OTA",
    r"not HIL",
    r"not localization",
]


def is_excluded(path: Path) -> bool:
    parts = set(path.relative_to(ROOT).parts) if path.is_relative_to(ROOT) else set(path.parts)
    if parts & EXCLUDE_DIR_NAMES:
        return True
    rel = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    if rel.startswith("experiments/") or rel.startswith("outputs/"):
        return True
    if rel.startswith("paper/figures/") or rel.startswith("paper/tables/"):
        return True
    return False


def iter_text_files(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if not target.exists():
            continue
        if target.is_file():
            if target.suffix in TEXT_SUFFIXES and not is_excluded(target):
                files.append(target)
            continue
        for path in target.rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES and not is_excluded(path):
                files.append(path)
    return sorted(set(files))


def has_negation_context(text: str, start: int) -> bool:
    window = text[max(0, start - 48):start].lower()
    return any(hint in window for hint in NEGATION_HINTS)


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def scan_file(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text = path.read_text(errors="ignore")
    unsafe_hits: list[dict[str, Any]] = []
    safe_hits: list[dict[str, Any]] = []

    for spec in FORBIDDEN_PATTERNS:
        for match in re.finditer(spec.regex, text, flags=re.IGNORECASE):
            negated = has_negation_context(text, match.start())
            hit = {
                "path": str(path.relative_to(ROOT)),
                "line": line_number(text, match.start()),
                "pattern_id": spec.pattern_id,
                "matched_text": match.group(0),
                "severity": spec.severity,
                "negated_or_guarded": negated,
                "unsafe_claim": spec.unsafe_claim,
                "safe_replacement": spec.safe_replacement,
            }
            if not negated:
                unsafe_hits.append(hit)
            else:
                safe_hits.append({**hit, "safe_context_type": "negated_forbidden_phrase"})

    for safe_regex in SAFE_PATTERNS:
        for match in re.finditer(safe_regex, text, flags=re.IGNORECASE):
            safe_hits.append({
                "path": str(path.relative_to(ROOT)),
                "line": line_number(text, match.start()),
                "pattern_id": "safe_framing",
                "matched_text": match.group(0),
                "safe_context_type": "safe_framing_phrase",
            })

    return unsafe_hits, safe_hits


def load_consolidated_evidence() -> dict[str, Any] | None:
    p = ROOT / "experiments/results/research_consolidated_evidence_table/consolidated_evidence_table.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include", nargs="*", default=None, help="Optional explicit scan targets.")
    parser.add_argument("--fail-on-unsafe", action="store_true")
    args = parser.parse_args()

    targets = [Path(x) if Path(x).is_absolute() else ROOT / x for x in args.include] if args.include else DEFAULT_SCAN_TARGETS
    files = iter_text_files(targets)

    unsafe_hits: list[dict[str, Any]] = []
    safe_hits: list[dict[str, Any]] = []
    for path in files:
        unsafe, safe = scan_file(path)
        unsafe_hits.extend(unsafe)
        safe_hits.extend(safe)

    evidence = load_consolidated_evidence()
    evidence_ready = bool(
        evidence
        and evidence.get("overall_assessment", {}).get("ready_for_claim_table_sync") is True
        and evidence.get("overall_assessment", {}).get("diagnostic_only") is True
    )

    unsafe_by_severity: dict[str, int] = {}
    for hit in unsafe_hits:
        unsafe_by_severity[hit["severity"]] = unsafe_by_severity.get(hit["severity"], 0) + 1

    recommended_actions = []
    if unsafe_hits:
        recommended_actions.append("Manually revise unsafe claim wording before paper-side synchronization.")
    if not evidence_ready:
        recommended_actions.append("Regenerate C23 consolidated evidence table before claim synchronization.")
    if not recommended_actions:
        recommended_actions.append("Proceed to manual paper-side claim/evidence synchronization with diagnostic-only wording.")

    summary = {
        "metadata": {
            "generated_by": "research_claim_evidence_audit.py",
            "phase": "C24",
            "scan_targets": [str(t.relative_to(ROOT)) if t.is_relative_to(ROOT) else str(t) for t in targets],
            "scanned_files": [str(p.relative_to(ROOT)) for p in files],
            "fail_on_unsafe": args.fail_on_unsafe,
        },
        "claim_boundary": {
            "allowed_framing": [
                "nuisance-aware DTOI observability diagnostic",
                "orbit-driven simulation/proxy evidence",
                "DTOI-vs-naive-baseline diagnostic comparison",
                "oscillator proxy sensitivity",
                "geometry placement proxy robustness",
            ],
            "forbidden_framing": [
                spec.unsafe_claim for spec in FORBIDDEN_PATTERNS
            ],
        },
        "evidence_status": {
            "c23_evidence_table_found": evidence is not None,
            "c23_ready_for_claim_table_sync": evidence_ready,
            "diagnostic_only": True,
        },
        "scan_summary": {
            "files_scanned": len(files),
            "unsafe_hit_count": len(unsafe_hits),
            "safe_hit_count": len(safe_hits),
            "unsafe_by_severity": unsafe_by_severity,
            "unsafe_free": len(unsafe_hits) == 0,
        },
        "unsafe_hits": unsafe_hits,
        "safe_hits_sample": safe_hits[:50],
        "recommended_actions": recommended_actions,
    }

    out_dir = ROOT / "experiments" / "results" / "research_claim_evidence_audit"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "claim_evidence_audit.json"
    csv_path = out_dir / "claim_evidence_audit_unsafe_hits.csv"
    md_path = out_dir / "claim_evidence_audit.md"

    json_path.write_text(json.dumps(summary, indent=2))

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "path",
                "line",
                "pattern_id",
                "matched_text",
                "severity",
                "unsafe_claim",
                "safe_replacement",
            ],
        )
        writer.writeheader()
        for hit in unsafe_hits:
            writer.writerow({k: hit.get(k) for k in writer.fieldnames})

    md_lines = [
        "# C24 Claim/Evidence Audit",
        "",
        "## Scan Summary",
        "",
    ]
    for k, v in summary["scan_summary"].items():
        md_lines.append(f"- {k}: {v}")
    md_lines.extend([
        "",
        "## Evidence Status",
        "",
    ])
    for k, v in summary["evidence_status"].items():
        md_lines.append(f"- {k}: {v}")
    md_lines.extend([
        "",
        "## Allowed Framing",
        "",
    ])
    for item in summary["claim_boundary"]["allowed_framing"]:
        md_lines.append(f"- {item}")
    md_lines.extend([
        "",
        "## Forbidden Framing",
        "",
    ])
    for item in summary["claim_boundary"]["forbidden_framing"]:
        md_lines.append(f"- {item}")
    md_lines.extend([
        "",
        "## Unsafe Hits",
        "",
    ])
    if unsafe_hits:
        for hit in unsafe_hits:
            md_lines.append(
                f"- {hit['path']}:{hit['line']} [{hit['severity']}] "
                f"{hit['pattern_id']} -> {hit['safe_replacement']}"
            )
    else:
        md_lines.append("None")
    md_lines.extend([
        "",
        "## Recommended Actions",
        "",
    ])
    for item in recommended_actions:
        md_lines.append(f"- {item}")
    md_lines.extend([
        "",
        "This audit does not modify manuscript files and does not create OTA, HIL, RF, deployment, or localization-accuracy evidence.",
    ])
    md_path.write_text("\n".join(md_lines) + "\n")

    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Files scanned: {len(files)}")
    print(f"Unsafe hits: {len(unsafe_hits)}")
    print(f"Evidence ready: {evidence_ready}")

    if args.fail_on_unsafe and unsafe_hits:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
