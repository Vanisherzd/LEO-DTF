"""Tests for the Jacobian and CRLB module.
"""

import numpy as np
import pytest
from leodtf.jacobian_crlb import compute_crlb_en_position, crlb_ellipse_area

def test_crlb_shape_and_finiteness():
    # Non-degenerate geometry: ground station at mid-latitude, inclined orbit
    from datetime import datetime, timedelta

    # Ground station at mid-latitude (Taipei area)
    gs_ref_geodetic = (25.0, 121.0, 0.0)
    # True ENU offset (we assume we know it for the test)
    gs_enu_offset_true = (0.0, 0.0)
    # True nuisance parameters
    delta_t_true = 0.0
    b0_true = 0.0
    b1_true = 0.0
    carrier_freq_hz = 1.6e9
    # Times over a pass (10 points over 10 minutes for better geometry)
    times = np.array([0, 60, 120, 180, 240, 300, 360, 420, 480, 540])  # seconds
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_dt = [ref_time + timedelta(seconds=float(t)) for t in times]

    # Create a synthetic inclined circular orbit at 400 km altitude
    # Inclination ~53 deg (typical LEO)
    R = 6378.137 + 400.0  # km
    mu = 3.986004418e5
    n = np.sqrt(mu / R**3)  # rad/s
    inc = np.radians(53.0)  # 53 degree inclination
    
    sat_positions_ecef = []
    sat_velocities_ecef = []
    for t in times:
        angle = n * t
        # Circular orbit in orbital plane, then rotate by inclination
        # Position in orbital plane
        x_orb = R * np.cos(angle)
        y_orb = R * np.sin(angle)
        # Rotate by inclination around x-axis
        x = x_orb
        y = y_orb * np.cos(inc)
        z = y_orb * np.sin(inc)
        # Velocity in orbital plane
        vx_orb = -R * n * np.sin(angle)
        vy_orb = R * n * np.cos(angle)
        # Rotate velocity by inclination
        vx = vx_orb
        vy = vy_orb * np.cos(inc)
        vz = vy_orb * np.sin(inc)
        sat_positions_ecef.append([x, y, z])
        sat_velocities_ecef.append([vx, vy, vz])
    sat_positions_ecef = np.array(sat_positions_ecef)
    sat_velocities_ecef = np.array(sat_velocities_ecef)

    # Compute CRLB
    crlb_cov = compute_crlb_en_position(
        sat_positions_ecef, sat_velocities_ecef,
        gs_ref_geodetic, carrier_freq_hz, times,
        delta_t_true, b0_true, b1_true, gs_enu_offset_true,
        sigma_f=1.0, sigma_tau=1e-3
    )

    # Check shape
    assert crlb_cov.shape == (2, 2)
    # Check that there are no NaNs in normal conditions
    assert not np.any(np.isnan(crlb_cov))
    # Check that the covariance is positive semi-diagonal (we expect positive variances)
    assert np.all(np.diag(crlb_cov) >= 0)
    # Check that the determinant is non-negative (for a valid covariance matrix)
    det = np.linalg.det(crlb_cov)
    assert det >= 0

def test_crlb_ellipse_area():
    # Test with a known covariance matrix
    cov = np.array([[1.0, 0.5], [0.5, 2.0]])
    area = crlb_ellipse_area(cov)
    expected_area = np.pi * np.sqrt(np.linalg.det(cov))
    assert abs(area - expected_area) < 1e-9

    # Test with NaN input
    cov_nan = np.array([[np.nan, 0.0], [0.0, 1.0]])
    area_nan = crlb_ellipse_area(cov_nan)
    assert np.isnan(area_nan)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])