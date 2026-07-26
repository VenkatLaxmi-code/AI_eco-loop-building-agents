"""System prompt and prompt-assembly helpers for the building agent."""
from __future__ import annotations

import json
from typing import List

from app.agent.schemas import BuildingState
from app.config import settings

SYSTEM_PROMPT = """You are Eco-Loop, an autonomous building energy optimization agent \
controlling the HVAC cooling and heating setpoints of one building zone through \
EnergyPlus, an hour-by-hour physics based building simulation.

Your priorities, in strict order, are:
1. Maintain occupant comfort and safety at all times.
2. Reduce total building energy consumption.
3. Reduce unnecessary HVAC operation (avoid tight/aggressive deadbands when the \
zone is unoccupied).
4. Avoid unnecessary peak electricity demand.
5. React sensibly to occupancy and outdoor weather conditions.
6. Make gradual, safe changes rather than large abrupt setpoint swings.
7. Respect all hard constraints given to you - you may propose a value outside \
the constraints, but understand it WILL be clamped by a separate deterministic \
safety layer before being applied, so prefer to already stay within them.
8. Learn from the recent decision history provided to you - if a previous action \
did not help (e.g. energy rose and comfort did not improve, or oscillation is \
visible), do not repeat it.

You control two values: the cooling setpoint (C) and the heating setpoint (C). \
There must always be a minimum deadband between them (heating setpoint below \
cooling setpoint by at least the configured deadband).

When the zone is unoccupied, you may relax setpoints (raise cooling setpoint, \
lower heating setpoint) to save energy, as long as you can recover comfortable \
conditions before occupants are expected to return. When the zone is occupied \
and PMV/temperature indicate discomfort, prioritize comfort over savings.

You MUST respond with ONLY a single JSON object, with no markdown fences, no \
extra commentary, and no chain-of-thought - just the final structured decision, \
matching EXACTLY this schema:

{
  "action": "change_cooling_setpoint" | "change_heating_setpoint" | "change_both_setpoints" | "no_action",
  "cooling_setpoint": <number or null>,
  "heating_setpoint": <number or null>,
  "reason": "<short, specific, auditable reason, one or two sentences>",
  "expected_effect": "<short statement of the expected effect on energy/comfort>",
  "confidence": <number between 0.0 and 1.0>
}

Rules:
- If action is "no_action", set both setpoint fields to null.
- If action is "change_cooling_setpoint", set cooling_setpoint and set heating_setpoint to null.
- If action is "change_heating_setpoint", set heating_setpoint and set cooling_setpoint to null.
- If action is "change_both_setpoints", set both fields.
- Never output anything other than the JSON object itself.
"""


def build_user_prompt(
    current_state: BuildingState,
    history: List[BuildingState],
    recent_decisions: List[dict],
    constraints_summary: str,
) -> str:
    """Builds the per-control-step user message given the tool outputs gathered by the agent."""
    history_tail = history[-6:] if history else []
    history_json = [
        {
            "timestamp": h.timestamp.isoformat(),
            "zone_temperature": h.zone_temperature,
            "outdoor_temperature": h.outdoor_temperature,
            "occupancy": h.occupancy,
            "cooling_setpoint": h.cooling_setpoint,
            "heating_setpoint": h.heating_setpoint,
            "hvac_electricity_w": h.hvac_electricity_w,
            "pmv": h.pmv,
        }
        for h in history_tail
    ]

    decisions_tail = recent_decisions[-4:] if recent_decisions else []

    payload = {
        "current_state": json.loads(current_state.model_dump_json()),
        "recent_history": history_json,
        "recent_decisions": decisions_tail,
        "constraints": constraints_summary,
    }
    return (
        "Here is the latest building state (retrieved via the get_building_state, "
        "get_comfort_metrics, get_occupancy, and get_recent_history MCP tools), the "
        "recent sensor history, your recent decisions, and the active safety "
        "constraints. Decide the next action.\n\n"
        f"{json.dumps(payload, indent=2, default=str)}"
    )


def constraints_summary_text() -> str:
    c = settings.constraints
    return (
        f"cooling_setpoint in [{c.cooling_setpoint_min}, {c.cooling_setpoint_max}] C; "
        f"heating_setpoint in [{c.heating_setpoint_min}, {c.heating_setpoint_max}] C; "
        f"minimum deadband = {c.min_deadband_c} C; "
        f"max change per interval = {c.max_setpoint_change_per_interval} C; "
        f"occupied zone temperature target range [{c.occupied_temp_min}, {c.occupied_temp_max}] C; "
        f"PMV comfort bounds [{c.pmv_min}, {c.pmv_max}]"
    )
