"""
Metrics computation over a run's captured BuildingState timeseries.

All functions operate on a pandas DataFrame with (at least) the columns
produced by app.control.closed_loop._write_states_csv, i.e. the fields
of app.agent.schemas.BuildingState.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd
from app.config import settings


def _timestep_hours(df: pd.DataFrame) -> float:
    """Estimate the timestep duration in hours from consecutive timestamps."""
    if len(df) < 2:
        return 15.0 / 60.0
    ts = pd.to_datetime(df["timestamp"]).sort_values().reset_index(drop=True)
    deltas = (ts.diff().dropna().dt.total_seconds() / 3600.0)
    deltas = deltas[deltas > 0]
    if deltas.empty:
        return 15.0 / 60.0
    return float(deltas.median())


def total_energy_kwh(df: pd.DataFrame, column: str = "total_electricity_w") -> float:
    """Integrate an instantaneous power column (W) into total energy (kWh)."""
    if df.empty or column not in df.columns:
        return 0.0
    dt_hours = _timestep_hours(df)
    watt_hours = df[column].astype(float).sum() * dt_hours
    return round(watt_hours / 1000.0, 3)

def estimated_hvac_energy_kwh(
    df: pd.DataFrame,
    cooling_cop: float = 3.0,
    heating_cop: float = 3.0,
) -> float:
    """
    Estimate HVAC electrical energy from EnergyPlus Ideal Loads thermal loads.

    ZoneHVAC:IdealLoadsAirSystem reports thermal heating/cooling demand but
    does not represent physical electrical HVAC equipment, so direct facility
    HVAC electricity is zero. For PoC comparison, convert thermal load to
    equivalent electrical input using documented COP assumptions.
    """
    if df.empty:
        return 0.0

    dt_hours = _timestep_hours(df)

    cooling_w = (
        df["cooling_load_w"].astype(float).clip(lower=0)
        if "cooling_load_w" in df.columns
        else 0.0
    )

    heating_w = (
        df["heating_load_w"].astype(float).clip(lower=0)
        if "heating_load_w" in df.columns
        else 0.0
    )

    electrical_w = (cooling_w / cooling_cop) + (heating_w / heating_cop)

    return round(float(electrical_w.sum()) * dt_hours / 1000.0, 3)


def peak_demand_w(df: pd.DataFrame, column: str = "total_electricity_w") -> float:
    if df.empty or column not in df.columns:
        return 0.0
    return round(float(df[column].astype(float).max()), 2)


def average_zone_temperature(df: pd.DataFrame) -> float:
    if df.empty or "zone_temperature" not in df.columns:
        return 0.0
    return round(float(df["zone_temperature"].astype(float).mean()), 2)


def comfort_compliance_percent(df: pd.DataFrame) -> float:
    """
    Percentage of OCCUPIED timesteps where the zone temperature stayed
    within [OCCUPIED_TEMP_MIN, OCCUPIED_TEMP_MAX].
    """
    if df.empty:
        return 100.0
    c = settings.constraints
    occupied = df[df["occupancy"].astype(float) > 0.01]
    if occupied.empty:
        return 100.0
    in_band = occupied[
        (occupied["zone_temperature"].astype(float) >= c.occupied_temp_min)
        & (occupied["zone_temperature"].astype(float) <= c.occupied_temp_max)
    ]
    return round(100.0 * len(in_band) / len(occupied), 2)


def pmv_statistics(df: pd.DataFrame) -> dict:
    if df.empty or "pmv" not in df.columns:
        return {"mean": None, "min": None, "max": None}
    pmv = df["pmv"].dropna().astype(float)
    if pmv.empty:
        return {"mean": None, "min": None, "max": None}
    return {
        "mean": round(float(pmv.mean()), 3),
        "min": round(float(pmv.min()), 3),
        "max": round(float(pmv.max()), 3),
    }


def summarize_run(df: pd.DataFrame) -> dict:
    base_electricity_kwh = total_energy_kwh(df)
    estimated_hvac_kwh = estimated_hvac_energy_kwh(df)

    return {
        "total_energy_kwh": round(
            base_electricity_kwh + estimated_hvac_kwh, 3
        ),
        "hvac_energy_kwh": estimated_hvac_kwh,
        "peak_demand_w": peak_demand_w(df),
        "average_zone_temperature_c": average_zone_temperature(df),
        "comfort_compliance_percent": comfort_compliance_percent(df),
        "pmv": pmv_statistics(df),
        "num_timesteps": int(len(df)),
    }
