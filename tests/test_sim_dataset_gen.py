"""Tests for the synthetic dataset generator."""

import numpy as np
import pytest
from leodtf.sim_dataset_gen import (
    generate_synthetic_pass_dataset,
    export_dataset_json,
    export_dataset_csv,
)
import tempfile
import os
import json


def test_output_length():
    """Output arrays have the expected number of elements."""
    ds = generate_synthetic_pass_dataset(
        duration_s=300.0,
        sample_interval_s=30.0,
        seed=0,
    )
    expected = int(round(300.0 / 30.0)) + 1  # 11
    assert len(ds["time_offsets_s"]) == expected
    assert len(ds["clean_doppler_hz"]) == expected
    assert len(ds["observed_doppler_hz"]) == expected
    assert len(ds["clean_delay_s"]) == expected
    assert len(ds["observed_delay_s"]) == expected
    assert len(ds["satellite_positions_ecef_km"]) == expected


def test_reproducibility_same_seed():
    """Same seed produces identical outputs."""
    kwargs = dict(
        true_lat_deg=25.0,
        true_lon_deg=121.0,
        duration_s=120.0,
        sample_interval_s=30.0,
        doppler_noise_std=1.0,
        seed=12345,
    )
    ds1 = generate_synthetic_pass_dataset(**kwargs)
    ds2 = generate_synthetic_pass_dataset(**kwargs)
    for key in ["observed_doppler_hz", "observed_delay_s", "time_offsets_s"]:
        assert ds1[key] == ds2[key], f"Mismatch in {key}"


def test_reproducibility_different_seed():
    """Different seed produces different noise realizations."""
    kwargs = dict(
        duration_s=120.0,
        sample_interval_s=30.0,
        doppler_noise_std=2.0,
    )
    ds1 = generate_synthetic_pass_dataset(**kwargs, seed=1)
    ds2 = generate_synthetic_pass_dataset(**kwargs, seed=2)
    assert ds1["observed_doppler_hz"] != ds2["observed_doppler_hz"]


def test_zero_noise_observed_equals_clean_plus_nuisance():
    """When noise std = 0, observed = clean + cfo + drift for doppler,
    and observed = clean + time_offset for delay."""
    cfo = 100.0
    drift = 0.05
    time_offset = 2e-3
    ds = generate_synthetic_pass_dataset(
        cfo_hz=cfo,
        drift_hz_per_s=drift,
        time_offset_s=time_offset,
        doppler_noise_std=0.0,
        delay_noise_std=0.0,
        duration_s=300.0,
        sample_interval_s=30.0,
        seed=0,
    )
    t = np.array(ds["time_offsets_s"])
    clean_d = np.array(ds["clean_doppler_hz"])
    obs_d = np.array(ds["observed_doppler_hz"])
    np.testing.assert_allclose(obs_d, clean_d + cfo + drift * t, rtol=1e-10)

    clean_tau = np.array(ds["clean_delay_s"])
    obs_tau = np.array(ds["observed_delay_s"])
    np.testing.assert_allclose(obs_tau, clean_tau + time_offset, rtol=1e-10)


def test_all_required_fields_present():
    """Every required field is present in the output dict."""
    ds = generate_synthetic_pass_dataset(seed=0)
    required = [
        "time_offsets_s",
        "satellite_positions_ecef_km",
        "satellite_velocities_ecef_km_s",
        "true_receiver_ecef_km",
        "true_receiver_geodetic",
        "clean_doppler_hz",
        "observed_doppler_hz",
        "clean_delay_s",
        "observed_delay_s",
        "cfo_hz",
        "drift_hz_per_s",
        "time_offset_s",
        "doppler_noise_std_hz",
        "delay_noise_std_s",
        "carrier_hz",
        "duration_s",
        "sample_interval_s",
        "seed",
        "orbit_altitude_km",
        "orbit_inclination_deg",
    ]
    for field in required:
        assert field in ds, f"Missing field: {field}"


def test_synthetic_orbit_fallback():
    """No TLE produces a valid dataset using synthetic orbit."""
    ds = generate_synthetic_pass_dataset(seed=0)
    pos = np.array(ds["satellite_positions_ecef_km"])
    assert pos.shape[1] == 3
    # Altitude should be near 400 km (Earth radius ~6378 km)
    norms = np.linalg.norm(pos, axis=1)
    assert 6700 < norms.min() < 6900, f"Unexpected altitude: {norms.min()}"
    assert 6700 < norms.max() < 6900


def test_geodetic_roundtrip():
    """True receiver geodetic coordinates are preserved."""
    ds = generate_synthetic_pass_dataset(
        true_lat_deg=35.7,
        true_lon_deg=139.7,
        true_alt_m=50.0,
        seed=0,
    )
    geo = ds["true_receiver_geodetic"]
    assert abs(geo["lat_deg"] - 35.7) < 1e-9
    assert abs(geo["lon_deg"] - 139.7) < 1e-9
    assert abs(geo["alt_m"] - 50.0) < 1e-9


def test_export_json():
    """JSON export round-trips correctly."""
    ds = generate_synthetic_pass_dataset(seed=0)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "ds.json")
        export_dataset_json(ds, path)
        with open(path) as f:
            loaded = json.load(f)
    assert loaded["carrier_hz"] == ds["carrier_hz"]
    assert len(loaded["time_offsets_s"]) == len(ds["time_offsets_s"])


def test_export_csv():
    """CSV export has correct headers and row count."""
    ds = generate_synthetic_pass_dataset(duration_s=120.0, sample_interval_s=30.0, seed=0)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "obs.csv")
        export_dataset_csv(ds, path)
        with open(path) as f:
            lines = f.readlines()
    assert lines[0].startswith("time_s")
    expected_rows = len(ds["time_offsets_s"])
    assert len(lines) == expected_rows + 1  # +1 header


if __name__ == "__main__":
    pytest.main([__file__, "-v"])