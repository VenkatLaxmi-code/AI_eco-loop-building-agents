"""
Unit tests for app.analytics.metrics and app.analytics.comparison.

Uses small synthetic DataFrames shaped like the CSVs the closed loop
writes (see app.control.closed_loop._write_states_csv) so these tests
never require a real EnergyPlus run.
"""
from __future__ import annotations

import pandas as pd

from app.analytics.comparison import compute_savings_percent
from app.analytics.metrics import (
    average_zone_temperature,
    comfort_compliance_percent,
    peak_demand_w,
    pmv_statistics,
    total_energy_kwh,
)


def _sample_df() -> pd.DataFrame:
    # 4 timesteps, 15 minutes apart -> 1 hour of data.
    timestamps = pd.date_range("2024-07-01 08:00", periods=4, freq="15min")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "zone_temperature": [23.0, 24.0, 25.0, 30.0],
            "occupancy": [5, 5, 5, 0],
            "total_electricity_w": [1000.0, 1200.0, 1500.0, 200.0],
            "hvac_electricity_w": [600.0, 700.0, 900.0, 50.0],
            "pmv": [0.1, 0.3, 0.6, 1.2],
        }
    )


def test_total_energy_kwh_integrates_power_over_time():
    df = _sample_df()
    # Average power ~975W over 1 hour ~= 0.975 kWh; each row is 15 min (0.25h).
    expected = round((1000 + 1200 + 1500 + 200) * 0.25 / 1000.0, 3)
    assert total_energy_kwh(df) == expected


def test_peak_demand_returns_max():
    df = _sample_df()
    assert peak_demand_w(df) == 1500.0


def test_average_zone_temperature():
    df = _sample_df()
    assert average_zone_temperature(df) == round((23 + 24 + 25 + 30) / 4, 2)


def test_comfort_compliance_percent_only_counts_occupied_rows():
    df = _sample_df()
    # Occupied rows: temps 23, 24, 25 (all comfortable with default 20-27 band);
    # the unoccupied row (30C) must be excluded from the calculation entirely.
    result = comfort_compliance_percent(df)
    assert result == 100.0


def test_comfort_compliance_detects_violation():
    df = _sample_df()
    df.loc[0, "zone_temperature"] = 35.0  # occupied but way too hot
    result = comfort_compliance_percent(df)
    assert result < 100.0


def test_pmv_statistics():
    df = _sample_df()
    stats = pmv_statistics(df)
    assert stats["min"] == 0.1
    assert stats["max"] == 1.2


def test_empty_dataframe_returns_safe_defaults():
    empty = pd.DataFrame(columns=["timestamp", "zone_temperature", "occupancy", "total_electricity_w"])
    assert total_energy_kwh(empty) == 0.0
    assert peak_demand_w(empty) == 0.0
    assert average_zone_temperature(empty) == 0.0
    assert comfort_compliance_percent(empty) == 100.0


def test_energy_savings_percent_formula():
    # ((baseline - ai) / baseline) * 100
    result = compute_savings_percent(baseline_kwh=100.0, ai_kwh=80.0)
    assert result == 20.0


def test_energy_savings_percent_handles_zero_baseline():
    result = compute_savings_percent(baseline_kwh=0.0, ai_kwh=10.0)
    assert result == 0.0


def test_energy_savings_percent_negative_when_ai_uses_more():
    result = compute_savings_percent(baseline_kwh=100.0, ai_kwh=120.0)
    assert result == -20.0
