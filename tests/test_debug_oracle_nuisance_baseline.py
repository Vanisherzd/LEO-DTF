"""Regression test: debug_oracle_nuisance_baseline.py ENU basis.

Verifies the local ENU basis in debug_oracle_nuisance_baseline.py satisfies
standard geodetic ENU properties:
  - |E| = |N| = |U| = 1
  - E·N = E·U = N·U = 0
  - N_z = cos(lat),  U_z = sin(lat)
  - determinant = +1
  - matches frame_transform.enu_basis_from_geodetic

This test does NOT import the debug script (which is a script, not a module).
It replicates the basis construction logic and validates it.
"""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from leodtf.frame_transform import enu_basis_from_geodetic


# ------------------------------------------------------------------
# Replicate the (fixed) basis construction from the debug script
# ------------------------------------------------------------------
def build_enu_basis_debug(lat_deg, lon_deg):
    """Replicate the ENU basis in debug_oracle_nuisance_baseline.py.

    This is the corrected version (clat = cos(lat_r), not cos(lon_r)).
    """
    lat_r = np.radians(lat_deg)
    lon_r = np.radians(lon_deg)
    slat = np.sin(lat_r)
    clat = np.cos(lat_r)
    slon = np.sin(lon_r)
    clon = np.cos(lon_r)

    enu_basis = np.column_stack([
        np.array([-slon, clon, 0.0]),
        np.array([-slat * clon, -slat * slon, clat]),
        np.array([clat * clon, clat * slon, slat]),
    ])
    return enu_basis


# ------------------------------------------------------------------
# Test cases (lat, lon)
# ------------------------------------------------------------------
CASES = [
    (40.0, -105.0),   # LAT0_DEG, LON0_DEG used in debug_oracle_nuisance_baseline.py
    (0.0, 0.0),
    (24.0, 121.0),
    (-30.0, 60.0),
    (80.0, -120.0),
    (45.0, 90.0),
]


class TestOracleNuisanceEnuBasis:
    """Validate the debug script's ENU basis against standard properties."""

    @pytest.mark.parametrize("lat_deg,lon_deg", CASES)
    def test_norms(self, lat_deg, lon_deg):
        R = build_enu_basis_debug(lat_deg, lon_deg)
        E, N, U = R[:, 0], R[:, 1], R[:, 2]
        assert_allclose(np.linalg.norm(E), 1.0, atol=1e-12)
        assert_allclose(np.linalg.norm(N), 1.0, atol=1e-12)
        assert_allclose(np.linalg.norm(U), 1.0, atol=1e-12)

    @pytest.mark.parametrize("lat_deg,lon_deg", CASES)
    def test_orthogonality(self, lat_deg, lon_deg):
        R = build_enu_basis_debug(lat_deg, lon_deg)
        E, N, U = R[:, 0], R[:, 1], R[:, 2]
        assert_allclose(np.dot(E, N), 0.0, atol=1e-12)
        assert_allclose(np.dot(E, U), 0.0, atol=1e-12)
        assert_allclose(np.dot(N, U), 0.0, atol=1e-12)

    @pytest.mark.parametrize("lat_deg,lon_deg", CASES)
    def test_determinant(self, lat_deg, lon_deg):
        R = build_enu_basis_debug(lat_deg, lon_deg)
        assert_allclose(np.linalg.det(R), 1.0, atol=1e-12)

    @pytest.mark.parametrize("lat_deg,lon_deg", CASES)
    def test_n_z_equals_cos_lat(self, lat_deg, lon_deg):
        """N_z must be cos(lat), NOT 0 (non-pole)."""
        R = build_enu_basis_debug(lat_deg, lon_deg)
        N = R[:, 1]
        assert_allclose(N[2], np.cos(np.radians(lat_deg)), atol=1e-12)

    @pytest.mark.parametrize("lat_deg,lon_deg", CASES)
    def test_u_z_equals_sin_lat(self, lat_deg, lon_deg):
        """U_z must be sin(lat)."""
        R = build_enu_basis_debug(lat_deg, lon_deg)
        U = R[:, 2]
        assert_allclose(U[2], np.sin(np.radians(lat_deg)), atol=1e-12)

    @pytest.mark.parametrize("lat_deg,lon_deg", CASES)
    def test_e_z_is_zero(self, lat_deg, lon_deg):
        """E_z must always be 0."""
        R = build_enu_basis_debug(lat_deg, lon_deg)
        E = R[:, 0]
        assert_allclose(E[2], 0.0, atol=1e-12)

    @pytest.mark.parametrize("lat_deg,lon_deg", CASES)
    def test_matches_frame_transform(self, lat_deg, lon_deg):
        """Debug script basis must match the shared frame_transform implementation."""
        R_debug = build_enu_basis_debug(lat_deg, lon_deg)
        R_ref   = enu_basis_from_geodetic(lat_deg, lon_deg)
        assert_allclose(R_debug, R_ref, atol=1e-12,
                        err_msg=f"Mismatch at lat={lat_deg}, lon={lon_deg}")

    def test_clat_not_clon(self):
        """Specific regression: clat must be cos(lat), not cos(lon)."""
        # At lat=40, lon=-105, cos(lat)=0.766, cos(lon)=-0.515
        R = build_enu_basis_debug(40.0, -105.0)
        N = R[:, 1]
        # Buggy value would be cos(lon=-105deg) = -0.515
        # Correct value is cos(40deg) = 0.766
        assert_allclose(N[2], np.cos(np.radians(40.0)), atol=1e-12,
                        err_msg="N_z != cos(lat) — clat was likely set to cos(lon)")
        # Also check determinant (buggy basis is not orthonormal)
        assert_allclose(np.linalg.det(R), 1.0, atol=1e-12,
                        err_msg="det != 1 — clat was likely set to cos(lon)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])