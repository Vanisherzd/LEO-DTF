import json
import subprocess
import sys
from pathlib import Path


def test_orbit_offset_source_audit_outputs():
    subprocess.run(
        [sys.executable, "scripts/research_orbit_offset_source_audit.py"],
        check=True,
    )

    out_dir = Path("experiments/results/research_orbit_offset_source_audit")
    json_path = out_dir / "orbit_offset_source_audit.json"
    md_path = out_dir / "orbit_offset_source_audit.md"
    csv_path = out_dir / "orbit_offset_source_trials.csv"

    assert json_path.exists()
    assert md_path.exists()
    assert csv_path.exists()

    data = json.loads(json_path.read_text())

    for key in [
        "unit_distance_checks",
        "rms_scaling_checks",
        "best_row",
        "c10_static_source_audit",
        "suspicious_flags",
        "bug_likelihood",
        "likely_failure_location",
        "conservative_interpretation",
        "recommended_next_action",
    ]:
        assert key in data

    assert len(data["unit_distance_checks"]) == 3
    assert len(data["rms_scaling_checks"]) == 3

    interp = data["conservative_interpretation"].lower()
    assert "not ota" in interp
    assert "does not prove localization accuracy" in interp

    static = data["c10_static_source_audit"]
    assert "verdict" in static
    assert "offset_m_mentions_in_orbit_branch" in static

    assert isinstance(data["suspicious_flags"], list)
