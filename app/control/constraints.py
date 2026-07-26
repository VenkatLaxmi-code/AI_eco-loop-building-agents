"""
Deterministic safety/comfort constraint validator.

This is the ONLY code path allowed to write a setpoint into EnergyPlus.
Every action proposed by the LLM agent (or the fallback controller)
passes through `validate_action` before it can reach the actuator
layer. The LLM cannot bypass this layer under any circumstances.
"""
from __future__ import annotations

from typing import Optional

from app.agent.schemas import AgentDecision, ValidatedAction
from app.config import ConstraintsConfig, settings


def validate_action(
    decision: AgentDecision,
    current_cooling_setpoint: float,
    current_heating_setpoint: float,
    constraints: Optional[ConstraintsConfig] = None,
) -> ValidatedAction:
    """
    Clamp the proposed decision into safe, physically and contractually
    valid bounds. Always returns a ValidatedAction - never raises for a
    merely out-of-range proposal (it clamps instead), but DOES raise
    ValueError for structurally impossible input (e.g. NaN).
    """
    c = constraints or settings.constraints
    reasons: list[str] = []

    proposed_cooling = decision.cooling_setpoint
    proposed_heating = decision.heating_setpoint

    if decision.action.value == "no_action":
        return ValidatedAction(
            cooling_setpoint=current_cooling_setpoint,
            heating_setpoint=current_heating_setpoint,
            was_clamped=False,
            clamp_reasons=[],
            source=decision.source,
        )

    new_cooling = proposed_cooling if proposed_cooling is not None else current_cooling_setpoint
    new_heating = proposed_heating if proposed_heating is not None else current_heating_setpoint

    for value in (new_cooling, new_heating):
        if value != value:  # NaN check
            raise ValueError("Proposed setpoint is NaN.")

    # 1) Absolute min/max bounds
    clamped_cooling = min(max(new_cooling, c.cooling_setpoint_min), c.cooling_setpoint_max)
    if clamped_cooling != new_cooling:
        reasons.append(
            f"cooling_setpoint {new_cooling} clamped to allowed range "
            f"[{c.cooling_setpoint_min}, {c.cooling_setpoint_max}]"
        )

    clamped_heating = min(max(new_heating, c.heating_setpoint_min), c.heating_setpoint_max)
    if clamped_heating != new_heating:
        reasons.append(
            f"heating_setpoint {new_heating} clamped to allowed range "
            f"[{c.heating_setpoint_min}, {c.heating_setpoint_max}]"
        )

    # 2) Maximum rate of change per control interval
    max_delta = c.max_setpoint_change_per_interval
    cooling_delta = clamped_cooling - current_cooling_setpoint
    if abs(cooling_delta) > max_delta:
        clamped_cooling = current_cooling_setpoint + max_delta * (1 if cooling_delta > 0 else -1)
        reasons.append(
            f"cooling_setpoint change limited to {max_delta} C per interval"
        )

    heating_delta = clamped_heating - current_heating_setpoint
    if abs(heating_delta) > max_delta:
        clamped_heating = current_heating_setpoint + max_delta * (1 if heating_delta > 0 else -1)
        reasons.append(
            f"heating_setpoint change limited to {max_delta} C per interval"
        )

    # 3) Minimum deadband between heating and cooling setpoints
    if clamped_cooling - clamped_heating < c.min_deadband_c:
        midpoint = (clamped_cooling + clamped_heating) / 2.0
        clamped_cooling = midpoint + c.min_deadband_c / 2.0
        clamped_heating = midpoint - c.min_deadband_c / 2.0
        # Re-clip to absolute bounds after deadband correction.
        clamped_cooling = min(max(clamped_cooling, c.cooling_setpoint_min), c.cooling_setpoint_max)
        clamped_heating = min(max(clamped_heating, c.heating_setpoint_min), c.heating_setpoint_max)
        reasons.append(f"enforced minimum deadband of {c.min_deadband_c} C between setpoints")

    return ValidatedAction(
        cooling_setpoint=round(clamped_cooling, 2),
        heating_setpoint=round(clamped_heating, 2),
        was_clamped=len(reasons) > 0,
        clamp_reasons=reasons,
        source=decision.source,
    )
