"""
MCP tool implementations.

These functions are the single source of truth for "what the building
looks like right now" and "what action was just taken". They are wired
into the MCP server (server.py) via @mcp.tool() decorators, AND used
directly by BuildingAgent for the tight synchronous decision loop that
runs inside the EnergyPlus timestep callback (see docs/ARCHITECTURE.md
for why both paths call the exact same functions instead of duplicating
logic: the MCP protocol layer is a thin transport around this module,
never a mock of it).

All state lives in a single thread-safe BuildingStateStore instance
(`STORE`) that is updated once per control step by the closed-loop
controller (`push_building_state`) and read/written by the agent
through the tools below.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import List, Optional

from app.agent.schemas import AgentDecision, BuildingState, ValidatedAction
from app.config import settings
from app.control.constraints import validate_action

logger = logging.getLogger("mcp.tools")


class BuildingStateStore:
    """Thread-safe in-memory store shared by all MCP tool calls for one run."""

    def __init__(self, history_limit: int = 200) -> None:
        self._lock = threading.RLock()
        self.current_state: Optional[BuildingState] = None
        self.history: List[BuildingState] = []
        self.decisions: List[dict] = []
        self.errors: List[str] = []
        self.history_limit = history_limit
        self.last_validated_action: Optional[ValidatedAction] = None

    def push_state(self, state: BuildingState) -> None:
        with self._lock:
            self.current_state = state
            self.history.append(state)
            if len(self.history) > self.history_limit:
                self.history = self.history[-self.history_limit:]

    def push_error(self, message: str) -> None:
        with self._lock:
            self.errors.append(f"{datetime.utcnow().isoformat()} - {message}")

    def record_decision(self, entry: dict) -> None:
        with self._lock:
            self.decisions.append(entry)


STORE = BuildingStateStore()


def _require_state() -> BuildingState:
    if STORE.current_state is None:
        raise RuntimeError(
            "No building state available yet. push_building_state must be called "
            "at least once before other tools are used."
        )
    return STORE.current_state


# ----------------------------------------------------------------------
# Tools (mirrored 1:1 as MCP tools in server.py)
# ----------------------------------------------------------------------
def push_building_state(state_dict: dict) -> dict:
    """Internal tool: ingest the latest EnergyPlus-derived state into the store."""
    state = BuildingState.model_validate(state_dict)
    STORE.push_state(state)
    logger.info("push_building_state: t=%s zone_temp=%.2f occ=%.1f",
                state.timestamp, state.zone_temperature, state.occupancy)
    return {"ok": True}


def get_building_state() -> dict:
    """Return the full current normalized building state."""
    state = _require_state()
    return state.model_dump(mode="json")


def get_zone_temperature() -> dict:
    """Return just the current zone and outdoor temperatures."""
    state = _require_state()
    return {
        "zone_temperature": state.zone_temperature,
        "outdoor_temperature": state.outdoor_temperature,
    }


def get_energy_consumption() -> dict:
    """Return current HVAC and total facility electric power."""
    state = _require_state()
    return {
        "hvac_electricity_w": state.hvac_electricity_w,
        "total_electricity_w": state.total_electricity_w,
        "cooling_load_w": state.cooling_load_w,
        "heating_load_w": state.heating_load_w,
    }


def get_comfort_metrics() -> dict:
    """Return PMV and humidity-based comfort indicators."""
    state = _require_state()
    c = settings.constraints
    in_comfort_band = c.occupied_temp_min <= state.zone_temperature <= c.occupied_temp_max
    return {
        "pmv": state.pmv,
        "humidity_percent": state.humidity_percent,
        "within_occupied_temp_band": in_comfort_band,
        "pmv_within_bounds": (
            state.pmv is not None and c.pmv_min <= state.pmv <= c.pmv_max
        ),
    }


def get_occupancy() -> dict:
    """Return current occupancy count."""
    state = _require_state()
    return {"occupancy": state.occupancy, "is_occupied": state.is_occupied()}


def get_current_setpoints() -> dict:
    """Return the currently active cooling/heating setpoints."""
    state = _require_state()
    return {
        "cooling_setpoint": state.cooling_setpoint,
        "heating_setpoint": state.heating_setpoint,
    }


def get_simulation_errors() -> dict:
    """Return any EnergyPlus / tool errors recorded so far in this run."""
    return {"errors": STORE.errors[-20:], "count": len(STORE.errors)}


def get_recent_history(limit: int = 8) -> dict:
    """Return the last `limit` building states as a compact list."""
    limit = max(1, min(limit, 50))
    tail = STORE.history[-limit:]
    return {"history": [s.model_dump(mode="json") for s in tail]}


def set_cooling_setpoint(value: float) -> dict:
    """
    Propose a new cooling setpoint. The value is validated against the
    deterministic safety/comfort constraints before being accepted -
    the returned value may differ from the requested one if it was
    clamped.
    """
    state = _require_state()
    decision = AgentDecision(
        action="change_cooling_setpoint",
        cooling_setpoint=value,
        heating_setpoint=None,
        reason="Direct MCP tool call: set_cooling_setpoint",
        expected_effect="Adjust cooling setpoint as requested.",
        confidence=1.0,
        source="tool_direct",
    )
    validated = validate_action(decision, state.cooling_setpoint, state.heating_setpoint)
    STORE.last_validated_action = validated
    return validated.model_dump()


def set_heating_setpoint(value: float) -> dict:
    """Propose a new heating setpoint, validated the same way as set_cooling_setpoint."""
    state = _require_state()
    decision = AgentDecision(
        action="change_heating_setpoint",
        cooling_setpoint=None,
        heating_setpoint=value,
        reason="Direct MCP tool call: set_heating_setpoint",
        expected_effect="Adjust heating setpoint as requested.",
        confidence=1.0,
        source="tool_direct",
    )
    validated = validate_action(decision, state.cooling_setpoint, state.heating_setpoint)
    STORE.last_validated_action = validated
    return validated.model_dump()


def apply_control_action(
    action: str,
    cooling_setpoint: Optional[float] = None,
    heating_setpoint: Optional[float] = None,
    reason: str = "",
    expected_effect: str = "",
    confidence: float = 0.5,
) -> dict:
    """
    Validate and record a full structured control decision in one call.
    This is the primary tool the agent uses each control step after
    reasoning about the current state and history.
    """
    state = _require_state()
    decision = AgentDecision(
        action=action,
        cooling_setpoint=cooling_setpoint,
        heating_setpoint=heating_setpoint,
        reason=reason or "No reason provided.",
        expected_effect=expected_effect or "Not specified.",
        confidence=confidence,
        source="llm",
    )
    validated = validate_action(decision, state.cooling_setpoint, state.heating_setpoint)
    STORE.last_validated_action = validated

    STORE.record_decision(
        {
            "timestamp": state.timestamp.isoformat(),
            "action": decision.action.value,
            "old_cooling_setpoint": state.cooling_setpoint,
            "new_cooling_setpoint": validated.cooling_setpoint,
            "old_heating_setpoint": state.heating_setpoint,
            "new_heating_setpoint": validated.heating_setpoint,
            "reason": decision.reason,
            "expected_effect": decision.expected_effect,
            "result": "clamped" if validated.was_clamped else "applied_as_proposed",
            "tool_used": "apply_control_action",
            "confidence": decision.confidence,
            "source": decision.source,
        }
    )
    logger.info(
        "apply_control_action: action=%s cooling=%.2f heating=%.2f clamped=%s",
        decision.action.value, validated.cooling_setpoint, validated.heating_setpoint,
        validated.was_clamped,
    )
    return validated.model_dump()
