import csv
import json
import math
import subprocess
import sys
from pathlib import Path


def test_research_multisat_geometry_observability_quick():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/research_multisat_geometry_observability.py",
            "--quick",
            "--seed",
            "42",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Rows:" in result.stdout

    base = Path("experiments/results/research_multisat_geometry")
    csv_path = base / "multisat_geometry_trials.csv"
    json_path = base / "multisat_geometry_summary.json"

    assert csv_path.exists()
    assert json_path.exists()

    rows = list(csv.DictReader(csv_path.open()))
    assert len(rows) == 24

    valid_status = {"unobservable", "weak", "moderate", "strong"}

    for row in rows:
        dtoi_global = float(row["dtoi_global_nuisance"])
        dtoi_per_sat = float(row["dtoi_per_satellite_nuisance"])

        assert math.isfinite(dtoi_global)
        assert math.isfinite(dtoi_per_sat)
        assert dtoi_global >= 0.0
        assert dtoi_per_sat >= 0.0
        assert int(row["total_samples"]) > 0
        assert row["observability_status_global"] in valid_status
        assert row["observability_status_per_satellite"] in valid_status

    summary = json.loads(json_path.read_text())
    assert summary["metadata"]["total_rows"] == 24
    assert "best_global_config" in summary["summary"]
    assert "best_per_satellite_config" in summary["summary"]
