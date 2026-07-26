"""
Unit tests for app.control.constraints.validate_action.

These tests do NOT require EnergyPlus, Ollama, or any network access -
the constraint validator is pure deterministic Python, which is exactly
why it is the safety-critical layer of the whole system.
"""
from __future__ import annotations

import pytest

from app.agent.schemas import AgentDecision, ActionType
from app.config import ConstraintsConfig
from app.control.constraints import validate_action


@pytest.fixture
def constraints() -> ConstraintsConfig:
    return ConstraintsConfig(
        cooling_setpoint_min=22.0,
        cooling_setpoint_max=28.0,
        heating_setpoint_min=18.0,
        heating_setpoint_max=22.0,
        min_deadband_c=1.5,
        max_setpoint_change_per_interval=1.0,
        pmv_min=-0.85,
        pmv_max=0.85,
        occupied_temp_min=20.0,
        occupied_temp_max=27.0,
    )


def _decision(action=ActionType.CHANGE_BOTH_SETPOINTS, cooling=None, heating=None) -> AgentDecision:
    return AgentDecision(
        action=action,
        cooling_setpoint=cooling,
        heating_setpoint=heating,
        reason="test",
        expected_effect="test",
        confidence=0.9,
        source="llm",
    )


def test_within_bounds_action_is_unchanged(constraints):
    decision = _decision(cooling=24.0, heating=21.0)
    result = validate_action(decision, current_cooling_setpoint=24.0, current_heating_setpoint=21.0, constraints=constraints)
    assert result.cooling_setpoint == 24.0
    assert result.heating_setpoint == 21.0
    assert result.was_clamped is False


def test_cooling_setpoint_clamped_to_max(constraints):
    decision = _decision(cooling=35.0, heating=21.0)
    result = validate_action(decision, current_cooling_setpoint=24.0, current_heating_setpoint=21.0, constraints=constraints)
    # Max rate-of-change (1.0C) applies before absolute clamp is even relevant here.
    assert result.cooling_setpoint <= constraints.cooling_setpoint_max
    assert result.was_clamped is True


def test_heating_setpoint_clamped_to_min(constraints):
    decision = _decision(cooling=24.0, heating=5.0)
    result = validate_action(decision, current_cooling_setpoint=24.0, current_heating_setpoint=21.0, constraints=constraints)
    assert result.heating_setpoint >= constraints.heating_setpoint_min
    assert result.was_clamped is True


def test_rate_of_change_limit_enforced(constraints):
    # Requesting a huge jump from 24 -> 27 in one step (limit is 1.0C/interval).
    decision = _decision(cooling=27.0, heating=21.0)
    result = validate_action(decision, current_cooling_setpoint=24.0, current_heating_setpoint=21.0, constraints=constraints)
    assert abs(result.cooling_setpoint - 24.0) <= constraints.max_setpoint_change_per_interval + 1e-6
    assert result.was_clamped is True


def test_minimum_deadband_enforced(constraints):
    # Propose setpoints that violate the deadband (cooling too close to heating).
    decision = _decision(cooling=22.2, heating=21.8)
    result = validate_action(decision, current_cooling_setpoint=22.5, current_heating_setpoint=21.0, constraints=constraints)
    assert (result.cooling_setpoint - result.heating_setpoint) >= constraints.min_deadband_c - 1e-6


def test_no_action_returns_current_setpoints_unchanged(constraints):
    # Values here are irrelevant for NO_ACTION but must stay within the
    # schema's own physical sanity bound (0-45C) to construct at all.
    decision = _decision(action=ActionType.NO_ACTION, cooling=40.0, heating=19.0)
    result = validate_action(decision, current_cooling_setpoint=24.0, current_heating_setpoint=21.0, constraints=constraints)
    assert result.cooling_setpoint == 24.0
    assert result.heating_setpoint == 21.0
    assert result.was_clamped is False


def test_nan_setpoint_raises(constraints):
    # The Pydantic schema itself already rejects NaN/out-of-range values at
    # construction time (defense in depth); to exercise validate_action's
    # OWN NaN guard directly we bypass schema validation with model_construct,
    # simulating an already-in-memory decision object with a corrupted value.
    decision = AgentDecision.model_construct(
        action=ActionType.CHANGE_BOTH_SETPOINTS,
        cooling_setpoint=float("nan"),
        heating_setpoint=21.0,
        reason="test",
        expected_effect="test",
        confidence=0.9,
        source="llm",
    )
    with pytest.raises(ValueError):
        validate_action(decision, current_cooling_setpoint=24.0, current_heating_setpoint=21.0, constraints=constraints)


def test_missing_cooling_falls_back_to_current(constraints):
    decision = _decision(cooling=None, heating=20.0)
    result = validate_action(decision, current_cooling_setpoint=24.0, current_heating_setpoint=21.0, constraints=constraints)
    # Cooling wasn't proposed, so it should stay near the current value (subject to rate limit only).
    assert abs(result.cooling_setpoint - 24.0) < 1e-6
