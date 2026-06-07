#!/usr/bin/env python3
"""
Summarize evaluation outputs from LEO-DTF experiments.

Reads results from:
  experiments/results/synthetic/
  experiments/results/montecarlo/
  experiments/results/crlb/

Outputs:
  experiments/results/evaluation_summary.md
  experiments/results/evaluation_summary.json
  paper/tables/evaluation_summary.tex
"""

import sys
import os
import json
import csv
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).parent.parent.resolve()
RESULTS = BASE / "experiments" / "results"
PAPER_TABLES = BASE / "paper" / "tables"
PAPER_TABLES.mkdir(parents=True, exist_ok=True)
RESULTS.mkdir(parents=True, exist_ok=True)


def read_json(path):
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def read_csv_dict(path):
    if not path.exists():
        return None
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def summarize_synthetic():
    """Read synthetic pass dataset results."""
    ds = RESULTS / "synthetic"
    jpath = ds / "synthetic_pass_dataset.json"
    cpath = ds / "synthetic_pass_observations.csv"

    out = {"status": "Missing"}
    if jpath.exists():
        data = read_json(jpath)
        if data:
            n = len(data.get("time_offsets_s", data.get("times", [])))
            out = {
                "status": "Available",
                "num_samples": n,
                "duration_s": data.get("duration_s", "N/A"),
                "sample_interval_s": data.get("sample_interval_s", "N/A"),
                "carrier_hz": data.get("carrier_hz", "N/A"),
                "cfo_hz": data.get("cfo_hz", "N/A"),
                "drift_hz_per_s": data.get("drift_hz_per_s", "N/A"),
                "time_offset_s": data.get("time_offset_s", "N/A"),
                "doppler_noise_std_hz": data.get("doppler_noise_std_hz", "N/A"),
                "delay_noise_std_s": data.get("delay_noise_std_s", "N/A"),
                "orbit_altitude_km": data.get("orbit_altitude_km", "N/A"),
                "orbit_inclination_deg": data.get("orbit_inclination_deg", "N/A"),
                "seed": data.get("seed", "N/A"),
            }
    return out


def summarize_montecarlo():
    """Read Monte Carlo summary JSON, fallback to CSV."""
    mdir = RESULTS / "montecarlo"
    jpath = mdir / "montecarlo_summary.json"
    cpath = mdir / "montecarlo_trials.csv"

    out = {"status": "Missing"}
    if jpath.exists():
        data = read_json(jpath)
        if data:
            m = data.get("metrics", {})
            out = {
                "status": "Available",
                "trials": data.get("trials", "N/A"),
                "seed": data.get("seed", "N/A"),
                "error_mag_mean_m": m.get("error_mag_mean_m", "N/A"),
                "error_mag_std_m": m.get("error_mag_std_m", "N/A"),
                "error_mag_median_m": m.get("error_mag_median_m", "N/A"),
                "error_mag_p90_m": m.get("error_mag_p90_m", "N/A"),
                "posterior_entropy_mean": m.get("posterior_entropy_mean", "N/A"),
                "hpd_n_cells_mean": m.get("hpd_n_cells_mean", "N/A"),
                "config": data.get("config", {}),
            }
    return out


def summarize_crlb():
    """Read CRLB sensitivity summary JSON."""
    cpath = RESULTS / "crlb" / "crlb_sensitivity_summary.json"

    out = {"status": "Missing"}
    if cpath.exists():
        data = read_json(cpath)
        if data:
            out = {
                "status": "Available",
                "sigma_tau_sweep": data.get("sigma_tau_sweep", "N/A"),
                "sigma_f_hz": data.get("sigma_f_hz", "N/A"),
                "qualitative": data.get("qualitative", {}),
                "recommendations": data.get("recommendations", []),
                "geometry": data.get("geometry", {}),
                "results": data.get("results", []),
            }
    return out


def build_json():
    """Build the combined evaluation summary JSON."""
    syn = summarize_synthetic()
    mc = summarize_montecarlo()
    crlb = summarize_crlb()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": None,  # fill if git available
        "synthetic": syn,
        "montecarlo": mc,
        "crlb": crlb,
        "generated_files": {
            "summary_md": str(RESULTS / "evaluation_summary.md"),
            "summary_json": str(RESULTS / "evaluation_summary.json"),
            "summary_tex": str(PAPER_TABLES / "evaluation_summary.tex"),
        },
    }


def build_md(data):
    """Build the markdown summary."""
    syn = data["synthetic"]
    mc = data["montecarlo"]
    crlb = data["crlb"]

    lines = [
        "# LEO-DTF Evaluation Summary",
        "",
        f"_Generated: {data['generated_at']}_",
        "",
        "## Synthetic Pass Summary",
        "",
        f"- Status: {syn.get('status', 'N/A')}",
        f"- Number of samples: {syn.get('num_samples', 'N/A')}",
        f"- Duration: {syn.get('duration_s', 'N/A')} s",
        f"- Sample interval: {syn.get('sample_interval_s', 'N/A')} s",
        f"- Carrier frequency: {syn.get('carrier_hz', 'N/A')} Hz",
        f"- Injected CFO: {syn.get('cfo_hz', 'N/A')} Hz",
        f"- Drift: {syn.get('drift_hz_per_s', 'N/A')} Hz/s",
        f"- Time offset: {syn.get('time_offset_s', 'N/A')} s",
        f"- Doppler noise std: {syn.get('doppler_noise_std_hz', 'N/A')} Hz",
        f"- Delay noise std: {syn.get('delay_noise_std_s', 'N/A')} s",
        f"- Orbit: {syn.get('orbit_altitude_km', 'N/A')} km @ {syn.get('orbit_inclination_deg', 'N/A')} deg",
        f"- Seed: {syn.get('seed', 'N/A')}",
        "",
        "## Monte Carlo Summary",
        "",
        f"- Status: {mc.get('status', 'N/A')}",
        f"- Trials: {mc.get('trials', 'N/A')}",
        f"- Error mean: {mc.get('error_mag_mean_m', 'N/A')} m",
        f"- Error std: {mc.get('error_mag_std_m', 'N/A')} m",
        f"- Error median: {mc.get('error_mag_median_m', 'N/A')} m",
        f"- Error 90th percentile: {mc.get('error_mag_p90_m', 'N/A')} m",
        f"- Posterior entropy mean: {mc.get('posterior_entropy_mean', 'N/A')}",
        f"- HPD cells mean: {mc.get('hpd_n_cells_mean', 'N/A')}",
        "",
        "## CRLB Sensitivity Summary",
        "",
        f"- Status: {crlb.get('status', 'N/A')}",
        f"- sigma_tau sweep: {crlb.get('sigma_tau_sweep', 'N/A')}",
        f"- sigma_f: {crlb.get('sigma_f_hz', 'N/A')} Hz",
        f"- CRLB trend: {crlb.get('qualitative', {}).get('trend', 'N/A')}",
        f"- sigma_tau=1ms note: {crlb.get('qualitative', {}).get('sigma_tau_1ms_note', 'N/A')}",
        "",
        "## Reproduction Commands",
        "",
        "```bash",
        "python scripts/generate_synthetic_dataset.py",
        "python scripts/run_monte_carlo_synthetic.py --trials 5",
        "python scripts/diagnose_crlb_sensitivity.py",
        "python scripts/summarize_evaluation.py",
        "```",
        "",
        "_All results are synthetic/trace-driven. No real satellite OTA validation claimed._",
    ]
    return "\n".join(lines)


def build_tex(data):
    """Build a simple LaTeX table for paper/tables/evaluation_summary.tex."""
    syn = data["synthetic"]
    mc = data["montecarlo"]
    crlb = data["crlb"]

    rows = [
        "Experiment & Script & Output File & Status \\\\",
        "\\hline",
        "Synthetic Pass & generate\\_synthetic\\_dataset.py & "
        "synthetic\\_pass\\_dataset.json & "
        + ("Implemented" if syn.get("status") == "Available" else "Missing") + " \\\\",
        "Monte Carlo (5 trials) & run\\_monte\\_carlo\\_synthetic.py & "
        "monte\\_carlo\\_trials.csv & "
        + ("Implemented" if mc.get("status") == "Available" else "Missing") + " \\\\",
        "CRLB Sensitivity & diagnose\\_crlb\\_sensitivity.py & "
        "crlb\\_sensitivity.csv & "
        + ("Implemented" if crlb.get("status") == "Available" else "Missing") + " \\\\",
        "Summary Report & summarize\\_evaluation.py & "
        "evaluation\\_summary.md & "
        "Implemented \\\\",
    ]

    content = """%% LEO-DTF Evaluation Summary
%% Auto-generated by scripts/summarize_evaluation.py
%% Do not edit manually — regenerate with summarize_evaluation.py

\\begin{table}[htbp]
\\centering
\\caption{Preliminary Evaluation Artifacts (Synthetic / Trace-driven Only)}
\\label{tab:evaluation_summary}
\\begin{tabular}{|l|l|l|c|}
\\hline
\\textbf{Experiment} & \\textbf{Script} & \\textbf{Output File} & \\textbf{Status} \\\\ \\hline
Synthetic Pass & \\texttt{generate\\_synthetic\\_dataset.py} &
  \\texttt{synthetic\\_pass\\_dataset.json} &
  \\makecell{""" + ("Implemented" if syn.get("status") == "Available" else "Missing") + """} \\\\ \\hline
Monte Carlo & \\texttt{run\\_monte\\_carlo\\_synthetic.py} &
  \\texttt{monte\\_carlo\\_trials.csv} &
  \\makecell{""" + ("Implemented" if mc.get("status") == "Available" else "Missing") + """} \\\\ \\hline
CRLB Sensitivity & \\texttt{diagnose\\_crlb\\_sensitivity.py} &
  \\texttt{crlb\\_sensitivity.csv} &
  \\makecell{""" + ("Implemented" if crlb.get("status") == "Available" else "Missing") + """} \\\\ \\hline
Summary Report & \\texttt{summarize\\_evaluation.py} &
  \\texttt{evaluation\\_summary.md} &
  Implemented \\\\ \\hline
\\end{tabular}
\\smallskip
\\footnotesize
All artifacts are synthetic or trace-driven. No real satellite OTA validation.
Monte Carlo trials use a coarse grid (20~m resolution) over a ±200~m ROI.
CRLB is a theoretical lower bound; MAP estimator with priors is not directly
comparable to classical CRLB.
\\end{table}
"""
    return content


def main():
    print("LEO-DTF Evaluation Summarizer")
    print("=" * 50)

    data = build_json()
    RESULTS.mkdir(parents=True, exist_ok=True)

    # Write JSON
    jout = RESULTS / "evaluation_summary.json"
    with open(jout, "w") as f:
        json.dump(data, f, indent=2)
    print(f"JSON: {jout}")

    # Write Markdown
    mdout = RESULTS / "evaluation_summary.md"
    with open(mdout, "w") as f:
        f.write(build_md(data))
    print(f"MD:   {mdout}")

    # Write LaTeX
    texout = PAPER_TABLES / "evaluation_summary.tex"
    with open(texout, "w") as f:
        f.write(build_tex(data))
    print(f"TeX:  {texout}")

    # Print a quick status line
    print()
    print("Summary:")
    print(f"  synthetic : {data['synthetic'].get('status', 'N/A')}")
    print(f"  montecarlo: {data['montecarlo'].get('status', 'N/A')}")
    print(f"  crlb      : {data['crlb'].get('status', 'N/A')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())