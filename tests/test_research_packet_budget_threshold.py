import csv
import json
import math
import subprocess
import sys
from pathlib import Path


def test_research_packet_budget_threshold_quick():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/research_packet_budget_threshold.py",
            "--quick",
            "--seed",
            "42",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Rows:" in result.stdout

    base = Path("experiments/results/research_packet_budget")
    csv_path = base / "packet_budget_trials.csv"
    json_path = base / "packet_budget_summary.json"

    assert csv_path.exists()
    assert json_path.exists()

    rows = list(csv.DictReader(csv_path.open()))
    assert len(rows) == 48

    valid_status = {"unobservable", "weak", "moderate", "strong"}

    for row in rows:
        dtoi = float(row["dtoi"])
        dtoi_per_packet = float(row["dtoi_per_packet"])
        assert math.isfinite(dtoi)
        assert math.isfinite(dtoi_per_packet)
        assert dtoi >= 0.0
        assert dtoi_per_packet >= 0.0
        assert int(row["total_samples"]) > 0
        assert row["observability_status"] in valid_status

    summary = json.loads(json_path.read_text())
    assert summary["metadata"]["total_rows"] == 48
    assert "best_config" in summary["summary"]
    assert "count_unobservable" in summary["summary"]
    assert "count_weak" in summary["summary"]
    assert "count_moderate" in summary["summary"]
    assert "count_strong" in summary["summary"]
