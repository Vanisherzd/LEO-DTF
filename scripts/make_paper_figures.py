#!/usr/bin/env python3
"""
Paper Figure Generation Script (Results-Driven)
================================================
Generates lightweight placeholder/preliminary figures for the LEO-DTF paper.
Only reads existing result files; never imports from src/.
Uses matplotlib only (no seaborn).

Usage:
    python scripts/make_paper_figures.py

Outputs:
    paper/figures/dtf_concept.pdf        -- Doppler-time concept (from CSV or toy)
    paper/figures/posterior_heatmap_placeholder.pdf  -- toy Gaussian heatmap
    paper/figures/ablation_summary.pdf  -- ablation bar chart (from JSON)
    paper/figures/crlb_sensitivity.pdf   -- CRLB sensitivity (from CSV)
"""

import json
import os
import sys
import glob

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


ROOT = os.path.join(os.path.dirname(__file__), '..')
FIG_DIR = os.path.join(ROOT, 'paper', 'figures')
os.makedirs(FIG_DIR, exist_ok=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _read_csv_dict(path):
    """Read a CSV with headers into a list of dicts."""
    with open(path) as f:
        lines = f.readlines()
    if len(lines) < 2:
        return []
    headers = [h.strip().strip('"') for h in lines[0].split(',')]
    rows = []
    for line in lines[1:]:
        parts = line.strip().split(',')
        if len(parts) == len(headers):
            rows.append(dict(zip(headers, [p.strip().strip('"') for p in parts])))
    return rows


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Figure 1: DTF Concept (from synthetic CSV or toy)
# --------------------------------------------------------------------------- #

def figure_dtf_concept():
    out = os.path.join(FIG_DIR, 'dtf_concept.pdf')

    # Try to find the synthetic observations CSV
    search = os.path.join(ROOT, 'experiments', 'results', 'synthetic',
                          '*synthetic*observations*.csv')
    matches = glob.glob(search)

    if matches:
        path = matches[0]
        rows = _read_csv_dict(path)
        if rows:
            # Try multiple possible column names
            t_col = next((k for k in rows[0].keys()
                          if 'time' in k.lower() and 'offset' not in k.lower()), None)
            d_col = next((k for k in rows[0].keys()
                          if 'doppler' in k.lower() or 'freq' in k.lower()), None)
            if t_col and d_col:
                times = [float(r[t_col]) for r in rows]
                dopplers = [float(r[d_col]) for r in rows]
                # normalize to relative time
                t0 = times[0]
                times = [t - t0 for t in times]

                plt.figure(figsize=(6, 3.5))
                plt.plot(times, dopplers, 'o-', color='steelblue',
                         linewidth=1.5, markersize=3)
                plt.xlabel('Time since first packet (s)')
                plt.ylabel('Frequency (Hz)')
                plt.title('Doppler-Time Fingerprint (from synthetic observations)')
                plt.grid(True, alpha=0.3)
                plt.tight_layout()
                plt.savefig(out)
                plt.close()
                print(f"  dtf_concept.pdf <- {path}")
                return

    # Fallback: simple toy sine-like curve
    plt.figure(figsize=(6, 3.5))
    t = np.linspace(0, 600, 200)
    # Synthetic Doppler-like shape: roughly parabolic for a pass
    d = -3000 + 80 * np.sin(2 * np.pi * t / 600) + 20 * np.sin(4 * np.pi * t / 600)
    plt.plot(t, d, color='steelblue', linewidth=1.5)
    plt.xlabel('Time since first packet (s)')
    plt.ylabel('Frequency (Hz)')
    plt.title('Doppler-Time Fingerprint — Synthetic Diagnostic Concept')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out)
    plt.close()
    print(f"  dtf_concept.pdf (toy fallback)")


# --------------------------------------------------------------------------- #
# Figure 2: Posterior Heatmap Placeholder (toy Gaussian)
# --------------------------------------------------------------------------- #

def figure_posterior_heatmap():
    out = os.path.join(FIG_DIR, 'posterior_heatmap_placeholder.pdf')

    # Deterministic toy Gaussian posterior
    n = 31
    x = np.linspace(-15, 15, n)
    y = np.linspace(-15, 15, n)
    X, Y = np.meshgrid(x, y)
    # Peak at (2, 1) km, broad spread
    Z = np.exp(-((X - 2)**2 / 20 + (Y - 1)**2 / 15))

    plt.figure(figsize=(5, 4))
    plt.contourf(x, y, Z, levels=15, cmap='Blues')
    plt.colorbar(label='Posterior density (normalized)')
    plt.xlabel('East offset (km)')
    plt.ylabel('North offset (km)')
    plt.title('Posterior Heatmap Placeholder — Synthetic Diagnostic')
    plt.plot(2, 1, 'r*', markersize=12, label='Peak', alpha=0.7)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(out)
    plt.close()
    print(f"  posterior_heatmap_placeholder.pdf (toy)")


# --------------------------------------------------------------------------- #
# Figure 3: Ablation Summary (from JSON)
# --------------------------------------------------------------------------- #

def figure_ablation_summary():
    out = os.path.join(FIG_DIR, 'ablation_summary.pdf')
    path = os.path.join(ROOT, 'experiments', 'results',
                        'ablation', 'ambiguity_ablation_summary.json')

    data = _load_json(path)
    if not data:
        print(f"  ablation_summary.pdf [SKIP] no JSON at {path}")
        return

    raw_cases = data.get('cases', {})
    if isinstance(raw_cases, dict):
        # Convert dict to sorted list for consistent ordering
        case_names_order = [
            'single_snapshot_frequency_only',
            'multi_snapshot_frequency_only',
            'multi_snapshot_frequency_with_cfo',
            'multi_snapshot_frequency_with_cfo_drift',
            'single_snapshot_frequency_with_delay',
            'multi_snapshot_frequency_with_delay',
            'multi_snapshot_frequency_with_cfo_delay',
            'multi_snapshot_frequency_with_cfo_drift_delay',
        ]
        cases = []
        for name in case_names_order:
            if name in raw_cases:
                c = dict(raw_cases[name])
                c['case_name'] = name
                cases.append(c)
        # Fallback: any remaining keys not in the ordered list
        for name, val in raw_cases.items():
            if not any(c['case_name'] == name for c in cases):
                c = dict(val)
                c['case_name'] = name
                cases.append(c)
    else:
        cases = raw_cases

    if not cases:
        print(f"  ablation_summary.pdf [SKIP] no cases found")
        return

    name_map = {
        'single_snapshot_frequency_only': 'Single\nSnap',
        'multi_snapshot_frequency_only': 'Multi\nSnap',
        'multi_snapshot_frequency_with_cfo': 'Multi\n+CFO',
        'multi_snapshot_frequency_with_cfo_drift': 'Multi\n+CFO\n+Drift',
        'single_snapshot_frequency_with_delay': 'Single\n+Delay',
        'multi_snapshot_frequency_with_delay': 'Multi\n+Delay',
        'multi_snapshot_frequency_with_cfo_delay': 'Multi\n+CFO\n+Delay',
        'multi_snapshot_frequency_with_cfo_drift_delay': 'Multi\n+CFO\n+Drift\n+Delay',
    }

    labels, entropies, hpd_cells = [], [], []
    for c in cases:
        lbl = c.get('case_name', 'unknown')
        labels.append(name_map.get(lbl, lbl[:12]))
        entropies.append(float(c.get('mean_entropy', 0)))
        hpd_cells.append(float(c.get('mean_hpd_cells', 0)))

    x = np.arange(len(labels))
    w = 0.35
    fig, a1 = plt.subplots(figsize=(7, 3.5))
    a2 = a1.twinx()
    a1.bar(x - w/2, entropies, w, label='Mean posterior entropy',
           color='steelblue', alpha=0.8)
    a2.bar(x + w/2, hpd_cells, w, label='HPD cells (95%)',
           color='darkorange', alpha=0.8)
    a1.set_xlabel('Ablation case')
    a1.set_ylabel('Mean posterior entropy (nats)')
    a2.set_ylabel('HPD grid cells (95%)')
    a1.set_xticks(x)
    a1.set_xticklabels(labels, fontsize=7)
    a1.tick_params(axis='y', labelcolor='steelblue')
    a2.tick_params(axis='y', labelcolor='darkorange')
    a1.set_title('Ablation: Entropy and HPD vs. Case Complexity')
    a1.legend(loc='upper left', fontsize=8)
    a2.legend(loc='upper right', fontsize=8)
    fig.tight_layout()
    fig.savefig(out)
    plt.close()
    print(f"  ablation_summary.pdf")


# --------------------------------------------------------------------------- #
# Figure 4: CRLB Sensitivity (from CSV)
# --------------------------------------------------------------------------- #

def figure_crlb_sensitivity():
    out = os.path.join(FIG_DIR, 'crlb_sensitivity.pdf')

    # Try both old and new paths
    for subdir in ['crlb', 'sensitivity']:
        search = os.path.join(ROOT, 'experiments', 'results', subdir,
                              '*sensitivity*.csv')
        matches = glob.glob(search)
        if matches:
            path = matches[0]
            break
    else:
        path = None

    if not path:
        print(f"  crlb_sensitivity.pdf [SKIP] no CSV found")
        return

    rows = _read_csv_dict(path)
    if not rows:
        print(f"  crlb_sensitivity.pdf [SKIP] empty CSV")
        return

    # CRLB CSV has sigma_tau_s empty in first row; use range_noise_km as x proxy
    # or try sigma_tau_s then range_noise_km
    x_col = next((k for k in rows[0].keys() if 'sigma_tau' in k.lower()), None)
    if not x_col or not any(r.get(x_col) for r in rows[:3]):
        # Empty column, use range_noise_km
        x_col = 'range_noise_km'

    y_col = next((k for k in rows[0].keys()
                  if 'rmse' in k.lower() and 'bound' in k.lower()), None)
    if not y_col:
        y_col = 'rmse_bound_m'

    xs = [float(r[x_col]) for r in rows if r.get(x_col) and r.get(y_col) and r[x_col]]
    ys = [float(r[y_col]) for r in rows if r.get(x_col) and r.get(y_col) and r[x_col]]

    if not xs:
        print(f"  crlb_sensitivity.pdf [SKIP] could not parse columns")
        return

    plt.figure(figsize=(5, 3.5))
    plt.loglog(xs, ys, 'o-', color='purple', linewidth=1.5, markersize=4)
    plt.xlabel(r'$\sigma$ range noise (km)' if x_col == 'range_noise_km' else r'$\sigma_\tau$ (s)')
    plt.ylabel('CRLB RMSE bound (m)')
    plt.title('CRLB Sensitivity: RMSE Lower Bound vs. Noise Level')
    plt.grid(True, which='both', alpha=0.3)
    plt.tight_layout()
    plt.savefig(out)
    plt.close()
    print(f"  crlb_sensitivity.pdf")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    print("Generating paper figures (results-driven, no src imports)...")
    print("NOTE: All figures are synthetic diagnostics. No paper claims.")
    figure_dtf_concept()
    figure_posterior_heatmap()
    figure_ablation_summary()
    figure_crlb_sensitivity()
    print("Done — figures in paper/figures/")


if __name__ == '__main__':
    main()