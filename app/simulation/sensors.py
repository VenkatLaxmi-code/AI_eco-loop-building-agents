"""
Sensor layer: turns raw EnergyPlus variable handles into a normalized
BuildingState object that the rest of the application understands.

This module never talks to EnergyPlus directly for I/O other than the
`exchange` API object it is given by EnergyPlusRunner - it purely knows
how to request the right variables/handles and convert their values.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from app.agent.schemas import BuildingState
from app.config import settings


class SensorHandles:
    """Holds the integer variable handles resolved once EnergyPlus data is ready."""

    def __init__(self) -> None:
        self.zone_temp: int = -1
        self.outdoor_temp: int = -1
        self.occupancy_count: int = -1
        self.hvac_electricity: int = -1
        self.total_electricity: int = -1
        self.cooling_load: int = -1
        self.heating_load: int = -1
        self.zone_humidity: int = -1
        self.cooling_setpoint_actuator: int = -1
        self.heating_setpoint_actuator: int = -1
        self.resolved: bool = False


class SensorReader:
    """
    Requests the EnergyPlus output variables needed by the agent and,
    once the simulation's data exchange API is ready, reads their
    current values and produces a validated BuildingState.
    """

    # Variable name, key -> used both for request_variable() and get_variable_handle()
    VARIABLES = [
        ("Zone Mean Air Temperature", None),  # key filled with zone name
        ("Site Outdoor Air Drybulb Temperature", "Environment"),
        ("Zone People Occupant Count", None),
        ("Facility Total HVAC Electricity Demand Rate", "Whole Building"),
        ("Facility Total Electricity Demand Rate", "Whole Building"),
        ("Zone Air System Sensible Cooling Rate", None),
        ("Zone Air System Sensible Heating Rate", None),
        ("Zone Air Relative Humidity", None),
    ]

    def __init__(self, zone_name: str = None):
        self.zone_name = zone_name or settings.energyplus.zone_name
        self.handles = SensorHandles()

    def request_variables(self, api, state) -> None:
        """
        Must be called BEFORE the simulation warms up (typically inside a
        callback_begin_new_environment or right at simulation start) so
        EnergyPlus knows to track these outputs during the run.
        """
        ex = api.exchange
        ex.request_variable(state, "Zone Mean Air Temperature", self.zone_name)
        ex.request_variable(state, "Site Outdoor Air Drybulb Temperature", "Environment")
        ex.request_variable(state, "Zone People Occupant Count", self.zone_name)
        ex.request_variable(state, "Facility Total HVAC Electricity Demand Rate", "Whole Building")
        ex.request_variable(state, "Facility Total Electricity Demand Rate", "Whole Building")
        ex.request_variable(state, "Zone Air System Sensible Cooling Rate", self.zone_name)
        ex.request_variable(state, "Zone Air System Sensible Heating Rate", self.zone_name)
        ex.request_variable(state, "Zone Air Relative Humidity", self.zone_name)

    def resolve_handles(self, api, state) -> bool:
        """
        Resolve integer variable handles. Only valid after
        exchange.api_data_fully_ready(state) is True. Returns True once
        all handles are successfully resolved.
        """
        ex = api.exchange
        if not ex.api_data_fully_ready(state):
            return False

        h = self.handles
        h.zone_temp = ex.get_variable_handle(state, "Zone Mean Air Temperature", self.zone_name)
        h.outdoor_temp = ex.get_variable_handle(
            state, "Site Outdoor Air Drybulb Temperature", "Environment"
        )
        h.occupancy_count = ex.get_variable_handle(
            state, "Zone People Occupant Count", self.zone_name
        )
        h.hvac_electricity = ex.get_variable_handle(
            state, "Facility Total HVAC Electricity Demand Rate", "Whole Building"
        )
        h.total_electricity = ex.get_variable_handle(
            state, "Facility Total Electricity Demand Rate", "Whole Building"
        )
        h.cooling_load = ex.get_variable_handle(
            state, "Zone Air System Sensible Cooling Rate", self.zone_name
        )
        h.heating_load = ex.get_variable_handle(
            state, "Zone Air System Sensible Heating Rate", self.zone_name
        )
        h.zone_humidity = ex.get_variable_handle(
            state, "Zone Air Relative Humidity", self.zone_name
        )

        resolved = all(
            handle_value != -1
            for handle_value in [
                h.zone_temp,
                h.outdoor_temp,
                h.occupancy_count,
                h.hvac_electricity,
                h.total_electricity,
            ]
        )
        h.resolved = resolved
        return resolved

    @staticmethod
    def _compute_pmv(zone_temp: float, humidity: Optional[float]) -> Optional[float]:
        """
        Lightweight simplified PMV (Predicted Mean Vote) estimate used when
        a full ASHRAE-55 PMV output variable is unavailable in the IDF.
        Based on a simplified linear approximation around neutral comfort
        (~24C, 50% RH) - adequate for comfort-trend reasoning, not a
        replacement for a certified thermal comfort report.
        """
        if humidity is None:
            humidity = 50.0
        neutral_temp = 24.0
        temp_component = (zone_temp - neutral_temp) * 0.28
        humidity_component = (humidity - 50.0) * 0.0035
        pmv = temp_component + humidity_component
        return round(max(-3.0, min(3.0, pmv)), 3)

    def read_state(
        self,
        api,
        state,
        cooling_setpoint: float,
        heating_setpoint: float,
        sim_start: datetime,
    ) -> Optional[BuildingState]:
        """Read the current values from EnergyPlus and build a BuildingState."""
        if not self.handles.resolved:
            return None

        ex = api.exchange
        h = self.handles

        zone_temp = ex.get_variable_value(state, h.zone_temp)
        outdoor_temp = ex.get_variable_value(state, h.outdoor_temp)
        occupancy = ex.get_variable_value(state, h.occupancy_count)
        hvac_elec = ex.get_variable_value(state, h.hvac_electricity)
        total_elec = ex.get_variable_value(state, h.total_electricity)
        cooling_load = ex.get_variable_value(state, h.cooling_load) if h.cooling_load != -1 else 0.0
        heating_load = ex.get_variable_value(state, h.heating_load) if h.heating_load != -1 else 0.0
        humidity = ex.get_variable_value(state, h.zone_humidity) if h.zone_humidity != -1 else None

        day = ex.day_of_month(state)
        hour = ex.hour(state)
        month = ex.month(state)
        minute = ex.minutes(state)

        try:
            timestamp = sim_start.replace(month=month, day=day, hour=hour % 24, minute=min(minute, 59))
        except ValueError:
            timestamp = sim_start + timedelta(hours=hour, minutes=minute)

        sim_day = (timestamp - sim_start).days + 1

        return BuildingState(
            timestamp=timestamp,
            zone_name=self.zone_name,
            zone_temperature=round(float(zone_temp), 3),
            outdoor_temperature=round(float(outdoor_temp), 3),
            occupancy=round(float(occupancy), 2),
            cooling_setpoint=round(float(cooling_setpoint), 2),
            heating_setpoint=round(float(heating_setpoint), 2),
            hvac_electricity_w=max(0.0, round(float(hvac_elec), 2)),
            total_electricity_w=max(0.0, round(float(total_elec), 2)),
            cooling_load_w=round(float(cooling_load), 2),
            heating_load_w=round(float(heating_load), 2),
            pmv=self._compute_pmv(float(zone_temp), humidity),
            humidity_percent=round(float(humidity), 2) if humidity is not None else None,
            simulation_day=max(1, sim_day),
            simulation_hour=hour % 24,
        )
