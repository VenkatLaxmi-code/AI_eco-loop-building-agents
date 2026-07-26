"""
Deterministic fallback controller.

Used whenever the LLM cannot be reached, returns malformed output that
fails schema validation after retries, or a repeated-oscillation guard
trips. Implements a simple, safe, occupancy-aware rule so the closed
loop NEVER stalls or crashes just because one model response was bad.
"""
from __future__ import annotations

from typing import List

from app.agent.schemas import AgentDecision, ActionType, BuildingState
from app.config import settings


def fallback_decision(current_state: BuildingState, history: List[BuildingState]) -> AgentDecision:
    c = settings.constraints

    if current_state.is_occupied():
        cooling = 24.0
        heating = 21.0
        reason = "Fallback controller: zone occupied, applying safe comfort-first defaults."
    else:
        # Unoccupied - relax setpoints toward the edges of the allowed range to save energy.
        cooling = min(c.cooling_setpoint_max, 26.5)
        heating = max(c.heating_setpoint_min, 19.0)
        reason = "Fallback controller: zone unoccupied, relaxing setpoints to save energy."

    # Respect deadband defensively even in the fallback path.
    if cooling - heating < c.min_deadband_c:
        heating = cooling - c.min_deadband_c

    return AgentDecision(
        action=ActionType.CHANGE_BOTH_SETPOINTS,
        cooling_setpoint=round(cooling, 2),
        heating_setpoint=round(heating, 2),
        reason=reason,
        expected_effect="Maintain safe, comfortable, moderately efficient operation until the LLM is available again.",
        confidence=0.5,
        source="fallback",
    )


def detect_oscillation(recent_decisions: List[dict], window: int = 4) -> bool:
    """
    Detects a simple back-and-forth oscillation pattern (e.g. setpoint
    repeatedly alternating up/down every step) in the most recent
    decisions, which usually indicates the agent is thrashing rather
    than converging.
    """
    if len(recent_decisions) < window:
        return False
    tail = recent_decisions[-window:]
    coolings = [d.get("new_cooling_setpoint") for d in tail if d.get("new_cooling_setpoint") is not None]
    if len(coolings) < window:
        return False
    diffs = [coolings[i + 1] - coolings[i] for i in range(len(coolings) - 1)]
    signs = [1 if d > 0.05 else (-1 if d < -0.05 else 0) for d in diffs]
    if len(signs) >= 3 and all(s != 0 for s in signs):
        alternating = all(signs[i] != signs[i + 1] for i in range(len(signs) - 1))
        if alternating:
            return True
    return False
