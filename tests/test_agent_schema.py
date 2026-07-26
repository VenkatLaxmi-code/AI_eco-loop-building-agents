"""
Unit tests for the Pydantic schemas that constrain every LLM response
(app.agent.schemas). These guarantee malformed LLM output is rejected
before it can ever reach the constraint validator or EnergyPlus.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.agent.schemas import AgentDecision, ActionType, BuildingState


def test_valid_agent_decision_parses():
    decision = AgentDecision(
        action="change_cooling_setpoint",
        cooling_setpoint=24.0,
        heating_setpoint=None,
        reason="Low occupancy allows relaxed cooling.",
        expected_effect="Reduced HVAC electricity draw.",
        confidence=0.86,
    )
    assert decision.action == ActionType.CHANGE_COOLING_SETPOINT
    assert decision.source == "llm"


def test_invalid_action_enum_rejected():
    with pytest.raises(ValidationError):
        AgentDecision(
            action="turn_off_building_forever",  # not a valid ActionType
            cooling_setpoint=24.0,
            reason="test",
            expected_effect="test",
            confidence=0.5,
        )


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError):
        AgentDecision(
            action="no_action",
            reason="test",
            expected_effect="test",
            confidence=1.5,  # must be <= 1.0
        )


def test_unreasonable_setpoint_rejected():
    with pytest.raises(ValidationError):
        AgentDecision(
            action="change_cooling_setpoint",
            cooling_setpoint=120.0,  # physically absurd
            reason="test",
            expected_effect="test",
            confidence=0.5,
        )


def test_reason_too_short_rejected():
    with pytest.raises(ValidationError):
        AgentDecision(
            action="no_action",
            reason="ok",  # below min_length=3... actually 2 chars, should fail
            expected_effect="fine explanation here",
            confidence=0.5,
        )


def test_building_state_requires_non_negative_occupancy():
    with pytest.raises(ValidationError):
        BuildingState(
            timestamp=datetime.utcnow(),
            zone_name="MAIN_ZONE",
            zone_temperature=24.0,
            outdoor_temperature=30.0,
            occupancy=-1,
            cooling_setpoint=24.0,
            heating_setpoint=21.0,
            hvac_electricity_w=100.0,
            total_electricity_w=500.0,
            simulation_day=1,
            simulation_hour=10,
        )


def test_building_state_is_occupied_helper():
    state = BuildingState(
        timestamp=datetime.utcnow(),
        zone_name="MAIN_ZONE",
        zone_temperature=24.0,
        outdoor_temperature=30.0,
        occupancy=3,
        cooling_setpoint=24.0,
        heating_setpoint=21.0,
        hvac_electricity_w=100.0,
        total_electricity_w=500.0,
        simulation_day=1,
        simulation_hour=10,
    )
    assert state.is_occupied() is True

    empty_state = state.model_copy(update={"occupancy": 0})
    assert empty_state.is_occupied() is False
