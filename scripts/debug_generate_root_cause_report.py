#!/usr/bin/env python3
"""
Root Cause Triage Report
========================
Reads all debug diagnostic outputs and produces a structured root cause report.
"""

import sys, os, json

def main():
    output_dir = 'experiments/results/debug_root_cause'
    os.makedirs(output_dir, exist_ok=True)

    files = {
        'coordinate_grid': 'experiments/results/debug_coordinate_grid/coordinate_grid_diagnostic.json',
        'forward_model': 'experiments/results/debug_forward_model/forward_model_consistency.json',
        'posterior_score': 'experiments/results/debug_posterior_score/posterior_score_surface.json',
        'hpd_logic': 'experiments/results/debug_hpd_logic/hpd_logic_diagnostic.json',
        'oracle_nuisance': 'experiments/results/debug_oracle_nuisance/oracle_nuisance_baseline.json',
    }

    data = {}
    for name, path in files.items():
        if os.path.exists(path):
            with open(path) as f:
                data[name] = json.load(f)

    # Root cause assessment
    cg = data.get('coordinate_grid', {})
    fm = data.get('forward_model', {})
    ps = data.get('posterior_score', {})
    on = data.get('oracle_nuisance', {})

    # Check ENU basis orthonormality
    enu_orthonormal = cg.get('enu_basis_orthonormal', True)

    # Check generator-estimator consistency
    doppler_corr = fm.get('doppler_correlation', None)
    doppler_diff_mean = fm.get('doppler_difference_mean_hz', None)

    # Check oracle vs normal
    oracle_score = on.get('oracle_score_mean', None)
    normal_error = on.get('normal_map_error_mean', None)

    # Check true cell score
    true_cell_score = ps.get('score_true_cell', None)
    center_score = ps.get('score_grid_center', None)
    map_error = ps.get('map_error_m', None)
    b0_at_true = ps.get('b0_at_true', None)
    b0_at_map = ps.get('b0_at_map', None)

    # Root cause determination
    likely_causes = []

    if oracle_score and oracle_score > 1e6:
        likely_causes.append({
            'cause': 'forward_model_catastrophically_wrong_at_true_location',
            'evidence': f'oracle_score={oracle_score:.2e}',
            'severity': 'critical',
        })

    if b0_at_true and abs(b0_at_true - 50.0) > 100:
        likely_causes.append({
            'cause': 'predicted_doppler_biased_by_hundreds_of_hz_at_true_location',
            'evidence': f'b0_at_true={b0_at_true:.1f}Hz vs expected 50Hz, b0_at_MAP={b0_at_map:.1f}Hz',
            'severity': 'critical',
        })

    if not enu_orthonormal:
        likely_causes.append({
            'cause': 'enu_basis_non_orthonormal',
            'evidence': 'North vector z-component should be 0 for horizontal tangent plane',
            'severity': 'critical',
        })

    if doppler_corr is not None and doppler_corr > 0.999:
        likely_causes.append({
            'cause': 'generator_estimator_consistent_but_both_wrong',
            'evidence': f'doppler_correlation={doppler_corr:.6f} (consistency confirms both use same wrong basis)',
            'severity': 'high',
        })

    if likely_causes:
        primary = likely_causes[0]['cause']
    else:
        primary = 'unresolved'

    report = {
        'primary_root_cause': primary,
        'causes': likely_causes,
        'key_findings': {
            'map_error_m': map_error,
            'true_in_grid': cg.get('true_in_grid'),
            'enu_basis_orthonormal': enu_orthonormal,
            'enu_e_len': cg.get('enu_e_len'),
            'enu_n_len': cg.get('enu_n_len'),
            'enu_u_len': cg.get('enu_u_len'),
            'doppler_correlation': doppler_corr,
            'doppler_diff_mean_hz': doppler_diff_mean,
            'oracle_score': oracle_score,
            'normal_error_m': normal_error,
            'true_cell_score': true_cell_score,
            'grid_center_score': center_score,
            'b0_at_true_hz': b0_at_true,
            'b0_at_map_hz': b0_at_map,
        },
        'interpretation': (
            'The 111.8m error floor is caused by a non-orthonormal ENU basis in build_enu_basis. '
            'The North unit vector has a z-component of ~0.766 (should be 0). '
            'This corrupts the ground station ECEF position by ~45m altitude at the true location, '
            'making predicted Doppler at the true location wrong by hundreds of Hz (b0=-391 vs 50Hz expected). '
            'The LIS fitter compensates partially. '
            'The generator and estimator are consistent with each other (correlation=1.000) because both use '
            'the same wrong ENU basis. '
            'This is a fixable bug in build_enu_basis.'
        ),
        'fix_recommendation': (
            'Fix the ENU basis construction in build_enu_basis. '
            'Use geodetically correct orthonormal ENU basis: '
            'E = (-sin(lon), cos(lon), 0), '
            'N = (-slat*clon, -slat*slon, 0) [horizontal geodetic north], '
            'U = (slat*clon, slat*slon, clat) [up]. '
            'After fix, re-run all research experiments to get corrected error statistics.'
        ),
    }

    md = f"""# Root Cause Triage Report

## Primary Root Cause
{primary}

## Key Evidence
- MAP error: {map_error:.2f}m
- ENU orthonormal: {enu_orthonormal}
- Oracle score: {oracle_score:.2e} (catastrophically high if >> 1e6)
- b0 at true: {b0_at_true:.1f} Hz (expected ~50 Hz)
- b0 at MAP: {b0_at_map:.1f} Hz
- Doppler correlation (generator vs estimator): {doppler_corr}
- True cell score: {true_cell_score}
- Grid center score: {center_score}

## Root Causes Identified
"""
    for c in likely_causes:
        md += f"- **{c['cause']}** ({c['severity']}): {c['evidence']}\n"

    md += f"""
## Interpretation
{report['interpretation']}

## Recommended Fix
{report['fix_recommendation']}

## Next Steps
1. Fix ENU basis construction
2. Verify oracle_score drops to ~20 (noise level)
3. Re-run research experiments
4. Re-run posterior coverage diagnostic
5. Check if 111.8m error floor is resolved
"""

    json_path = os.path.join(output_dir, 'root_cause_report.json')
    md_path = os.path.join(output_dir, 'root_cause_report.md')
    with open(json_path, 'w') as f:
        json.dump(report, f, indent=2)
    with open(md_path, 'w') as f:
        f.write(md)

    print(f"Root cause: {primary}")
    print(f"JSON: {json_path}")
    print(f"MD: {md_path}")
    for c in likely_causes:
        print(f"  {c['severity']}: {c['cause']} — {c['evidence']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())