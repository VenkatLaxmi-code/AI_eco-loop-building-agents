"""
Actuator layer: applies validated HVAC setpoint changes back into the
running EnergyPlus simulation using EMS actuators.

The baseline.idf model exposes two Schedule:Constant objects
(CLG_SETPOINT_SCHED and HTG_SETPOINT_SCHED) that drive the zone
thermostat via a ZoneControl:Thermostat / ThermostatSetpoint:DualSetpoint
pair. Both schedules are declared with EMS "Actuate" access in the IDF
(see models/baseline.idf, the "ActuatorAvailability" comment block),
which lets this module override their value every control interval
without editing the IDF or restarting the simulation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("actuators")


@dataclass
class ActuatorHandles:
    cooling_setpoint: int = -1
    heating_setpoint: int = -1
    resolved: bool = False


class ActuatorController:
    """Resolves and writes to the EnergyPlus EMS actuators for setpoint control."""

    COOLING_SCHEDULE_NAME = "CLG_SETPOINT_SCHED"
    HEATING_SCHEDULE_NAME = "HTG_SETPOINT_SCHED"

    def __init__(self) -> None:
        self.handles = ActuatorHandles()
        # Track the last applied values so the runner can report the
        # "current setpoint" sensor reading even between control steps.
        self.current_cooling_setpoint: float = 24.0
        self.current_heating_setpoint: float = 21.0

    def resolve_handles(self, api, state) -> bool:
        ex = api.exchange
        if not ex.api_data_fully_ready(state):
            return False

        self.handles.cooling_setpoint = ex.get_actuator_handle(
            state, "Schedule:Constant", "Schedule Value", self.COOLING_SCHEDULE_NAME
        )
        self.handles.heating_setpoint = ex.get_actuator_handle(
            state, "Schedule:Constant", "Schedule Value", self.HEATING_SCHEDULE_NAME
        )
        self.handles.resolved = (
            self.handles.cooling_setpoint != -1 and self.handles.heating_setpoint != -1
        )
        if not self.handles.resolved:
            logger.error(
                "Failed to resolve actuator handles (cooling=%s, heating=%s). "
                "Verify Schedule:Constant object names in the IDF match "
                "CLG_SETPOINT_SCHED / HTG_SETPOINT_SCHED.",
                self.handles.cooling_setpoint,
                self.handles.heating_setpoint,
            )
        return self.handles.resolved

    def apply(self, api, state, cooling_setpoint: float, heating_setpoint: float) -> None:
        """Write the validated setpoints into the running simulation."""
        if not self.handles.resolved:
            raise RuntimeError("Actuator handles not resolved yet; cannot apply setpoints.")

        ex = api.exchange
        ex.set_actuator_value(state, self.handles.cooling_setpoint, cooling_setpoint)
        ex.set_actuator_value(state, self.handles.heating_setpoint, heating_setpoint)
        self.current_cooling_setpoint = cooling_setpoint
        self.current_heating_setpoint = heating_setpoint
        logger.debug(
            "Applied setpoints -> cooling=%.2fC heating=%.2fC", cooling_setpoint, heating_setpoint
        )

    def initialize_defaults(
        self, api, state, cooling_setpoint: float, heating_setpoint: float
    ) -> None:
        """Push the initial setpoints as soon as handles are resolved."""
        self.apply(api, state, cooling_setpoint, heating_setpoint)
