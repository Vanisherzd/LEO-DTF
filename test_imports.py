import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from leodtf.frame_transform import geodetic_to_ecef
    print("frame_transform import ok")
except Exception as e:
    print(f"frame_transform import failed: {e}")

try:
    from leodtf.observation_model import ObservationModel
    print("observation_model import ok")
except Exception as e:
    print(f"observation_model import failed: {e}")

try:
    from leodtf.jacobian_crlb import compute_crlb_en_position
    print("jacobian_crlb import ok")
except Exception as e:
    print(f"jacobian_crlb import failed: {e}")

try:
    from leodtf.orbit_propagation import propagate_orbit
    print("orbit_propagation import ok")
except Exception as e:
    print(f"orbit_propagation import failed: {e}")

try:
    from leodtf.tle_loader import parse_tle
    print("tle_loader import ok")
except Exception as e:
    print(f"tle_loader import failed: {e}")