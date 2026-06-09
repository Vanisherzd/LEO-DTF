import csv
import json
import math
import subprocess
import sys
from pathlib import Path


def test_research_multipass_observability_quick():
    result = subprocess.run(
        [sys.executable, "scripts/research_multipass_observability.py", "--quick", "--seed", "42"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Rows:" in result.stdout

    base = Path("experiments/results/research_multipass_observability")
    csv_path = base / "multipass_observability_trials.csv"
    json_path = base / "multipass_observability_summary.json"

    assert csv_path.exists()
    assert json_path.exists()

    rows = list(csv.DictReader(csv_path.open()))
    assert len(rows) == 24

    valid = {"unobservable", "weak", "moderate", "strong"}

    for row in rows:
        dg = float(row["dtoi_global_nuisance"])
        dp = float(row["dtoi_per_pass_nuisance"])
        assert math.isfinite(dg) and dg >= 0
        assert math.isfinite(dp) and dp >= 0
        assert row["observability_status_global"] in valid
        assert row["observability_status_per_pass"] in valid
        assert int(row["total_samples"]) > 0

    summary = json.loads(json_path.read_text())
    assert summary["metadata"]["total_rows"] == 24
    assert "best_global_config" in summary["summary"]
    assert "best_per_pass_config" in summary["summary"]
