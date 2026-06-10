#!/usr/bin/env python3
"""
Source-level orbit offset audit for LEO-DTF.

This script does not modify the C10 orbit bridge. It verifies whether a
nearby ground-station offset produces the expected ECEF distance and
differential Doppler scaling, and it also statically checks whether the
C10 orbit-driven branch appears to use offset_m.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from leodtf.frame_transform import geodetic_to_ecef, enu_to_ecef
from leodtf.observation_model import ObservationModel
from leodtf.orbit_propagation import propagate_orbit, HAS_SGP4

SIGMA_F_HZ = 1.0
OUTPUT_DIR = REPO_ROOT / "experiments/results/research_orbit_offset_source_audit"
C10_SCRIPT = REPO_ROOT / "scripts/research_orbit_trace_dtoi_bridge.py"

LINE1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
LINE2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"

LAT0_DEG = 40.0
LON0_DEG = -105.0
ALT0_KM = 0.0


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(x, dtype=float) ** 2)))


def project_affine(signal: np.ndarray, t: np.ndarray) -> np.ndarray:
    basis = np.column_stack([np.ones_like(t), t])
    coeff, _, _, _ = np.linalg.lstsq(basis, signal, rcond=None)
    return signal - basis @ coeff


def status_from_dtoi(dtoi: float) -> str:
    if dtoi < 0.5:
        return "unobservable"
    if dtoi < 1.0:
        return "weak"
    if dtoi < 2.0:
        return "moderate"
    return "strong"


def orbit_states(duration_s: int = 1800) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = int(duration_s)
    t = np.arange(n, dtype=float)
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_dt = [ref_time + timedelta(seconds=float(ti)) for ti in t]
    try:
        positions, velocities = propagate_orbit(LINE1, LINE2, times_dt)
        return t, np.asarray(positions, dtype=float), np.asarray(velocities, dtype=float)
    except Exception:
        # Conservative deterministic fallback: circular-ish motion in ECEF-like coordinates.
        # This is only for making the audit runnable if SGP4 is unavailable.
        omega = 2.0 * np.pi / 5400.0
        radius_km = 6871.0
        positions = np.column_stack([
            radius_km * np.cos(omega * t),
            radius_km * np.sin(omega * t),
            700.0 * np.sin(0.5 * omega * t),
        ])
        velocities = np.column_stack([
            -radius_km * omega * np.sin(omega * t),
            radius_km * omega * np.cos(omega * t),
            700.0 * 0.5 * omega * np.cos(0.5 * omega * t),
        ])
        return t, positions, velocities


def direct_differential_trial(carrier_hz: float, offset_m: float, duration_s: int = 1800) -> dict[str, Any]:
    t, positions, velocities = orbit_states(duration_s)
    base_ecef = np.asarray(geodetic_to_ecef(LAT0_DEG, LON0_DEG, ALT0_KM), dtype=float)

    offset_km_expected = float(offset_m) / 1000.0
    offset_ecef = np.asarray(
        enu_to_ecef(offset_km_expected, 0.0, 0.0, LAT0_DEG, LON0_DEG, ALT0_KM),
        dtype=float,
    )

    ecef_distance_km = float(np.linalg.norm(offset_ecef - base_ecef))
    ecef_distance_error_km = abs(ecef_distance_km - offset_km_expected)

    base_model = ObservationModel(base_ecef, carrier_freq_hz=carrier_hz)
    offset_model = ObservationModel(offset_ecef, carrier_freq_hz=carrier_hz)

    diff = np.zeros_like(t)
    for i in range(len(t)):
        state = (positions[i], velocities[i])
        base_doppler, _ = base_model.compute_expected_measurements(state, float(t[i]))
        offset_doppler, _ = offset_model.compute_expected_measurements(state, float(t[i]))
        diff[i] = offset_doppler - base_doppler

    projected = project_affine(diff, t)
    rms_diff_hz = rms(diff)
    projected_rms_hz = rms(projected)
    dtoi = projected_rms_hz / SIGMA_F_HZ

    distance_pass = ecef_distance_error_km <= max(0.05 * offset_km_expected, 1e-9)

    return {
        "carrier_hz": carrier_hz,
        "offset_m": offset_m,
        "offset_km_expected": offset_km_expected,
        "ecef_distance_km": ecef_distance_km,
        "ecef_distance_error_km": ecef_distance_error_km,
        "rms_diff_hz": rms_diff_hz,
        "max_abs_diff_hz": float(np.max(np.abs(diff))),
        "projected_rms_hz": projected_rms_hz,
        "dtoi": dtoi,
        "observability_status": status_from_dtoi(dtoi),
        "offset_distance_check": "PASS" if distance_pass else "FAIL",
        "rms_scaling_check": "BASELINE",
        "diagnostic_status": "computed_direct_differential_doppler",
    }


def check_ratio(actual: float, expected: float, tolerance: float = 0.35) -> str:
    if expected == 0:
        return "FAIL"
    rel_err = abs(actual - expected) / expected
    return "PASS" if rel_err <= tolerance else "FAIL"


def static_c10_offset_audit() -> dict[str, Any]:
    text = C10_SCRIPT.read_text(encoding="utf-8")
    match = re.search(
        r'elif\s+trace_source\s*==\s*"orbit_driven_fallback"\s*:(.*?)(?:\n\s*else\s*:|\n\s*# Add noise)',
        text,
        flags=re.S,
    )
    branch = match.group(1) if match else ""
    offset_mentions = branch.count("offset_m")
    uses_single_observation_model = "ObservationModel(gs_ecef" in branch
    computes_absolute_doppler_signal = "signal[i] = doppler_hz" in branch
    has_second_ground_station = any(
        token in branch
        for token in ["offset_ecef", "offset_model", "gs_ecef_offset", "doppler_offset"]
    )

    if offset_mentions == 0 and uses_single_observation_model and computes_absolute_doppler_signal:
        verdict = "C10_ORBIT_BRANCH_IGNORES_OFFSET_AND_USES_ABSOLUTE_DOPPLER"
    elif has_second_ground_station:
        verdict = "C10_ORBIT_BRANCH_APPEARS_TO_USE_DIFFERENTIAL_DOPPLER"
    else:
        verdict = "INCONCLUSIVE"

    return {
        "orbit_branch_found": bool(branch),
        "offset_m_mentions_in_orbit_branch": offset_mentions,
        "uses_single_observation_model": uses_single_observation_model,
        "computes_absolute_doppler_signal": computes_absolute_doppler_signal,
        "has_second_ground_station": has_second_ground_station,
        "verdict": verdict,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    carrier_hz = 2.4e9
    offsets_m = [100.0, 1000.0, 5000.0]
    rows = [direct_differential_trial(carrier_hz, offset) for offset in offsets_m]

    baseline = rows[0]["rms_diff_hz"]
    for row in rows:
        if row["offset_m"] == 100.0:
            row["rms_scaling_check"] = "BASELINE"
            row["rms_ratio_vs_100m"] = 1.0
            row["expected_rms_ratio_vs_100m"] = 1.0
        else:
            expected_ratio = row["offset_m"] / 100.0
            actual_ratio = row["rms_diff_hz"] / baseline if baseline > 0 else float("nan")
            row["rms_ratio_vs_100m"] = actual_ratio
            row["expected_rms_ratio_vs_100m"] = expected_ratio
            row["rms_scaling_check"] = check_ratio(actual_ratio, expected_ratio)

    csv_path = OUTPUT_DIR / "orbit_offset_source_trials.csv"
    fieldnames = [
        "carrier_hz",
        "offset_m",
        "offset_km_expected",
        "ecef_distance_km",
        "ecef_distance_error_km",
        "rms_diff_hz",
        "max_abs_diff_hz",
        "projected_rms_hz",
        "dtoi",
        "observability_status",
        "offset_distance_check",
        "rms_ratio_vs_100m",
        "expected_rms_ratio_vs_100m",
        "rms_scaling_check",
        "diagnostic_status",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    static_audit = static_c10_offset_audit()
    suspicious_flags: list[str] = []

    if any(row["offset_distance_check"] == "FAIL" for row in rows):
        suspicious_flags.append("ecef_offset_distance_failed")
    if any(row["rms_scaling_check"] == "FAIL" for row in rows):
        suspicious_flags.append("direct_differential_rms_scaling_failed")
    if static_audit["verdict"] == "C10_ORBIT_BRANCH_IGNORES_OFFSET_AND_USES_ABSOLUTE_DOPPLER":
        suspicious_flags.append("c10_orbit_branch_ignores_offset_m")
        suspicious_flags.append("c10_orbit_branch_uses_absolute_doppler")

    distance_all_pass = all(row["offset_distance_check"] != "FAIL" for row in rows)
    rms_all_pass = all(row["rms_scaling_check"] != "FAIL" for row in rows)

    if static_audit["verdict"] == "C10_ORBIT_BRANCH_IGNORES_OFFSET_AND_USES_ABSOLUTE_DOPPLER":
        likely_failure_location = "scripts/research_orbit_trace_dtoi_bridge.py orbit_driven_fallback branch"
        bug_likelihood = "HIGH"
        recommended_next_action = (
            "Patch C10 so orbit_driven_fallback computes Doppler difference between baseline and "
            "offset ground stations, then rerun C10/C10A/C11."
        )
    elif distance_all_pass and rms_all_pass:
        likely_failure_location = "C10 bridge source offset construction appears sane; C11 artifact logic may be wrong."
        bug_likelihood = "LOW_FOR_DIRECT_DIFFERENTIAL_CALCULATION"
        recommended_next_action = "Inspect C11 artifact selection and then patch C10 if static audit still flags absolute Doppler."
    elif distance_all_pass and not rms_all_pass:
        likely_failure_location = "Doppler calculation or artifact selection"
        bug_likelihood = "MEDIUM"
        recommended_next_action = "Inspect differential Doppler computation and artifact grouping."
    else:
        likely_failure_location = "ENU/ECEF offset construction"
        bug_likelihood = "HIGH"
        recommended_next_action = "Fix ENU/ECEF offset application before using C10."

    summary = {
        "metadata": {
            "carrier_hz": carrier_hz,
            "duration_s": 1800,
            "sigma_f_hz": SIGMA_F_HZ,
            "has_sgp4": bool(HAS_SGP4),
            "total_rows": len(rows),
        },
        "unit_distance_checks": [
            {
                "offset_m": row["offset_m"],
                "offset_km_expected": row["offset_km_expected"],
                "ecef_distance_km": row["ecef_distance_km"],
                "ecef_distance_error_km": row["ecef_distance_error_km"],
                "status": row["offset_distance_check"],
            }
            for row in rows
        ],
        "rms_scaling_checks": [
            {
                "offset_m": row["offset_m"],
                "rms_diff_hz": row["rms_diff_hz"],
                "rms_ratio_vs_100m": row["rms_ratio_vs_100m"],
                "expected_rms_ratio_vs_100m": row["expected_rms_ratio_vs_100m"],
                "status": row["rms_scaling_check"],
            }
            for row in rows
        ],
        "best_row": max(rows, key=lambda row: row["dtoi"]),
        "c10_static_source_audit": static_audit,
        "suspicious_flags": suspicious_flags,
        "bug_likelihood": bug_likelihood,
        "likely_failure_location": likely_failure_location,
        "conservative_interpretation": (
            "This is not OTA validation and does not prove localization accuracy. "
            "C10 DTOI remains unusable until offset scaling is resolved. "
            "If the C10 orbit branch ignores offset_m or uses absolute Doppler, C10 must be corrected or excluded."
        ),
        "recommended_next_action": recommended_next_action,
    }

    json_path = OUTPUT_DIR / "orbit_offset_source_audit.json"
    md_path = OUTPUT_DIR / "orbit_offset_source_audit.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_lines = [
        "# Orbit Offset Source Audit",
        "",
        f"- Bug likelihood: {bug_likelihood}",
        f"- Likely failure location: {likely_failure_location}",
        f"- Suspicious flags: {', '.join(suspicious_flags) if suspicious_flags else 'none'}",
        "",
        "## Static C10 audit",
        f"- Verdict: {static_audit['verdict']}",
        f"- offset_m mentions in orbit branch: {static_audit['offset_m_mentions_in_orbit_branch']}",
        f"- uses single ObservationModel: {static_audit['uses_single_observation_model']}",
        f"- computes absolute Doppler signal: {static_audit['computes_absolute_doppler_signal']}",
        "",
        "## Conservative interpretation",
        summary["conservative_interpretation"],
        "",
        "## Recommended next action",
        recommended_next_action,
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Bug likelihood: {bug_likelihood}")
    print(f"Likely failure location: {likely_failure_location}")


if __name__ == "__main__":
    main()
