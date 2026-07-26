"""
Structured data contracts shared across the whole application.

Every value that crosses a boundary (EnergyPlus -> sensors, agent -> MCP
tools, agent -> controller, controller -> logs/dashboard) is validated
through one of these Pydantic models so malformed data is caught early
instead of silently corrupting the control loop.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class BuildingState(BaseModel):
    """A single normalized snapshot of the building at one simulation timestep."""

    timestamp: datetime
    zone_name: str
    zone_temperature: float = Field(..., description="Zone air temperature (C)")
    outdoor_temperature: float = Field(..., description="Outdoor dry-bulb temperature (C)")
    occupancy: float = Field(..., ge=0, description="Number of people currently in the zone")
    cooling_setpoint: float = Field(..., description="Current cooling setpoint (C)")
    heating_setpoint: float = Field(..., description="Current heating setpoint (C)")
    hvac_electricity_w: float = Field(..., ge=0, description="Instantaneous HVAC electric power (W)")
    total_electricity_w: float = Field(..., ge=0, description="Instantaneous total facility electric power (W)")
    cooling_load_w: float = Field(0.0, description="Zone sensible cooling load (W)")
    heating_load_w: float = Field(0.0, description="Zone sensible heating load (W)")
    pmv: Optional[float] = Field(None, description="Predicted Mean Vote thermal comfort index")
    humidity_percent: Optional[float] = Field(None, description="Zone relative humidity (%)")
    simulation_day: int = Field(..., ge=1)
    simulation_hour: int = Field(..., ge=0, le=23)

    def is_occupied(self) -> bool:
        return self.occupancy > 0.01


class ActionType(str, Enum):
    CHANGE_COOLING_SETPOINT = "change_cooling_setpoint"
    CHANGE_HEATING_SETPOINT = "change_heating_setpoint"
    CHANGE_BOTH_SETPOINTS = "change_both_setpoints"
    NO_ACTION = "no_action"


class AgentDecision(BaseModel):
    """Structured decision returned by the LLM agent (or the fallback controller)."""

    action: ActionType
    cooling_setpoint: Optional[float] = Field(
        None, description="Requested new cooling setpoint (C), if applicable"
    )
    heating_setpoint: Optional[float] = Field(
        None, description="Requested new heating setpoint (C), if applicable"
    )
    reason: str = Field(..., min_length=3, max_length=400)
    expected_effect: str = Field(..., min_length=3, max_length=400)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: str = Field("llm", description="'llm' or 'fallback'")

    @field_validator("cooling_setpoint", "heating_setpoint")
    @classmethod
    def _reasonable_temperature(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if not (0.0 <= v <= 45.0):
            raise ValueError("Setpoint out of physically reasonable range (0-45C)")
        return v


class ValidatedAction(BaseModel):
    """The final, constraint-checked action that is actually applied to EnergyPlus."""

    cooling_setpoint: float
    heating_setpoint: float
    was_clamped: bool
    clamp_reasons: list[str] = Field(default_factory=list)
    source: str


class DecisionLogEntry(BaseModel):
    """One row of the agent decision audit log used by the dashboard."""

    timestamp: datetime
    building_state_summary: str
    action: str
    old_cooling_setpoint: float
    new_cooling_setpoint: float
    old_heating_setpoint: float
    new_heating_setpoint: float
    reason: str
    expected_effect: str
    result: str
    tool_used: str
    confidence: float
    source: str
