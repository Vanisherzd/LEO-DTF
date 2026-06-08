"""Tests for standard ENU basis math.

Verifies that the ENU basis implementation satisfies standard geodetic
coordinate frame properties at multiple latitudes and longitudes.
"""

import numpy as np
import pytest
from numpy.testing import assert_allclose


# ------------------------------------------------------------------
# Reference implementation (standard geodetic ENU)
# ------------------------------------------------------------------
def standard_enu_basis(lat_deg, lon_deg):
    """Standard ENU basis at geodetic lat/lon.

    E  = [-sin(lon),  cos(lon), 0]
    N  = [-sin(lat)*cos(lon), -sin(lat)*sin(lon), cos(lat)]
    U  = [ cos(lat)*cos(lon),  cos(lat)*sin(lon), sin(lat)]

    Columns of returned array: E, N, U  (shape [3, 3]).
    """
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    slat = np.sin(lat)
    clat = np.cos(lat)
    slon = np.sin(lon)
    clon = np.cos(lon)

    E = np.array([-slon, clon, 0.0])
    N = np.array([-slat * clon, -slat * slon, clat])
    U = np.array([clat * clon, clat * slon, slat])

    return np.column_stack([E, N, U])


# ------------------------------------------------------------------
# Test cases  (lat, lon)
# ------------------------------------------------------------------
ENABLE_TEST_CASES = [
    (0.0, 0.0),        # equator / prime meridian
    (24.0, 121.0),     # Taiwan
    (40.0, 0.0),       # mid-latitude
    (-30.0, 60.0),     # southern hemisphere
    (80.0, -120.0),    # high latitude
    (45.0, 90.0),      # 45°N, 90°E
    (-65.0, 175.0),    # high southern latitude
]


# ------------------------------------------------------------------
# Parametrised test
# ------------------------------------------------------------------
class TestEnuBasisMath:
    """Standard ENU basis properties at multiple locations."""

    @pytest.mark.parametrize("lat_deg,lon_deg", ENABLE_TEST_CASES)
    def test_norms(self, lat_deg, lon_deg):
        R = standard_enu_basis(lat_deg, lon_deg)
        E, N, U = R[:, 0], R[:, 1], R[:, 2]
        assert_allclose(np.linalg.norm(E), 1.0, atol=1e-12,
                        err_msg=f"lat={lat_deg}, lon={lon_deg}: |E| != 1")
        assert_allclose(np.linalg.norm(N), 1.0, atol=1e-12,
                        err_msg=f"lat={lat_deg}, lon={lon_deg}: |N| != 1")
        assert_allclose(np.linalg.norm(U), 1.0, atol=1e-12,
                        err_msg=f"lat={lat_deg}, lon={lon_deg}: |U| != 1")

    @pytest.mark.parametrize("lat_deg,lon_deg", ENABLE_TEST_CASES)
    def test_orthogonality(self, lat_deg, lon_deg):
        R = standard_enu_basis(lat_deg, lon_deg)
        E, N, U = R[:, 0], R[:, 1], R[:, 2]
        assert_allclose(np.dot(E, N), 0.0, atol=1e-12,
                        err_msg=f"lat={lat_deg}, lon={lon_deg}: E·N != 0")
        assert_allclose(np.dot(E, U), 0.0, atol=1e-12,
                        err_msg=f"lat={lat_deg}, lon={lon_deg}: E·U != 0")
        assert_allclose(np.dot(N, U), 0.0, atol=1e-12,
                        err_msg=f"lat={lat_deg}, lon={lon_deg}: N·U != 0")

    @pytest.mark.parametrize("lat_deg,lon_deg", ENABLE_TEST_CASES)
    def test_determinant(self, lat_deg, lon_deg):
        R = standard_enu_basis(lat_deg, lon_deg)
        assert_allclose(np.linalg.det(R), 1.0, atol=1e-12,
                        err_msg=f"lat={lat_deg}, lon={lon_deg}: det != 1")

    @pytest.mark.parametrize("lat_deg,lon_deg", ENABLE_TEST_CASES)
    def test_cross_en_equals_u(self, lat_deg, lon_deg):
        R = standard_enu_basis(lat_deg, lon_deg)
        E, N, U = R[:, 0], R[:, 1], R[:, 2]
        cross_en = np.cross(E, N)
        assert_allclose(cross_en, U, atol=1e-12,
                        err_msg=f"lat={lat_deg}, lon={lon_deg}: E×N != U")

    @pytest.mark.parametrize("lat_deg,lon_deg", ENABLE_TEST_CASES)
    def test_n_z_equals_cos_lat(self, lat_deg, lon_deg):
        """North z-component is cos(lat), NOT zero (non-pole)."""
        R = standard_enu_basis(lat_deg, lon_deg)
        N = R[:, 1]
        expected_N_z = np.cos(np.radians(lat_deg))
        assert_allclose(N[2], expected_N_z, atol=1e-12,
                        err_msg=f"lat={lat_deg}, lon={lon_deg}: N_z != cos(lat)")

    @pytest.mark.parametrize("lat_deg,lon_deg", ENABLE_TEST_CASES)
    def test_u_z_equals_sin_lat(self, lat_deg, lon_deg):
        """Up z-component is sin(lat)."""
        R = standard_enu_basis(lat_deg, lon_deg)
        U = R[:, 2]
        expected_U_z = np.sin(np.radians(lat_deg))
        assert_allclose(U[2], expected_U_z, atol=1e-12,
                        err_msg=f"lat={lat_deg}, lon={lon_deg}: U_z != sin(lat)")

    @pytest.mark.parametrize("lat_deg,lon_deg", ENABLE_TEST_CASES)
    def test_e_z_is_zero(self, lat_deg, lon_deg):
        """East z-component is always zero (tangent to parallels)."""
        R = standard_enu_basis(lat_deg, lon_deg)
        E = R[:, 0]
        assert_allclose(E[2], 0.0, atol=1e-12,
                        err_msg=f"lat={lat_deg}, lon={lon_deg}: E_z != 0")

    @pytest.mark.parametrize("lat_deg,lon_deg", ENABLE_TEST_CASES)
    def test_n_z_at_pole(self, lat_deg, lon_deg):
        """At the geographic poles N_z = 0 by definition."""
        if abs(lat_deg) < 89.0:
            pytest.skip("Only meaningful very close to poles")
        R = standard_enu_basis(lat_deg, lon_deg)
        N = R[:, 1]
        assert_allclose(N[2], 0.0, atol=1e-6,
                        err_msg=f"lat={lat_deg}, lon={lon_deg}: N_z != 0 at pole")


# ------------------------------------------------------------------
# Cross-check against frame_transform.enu_basis_from_geodetic
# ------------------------------------------------------------------
class TestEnuBasisMatchesFrameTransform:
    """Verify script build_enu_basis matches src/leodtf/frame_transform."""

    @pytest.mark.parametrize("lat_deg,lon_deg", ENABLE_TEST_CASES)
    def test_script_build_enu_matches_standard(self, lat_deg, lon_deg):
        """script build_enu_basis must equal the standard formula."""
        from leodtf import frame_transform

        # Reference: standard formula
        R_ref = standard_enu_basis(lat_deg, lon_deg)

        # Actual: frame_transform implementation
        R_actual = frame_transform.enu_basis_from_geodetic(lat_deg, lon_deg)

        assert_allclose(R_actual, R_ref, atol=1e-12,
                        err_msg=f"Mismatch at lat={lat_deg}, lon={lon_deg}")

    @pytest.mark.parametrize("lat_deg,lon_deg", ENABLE_TEST_CASES)
    def test_build_enu_script_matches_standard(self, lat_deg, lon_deg):
        """The build_enu_basis in scripts must equal the standard formula."""
        # Import the build_enu_basis from run_monte_carlo_synthetic
        # (all script versions use identical code)
        import sys
        sys.path.insert(0, "scripts")
        from run_monte_carlo_synthetic import build_enu_basis

        R_standard = standard_enu_basis(lat_deg, lon_deg)
        R_script  = build_enu_basis(lat_deg, lon_deg)

        assert_allclose(R_script, R_standard, atol=1e-12,
                        err_msg=f"script build_enu_basis mismatch at lat={lat_deg}, lon={lon_deg}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])