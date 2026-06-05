"""Tests for frame_transform module.

Verifies coordinate frame conversions and ENU basis properties.
"""

import numpy as np
import pytest
from leodtf import frame_transform


def test_geodetic_to_ecef_earth_radius():
    """Geodetic to ECEF returns position with norm near Earth radius."""
    # Test at sea level, equator
    lat, lon, alt = 0.0, 0.0, 0.0  # degrees, km
    x, y, z = frame_transform.geodetic_to_ecef(lat, lon, alt)
    pos_ecef = np.array([x, y, z])
    norm = np.linalg.norm(pos_ecef)
    # Earth equatorial radius ~6378 km
    assert 6370.0 < norm < 6390.0, f"ECEF norm {norm} km not near Earth radius"
    
    # Test at sea level, pole
    lat_pole, lon_pole, alt_pole = 90.0, 0.0, 0.0
    xp, yp, zp = frame_transform.geodetic_to_ecef(lat_pole, lon_pole, alt_pole)
    pos_pole = np.array([xp, yp, zp])
    norm_pole = np.linalg.norm(pos_pole)
    # Earth polar radius ~6357 km
    assert 6350.0 < norm_pole < 6370.0, f"Polar ECEF norm {norm_pole} km not near Earth radius"


def test_geodetic_to_ecef_altitude():
    """Increasing altitude increases ECEF norm by approximately the altitude change."""
    lat, lon = 45.0, -105.0
    alt1, alt2 = 0.0, 10.0  # km
    
    x1, y1, z1 = frame_transform.geodetic_to_ecef(lat, lon, alt1)
    pos1 = np.array([x1, y1, z1])
    x2, y2, z2 = frame_transform.geodetic_to_ecef(lat, lon, alt2)
    pos2 = np.array([x2, y2, z2])
    
    norm_diff = np.linalg.norm(pos2) - np.linalg.norm(pos1)
    # At mid-latitudes, altitude change should nearly equal norm change
    assert abs(norm_diff - alt2) < 0.1, f"Altitude change {alt2} km, norm change {norm_diff} km"


def test_enu_basis_orthogonality():
    """ENU basis vectors are mutually orthogonal and unit norm."""
    lat, lon, alt = 40.0, -105.0, 1.5  # Boulder, CO
    
    # Get ECEF position for reference
    x0, y0, z0 = frame_transform.geodetic_to_ecef(lat, lon, alt)
    pos_ecef = np.array([x0, y0, z0])
    
    # Compute ENU basis by perturbing each coordinate
    eps = 1e-6  # km = 1 mm
    
    # East: increase longitude slightly
    xe, ye, ze = frame_transform.geodetic_to_ecef(lat, lon + eps*180/np.pi, alt)
    east_vec = np.array([xe, ye, ze]) - pos_ecef
    east_unit = east_vec / np.linalg.norm(east_vec)
    
    # North: increase latitude slightly
    xn, yn, zn = frame_transform.geodetic_to_ecef(lat + eps*180/np.pi, lon, alt)
    north_vec = np.array([xn, yn, zn]) - pos_ecef
    north_unit = north_vec / np.linalg.norm(north_vec)
    
    # Up: increase altitude
    xu, yu, zu = frame_transform.geodetic_to_ecef(lat, lon, alt + eps)
    up_vec = np.array([xu, yu, zu]) - pos_ecef
    up_unit = up_vec / np.linalg.norm(up_vec)
    
    # Check unit norm
    assert abs(np.linalg.norm(east_unit) - 1.0) < 1e-6, f"East unit norm: {np.linalg.norm(east_unit)}"
    assert abs(np.linalg.norm(north_unit) - 1.0) < 1e-6, f"North unit norm: {np.linalg.norm(north_unit)}"
    assert abs(np.linalg.norm(up_unit) - 1.0) < 1e-6, f"Up unit norm: {np.linalg.norm(up_unit)}"
    
    # Check orthogonality
    assert abs(np.dot(east_unit, north_unit)) < 1e-6, f"East-North dot: {np.dot(east_unit, north_unit)}"
    assert abs(np.dot(east_unit, up_unit)) < 1e-6, f"East-Up dot: {np.dot(east_unit, up_unit)}"
    assert abs(np.dot(north_unit, up_unit)) < 1e-6, f"North-Up dot: {np.dot(north_unit, up_unit)}"


def test_enu_offset_changes_ecef_by_expected_amount():
    """A 100 m east ENU offset changes ECEF position by approximately 0.1 km."""
    lat, lon, alt = 40.0, -105.0, 1.5  # Boulder, CO
    
    x0, y0, z0 = frame_transform.geodetic_to_ecef(lat, lon, alt)
    pos_ref = np.array([x0, y0, z0])
    
    # Convert 100 m east offset to ECEF
    offset_e_km = 0.1  # 100 m = 0.1 km
    offset_n_km = 0.0
    offset_u_km = 0.0
    
    xo, yo, zo = frame_transform.enu_to_ecef(offset_e_km, offset_n_km, offset_u_km, lat, lon, alt)
    pos_offset = np.array([xo, yo, zo])
    
    # The change in position should be approximately 0.1 km
    delta = np.linalg.norm(pos_offset - pos_ref)
    assert 0.099 < delta < 0.101, f"100 m ENU offset produced {delta*1000:.1f} m ECEF change"


def test_enu_to_ecef_and_back():
    """Round-trip ECEF to ENU and back preserves position."""
    lat, lon, alt = 25.0, 121.0, 0.5  # Taipei area
    
    # Reference position
    xr, yr, zr = frame_transform.geodetic_to_ecef(lat, lon, alt)
    pos_ref_ecef = np.array([xr, yr, zr])
    
    # Some ENU offset
    e_offset, n_offset, u_offset = 0.05, -0.03, 0.01  # km (50 m, -30 m, 10 m)
    
    # Convert ENU offset to ECEF
    xo, yo, zo = frame_transform.enu_to_ecef(e_offset, n_offset, u_offset, lat, lon, alt)
    pos_offset_ecef = np.array([xo, yo, zo])
    
    # Convert back to ENU (relative to reference)
    e_ret, n_ret, u_ret = frame_transform.ecef_to_enu(xo, yo, zo, lat, lon, alt)
    
    # Should recover original offset
    assert abs(e_ret - e_offset) < 1e-6, f"East round-trip: {e_ret} vs {e_offset}"
    assert abs(n_ret - n_offset) < 1e-6, f"North round-trip: {n_ret} vs {n_offset}"
    assert abs(u_ret - u_offset) < 1e-6, f"Up round-trip: {u_ret} vs {u_offset}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])