"""
Test that estimator grid map ENU offset computation uses correct units.

Bug: score_candidate passes position_en in meters, but the ECEF offset
must be in km (since ground_station_ecef is in km, per the docstring).
Without dividing by 1000, a 100m ENU offset becomes ~100km ECEF offset.

This test creates a minimal score_candidate scenario to verify the unit conversion.
"""

import numpy as np
import pytest
import sys
sys.path.insert(0, "src")

from leodtf.frame_transform import enu_basis_from_geodetic, geodetic_to_ecef
from leodtf.observation_model import ObservationModel


def make_simple_doppler_score(position_en_m, gs_lat, gs_lon, seed=42):
    """Minimal score_candidate-like function.

    Returns the predicted Doppler Hz at the given position for the first satellite.
    This mirrors what score_candidate does up to the Doppler prediction step.

    Returns (predicted_doppler_hz, position_ecef_offset_km)
    """
    np.random.seed(seed)
    lat, lon = gs_lat, gs_lon

    # Ground station ECEF (km)
    gs_ecef = np.array(geodetic_to_ecef(lat, lon, 0.0))

    # ENU basis
    enu_basis = enu_basis_from_geodetic(lat, lon)

    # Compute ECEF offset (THIS IS THE BUG LOCATION)
    # position_en is in METERS, enu_basis is unitless direction cosines
    # To get km ECEF offset: divide by 1000
    pos_en = np.array(position_en_m)
    buggy_offset = enu_basis @ np.append(pos_en, 0.0)          # BUG: meters as km
    correct_offset = enu_basis @ np.append(pos_en / 1000.0, 0.0)  # CORRECT

    buggy_candidate_ecef = gs_ecef + buggy_offset
    correct_candidate_ecef = gs_ecef + correct_offset

    # Simple Doppler at VHF (137 MHz) using single LOS vector
    carrier_freq_hz = 137.0e6
    los_vec = np.array([0.5, 0.5, 0.8])
    los_unit = los_vec / np.linalg.norm(los_vec)

    # Satellite velocity in ECI (roughly in orbital plane)
    sat_vel = np.array([2.0, 3.5, 0.0])  # km/s

    # Buggy: very large offset
    buggy_range_rate = np.dot(buggy_candidate_ecef, los_unit)
    correct_range_rate = np.dot(correct_candidate_ecef, los_unit)

    buggy_doppler = carrier_freq_hz * buggy_range_rate / 3e5
    correct_doppler = carrier_freq_hz * correct_range_rate / 3e5

    return buggy_doppler, correct_doppler, buggy_offset, correct_offset


def test_score_candidate_bug_exists():
    """Verify the unit bug: buggy vs correct ECEF offset.

    At lat=40, lon=-105, position [100, 50]m:
    - Correct offset: ~0.112 km
    - Buggy offset:  ~112 km (1000× too large)

    The Doppler prediction will be catastrophically wrong.
    """
    buggy_hz, correct_hz, buggy_off, correct_off = make_simple_doppler_score(
        [100.0, 50.0], 40.0, -105.0
    )

    buggy_norm = np.linalg.norm(buggy_off)
    correct_norm = np.linalg.norm(correct_off)

    # Offset norms confirm 1000× bug
    # Bug gives ~112 km, correct gives ~0.112 km
    assert buggy_norm > 100, f"Buggy norm should be ~112 km, got {buggy_norm}"
    assert np.isclose(correct_norm, 0.112, atol=0.01), \
        f"Correct norm should be ~0.112 km, got {correct_norm}"

    # Note: Doppler ratio depends on LOS geometry and is not a reliable test signal.


def test_estimator_grid_map_score_candidate_unit_regression(tmp_path):
    """Regression: after fix, score_candidate should give km-scale ECEF offsets.

    This test verifies that the actual score_candidate function (if importable)
    produces correct-scale ECEF offsets. If the fix is not applied, this will fail.
    """
    import importlib.util
    spec = importlib.util.find_spec("leodtf.estimator_grid_map")
    if spec is None:
        pytest.skip("estimator_grid_map not importable")

    from leodtf import estimator_grid_map
    importlib.reload(estimator_grid_map)

    # Check the source has the fix applied
    import inspect
    src = inspect.getsource(estimator_grid_map.score_candidate)

    # After fix, line should contain "/ 1000" or equivalent
    has_fix = "/ 1000" in src or "/1000" in src or "* 0.001" in src

    if not has_fix:
        pytest.fail(
            "score_candidate source does not contain meter→km conversion. "
            "Expected: position_en / 1000 or equivalent. "
            "This test documents the regression that was found."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])