"""
Unit tests for app.mcp_server.tools.

These call the underlying tool functions directly (the same functions
the FastMCP server in app.mcp_server.server exposes over the wire) so
the tests run instantly with no MCP transport, EnergyPlus, or LLM
required, while still exercising the exact logic the agent depends on.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.agent.schemas import BuildingState
from app.mcp_server import tools as t


@pytest.fixture(autouse=True)
def reset_store():
    """Each test gets a clean, isolated store."""
    t.STORE.current_state = None
    t.STORE.history = []
    t.STORE.decisions = []
    t.STORE.errors = []
    yield


def _make_state(**overrides) -> dict:
    base = dict(
        timestamp=datetime(2024, 7, 1, 14, 0, 0),
        zone_name="MAIN_ZONE",
        zone_temperature=25.0,
        outdoor_temperature=33.0,
        occupancy=6,
        cooling_setpoint=24.0,
        heating_setpoint=21.0,
        hvac_electricity_w=1200.0,
        total_electricity_w=3400.0,
        cooling_load_w=900.0,
        heating_load_w=0.0,
        pmv=0.4,
        humidity_percent=48.0,
        simulation_day=1,
        simulation_hour=14,
    )
    base.update(overrides)
    return base


def test_tools_raise_before_any_state_pushed():
    with pytest.raises(RuntimeError):
        t.get_building_state()


def test_push_and_get_building_state_round_trip():
    t.push_building_state(_make_state())
    state = t.get_building_state()
    assert state["zone_temperature"] == 25.0
    assert state["occupancy"] == 6


def test_get_zone_temperature():
    t.push_building_state(_make_state(zone_temperature=23.5, outdoor_temperature=31.0))
    result = t.get_zone_temperature()
    assert result == {"zone_temperature": 23.5, "outdoor_temperature": 31.0}


def test_get_energy_consumption():
    t.push_building_state(_make_state())
    result = t.get_energy_consumption()
    assert result["hvac_electricity_w"] == 1200.0
    assert result["total_electricity_w"] == 3400.0


def test_get_occupancy():
    t.push_building_state(_make_state(occupancy=0))
    result = t.get_occupancy()
    assert result["occupancy"] == 0
    assert result["is_occupied"] is False


def test_set_cooling_setpoint_clamps_unsafe_value():
    t.push_building_state(_make_state(cooling_setpoint=24.0, heating_setpoint=21.0))
    # 40C is physically plausible (passes the schema's 0-45C sanity bound)
    # but is well above the configured cooling_setpoint_max, so the
    # deterministic constraint layer must clamp it.
    result = t.set_cooling_setpoint(40.0)
    assert result["cooling_setpoint"] < 40.0
    assert result["was_clamped"] is True


def test_apply_control_action_records_decision_log_entry():
    t.push_building_state(_make_state(cooling_setpoint=24.0, heating_setpoint=21.0))
    t.apply_control_action(
        action="change_cooling_setpoint",
        cooling_setpoint=25.0,
        reason="Low occupancy permits relaxed cooling.",
        expected_effect="Lower HVAC energy use.",
        confidence=0.8,
    )
    assert len(t.STORE.decisions) == 1
    entry = t.STORE.decisions[0]
    assert entry["action"] == "change_cooling_setpoint"
    assert entry["tool_used"] == "apply_control_action"


def test_get_recent_history_respects_limit():
    for i in range(10):
        t.push_building_state(_make_state(simulation_hour=i % 24))
    result = t.get_recent_history(limit=3)
    assert len(result["history"]) == 3


def test_get_simulation_errors_empty_by_default():
    result = t.get_simulation_errors()
    assert result["count"] == 0
    assert result["errors"] == []
