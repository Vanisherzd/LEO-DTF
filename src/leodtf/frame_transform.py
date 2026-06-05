"""Frame Transform for LEO-DTF
---------------------------
Handles coordinate transformations between different reference frames (WGS84, ECEF, ENU).
"""

import numpy as np

# WGS84 constants
WGS84_A = 6378.137  # semi-major axis in km
WGS84_F = 1 / 298.257223563  # flattening
WGS84_E2 = WGS84_F * (2 - WGS84_F)  # square of first eccentricity
WGS84_B = WGS84_A * (1 - WGS84_F)  # semi-minor axis in km


def geodetic_to_ecef(lat, lon, alt):
    """
    Convert geodetic coordinates (latitude, longitude, altitude) to ECEF.

    Parameters
    ----------
    lat : float or ndarray
        Latitude in degrees.
    lon : float or ndarray
        Longitude in degrees.
    alt : float or ndarray
        Altitude above WGS84 ellipsoid in km.

    Returns
    -------
    x, y, z : float or ndarray
        ECEF coordinates in km.
    """
    # Convert degrees to radians
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)

    # Prime vertical radius of curvature
    N = WGS84_A / np.sqrt(1 - WGS84_E2 * np.sin(lat_rad)**2)

    x = (N + alt) * np.cos(lat_rad) * np.cos(lon_rad)
    y = (N + alt) * np.cos(lat_rad) * np.sin(lon_rad)
    z = (N * (1 - WGS84_E2) + alt) * np.sin(lat_rad)

    return x, y, z


def ecef_to_geodetic(x, y, z):
    """
    Convert ECEF coordinates to geodetic (latitude, longitude, altitude).
    Uses Bowring's method for simplicity (iterative, but we use a direct approximation).

    Parameters
    ----------
    x, y, z : float or ndarray
        ECEF coordinates in km.

    Returns
    -------
    lat, lon, alt : float or ndarray
        Latitude and longitude in degrees, altitude in km.
    """
    lon = np.arctan2(y, x)
    p = np.sqrt(x**2 + y**2)
    # Initial guess for latitude
    lat = np.arctan2(z, p * (1 - WGS84_E2))
    # Iterate a few times for better accuracy (we do 2 iterations)
    for _ in range(2):
        N = WGS84_A / np.sqrt(1 - WGS84_E2 * np.sin(lat)**2)
        alt = p / np.cos(lat) - N
        lat = np.arctan2(z, p * (1 - WGS84_E2 * N / (N + alt)))
    lat = np.degrees(lat)
    lon = np.degrees(lon)
    alt = p / np.cos(np.radians(lat)) - WGS84_A / np.sqrt(1 - WGS84_E2 * np.sin(np.radians(lat))**2)
    return lat, lon, alt


def enu_basis_from_geodetic(lat0, lon0):
    """
    Compute the ENU basis vectors (columns of the rotation matrix) at a given geodetic point.

    Parameters
    ----------
    lat0 : float
        Reference latitude in degrees.
    lon0 : float
        Reference longitude in degrees.

    Returns
    -------
    R : ndarray of shape (3, 3)
        Rotation matrix from ENU to ECEF (columns are unit vectors of E, N, U in ECEF).
    """
    lat0_rad = np.radians(lat0)
    lon0_rad = np.radians(lon0)

    # East unit vector in ECEF
    e_ecef = np.array([-np.sin(lon0_rad), np.cos(lon0_rad), 0])
    # North unit vector in ECEF
    n_ecef = np.array([-np.sin(lat0_rad) * np.cos(lon0_rad),
                       -np.sin(lat0_rad) * np.sin(lon0_rad),
                       np.cos(lat0_rad)])
    # Up unit vector in ECEF (same as unit vector from ellipsoid center to point)
    u_ecef = np.array([np.cos(lat0_rad) * np.cos(lon0_rad),
                       np.cos(lat0_rad) * np.sin(lon0_rad),
                       np.sin(lat0_rad)])

    R = np.column_stack((e_ecef, n_ecef, u_ecef))
    return R


def enu_to_ecef(e, n, u, lat0, lon0, alt0=0):
    """
    Convert local ENU coordinates to ECEF.

    Parameters
    ----------
    e, n, u : float or ndarray
        Local East, North, Up coordinates in km.
    lat0, lon0 : float
        Reference geodetic latitude and longitude in degrees.
    alt0 : float, optional
        Reference altitude in km (default 0).

    Returns
    -------
    x, y, z : float or ndarray
        ECEF coordinates in km.
    """
    # Get the reference point in ECEF
    x0, y0, z0 = geodetic_to_ecef(lat0, lon0, alt0)
    # Get the rotation matrix from ENU to ECEF at the reference point
    R = enu_basis_from_geodetic(lat0, lon0)
    # Convert ENU vector to ECEF vector and add the reference point
    enu_vec = np.array([e, n, u])
    ecef_vec = np.dot(R, enu_vec) + np.array([x0, y0, z0])
    return ecef_vec[0], ecef_vec[1], ecef_vec[2]


def ecef_to_enu(x, y, z, lat0, lon0, alt0=0):
    """
    Convert ECEF coordinates to local ENU.

    Parameters
    ----------
    x, y, z : float or ndarray
        ECEF coordinates in km.
    lat0, lon0 : float
        Reference geodetic latitude and longitude in degrees.
    alt0 : float, optional
        Reference altitude in km (default 0).

    Returns
    -------
    e, n, u : float or ndarray
        Local East, North, Up coordinates in km.
    """
    # Get the reference point in ECEF
    x0, y0, z0 = geodetic_to_ecef(lat0, lon0, alt0)
    # Vector from reference point to the point of interest
    ecef_vec = np.array([x - x0, y - y0, z - z0])
    # Get the rotation matrix from ENU to ECEF at the reference point
    R = enu_basis_from_geodetic(lat0, lon0)
    # The inverse of R is its transpose (since it's orthonormal)
    enu_vec = np.dot(R.T, ecef_vec)
    return enu_vec[0], enu_vec[1], enu_vec[2]


def gmst_from_jd(jd_utc):
    """
    Compute Greenwich Mean Sidereal Time (GMST) from Julian Date UTC.
    Uses the formula from the US Naval Observatory (approximate).

    Parameters
    ----------
    jd_utc : float or ndarray
        Julian Date UTC.

    Returns
    -------
    gmst : float or ndarray
        GMST in radians.
    """
    # Number of Julian centuries from J2000.0
    t = (jd_utc - 2451545.0) / 36525.0
    # GMST in seconds at 0h UT1
    gmst_sec = 24110.54841 + 8640184.812866 * t + 0.093104 * t**2 - 6.2e-6 * t**3
    # Convert to radians and adjust for the time of day
    gmst_rad = np.radians((gmst_sec % 86400) * 15.04106864 / 3600.0)
    return gmst_rad


def teme_to_ecef(pos_teme, vel_teme, jd_utc):
    """
    Convert TEME (True Equator, Mean Equinox) coordinates to ECEF.
    This is a simplified version that ignores nutation and polar motion.
    For high accuracy, one should use IAU 2006/2009 precession and nutation models.

    Parameters
    ----------
    pos_teme : ndarray of shape (3,)
        Position vector in TEME (km).
    vel_teme : ndarray of shape (3,)
        Velocity vector in TEME (km/s).
    jd_utc : float
        Julian Date UTC.

    Returns
    -------
    pos_ecef : ndarray of shape (3,)
        Position vector in ECEF (km).
    vel_ecef : ndarray of shape (3,)
        Velocity vector in ECEF (km/s).
    """
    # Get GMST
    gmst = gmst_from_jd(jd_utc)
    # Rotation matrix about the z-axis
    R = np.array([[np.cos(gmst), np.sin(gmst), 0],
                  [-np.sin(gmst), np.cos(gmst), 0],
                  [0, 0, 1]])
    pos_ecef = np.dot(R, pos_teme)
    # Velocity: include the rotation effect due to Earth's rotation
    # omega_earth = 7.2921151467e-5 rad/s (Earth's rotation rate)
    omega_earth = 7.2921151467e-5
    # Velocity in ECEF: R * vel_teme + omega_earth cross (R * pos_teme)
    vel_ecef = np.dot(R, vel_teme) + np.cross([0, 0, omega_earth], pos_ecef)
    return pos_ecef, vel_ecef


if __name__ == "__main__":
    # Example usage (for testing)
    # Convert a geodetic point to ECEF and back
    lat, lon, alt = 40.0, -105.0, 1.5  # Boulder, CO
    x, y, z = geodetic_to_ecef(lat, lon, alt)
    print(f"ECEF: {x:.2f}, {y:.2f}, {z:.2f} km")
    lat2, lon2, alt2 = ecef_to_geodetic(x, y, z)
    print(f"Geodetic: {lat2:.2f}°, {lon2:.2f}°, {alt2:.2f} km")

    # Test ENU basis
    R = enu_basis_from_geodetic(lat, lon)
    print("ENU to ECEF rotation matrix (columns: E, N, U):")
    print(R)
    # Convert a local ENU vector to ECEF
    e, n, u = 0.1, 0.2, 0.3  # km
    x2, y2, z2 = enu_to_ecef(e, n, u, lat, lon, alt)
    print(f"ENU ({e}, {n}, {u}) km -> ECEF: {x2:.2f}, {y2:.2f}, {z2:.2f} km")
    # Convert back
    e2, n2, u2 = ecef_to_enu(x2, y2, z2, lat, lon, alt)
    print(f"ECEF -> ENU: {e2:.2f}, {n2:.2f}, {u2:.2f} km")