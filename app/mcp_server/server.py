"""
Eco-Loop MCP server.

Exposes the building's live simulation state and control tools over the
Model Context Protocol (stdio transport by default), using the official
`mcp` Python SDK's FastMCP high-level API.

Run standalone (e.g. to inspect with the MCP Inspector, or connect from
Claude Desktop / another MCP client) with:

    python -m app.mcp_server.server

The same process is also spawned as a subprocess by BuildingAgent
(app/agent/building_agent.py) so the autonomous control loop talks to
this server over the real MCP protocol rather than calling Python
functions directly across process boundaries.
"""
from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from app.mcp_server import tools as t

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp.server")

mcp = FastMCP("eco-loop-building-agents")


@mcp.tool()
def push_building_state(state: dict) -> dict:
    """Ingest the latest normalized EnergyPlus building state (internal/bridge tool)."""
    return t.push_building_state(state)


@mcp.tool()
def get_building_state() -> dict:
    """Get the full current building state: temperatures, occupancy, setpoints, energy, comfort."""
    return t.get_building_state()


@mcp.tool()
def get_zone_temperature() -> dict:
    """Get the current zone and outdoor air temperatures (Celsius)."""
    return t.get_zone_temperature()


@mcp.tool()
def get_energy_consumption() -> dict:
    """Get current HVAC and total facility electric power demand (Watts)."""
    return t.get_energy_consumption()


@mcp.tool()
def get_comfort_metrics() -> dict:
    """Get thermal comfort indicators: PMV, humidity, and whether temperature/PMV are within bounds."""
    return t.get_comfort_metrics()


@mcp.tool()
def get_occupancy() -> dict:
    """Get the current occupant count and occupied/unoccupied flag for the zone."""
    return t.get_occupancy()


@mcp.tool()
def get_current_setpoints() -> dict:
    """Get the cooling and heating setpoints currently active in the simulation."""
    return t.get_current_setpoints()


@mcp.tool()
def get_simulation_errors() -> dict:
    """Get any EnergyPlus or tool errors recorded so far during this run."""
    return t.get_simulation_errors()


@mcp.tool()
def get_recent_history(limit: int = 8) -> dict:
    """Get the last `limit` building states, most recent last (default 8, max 50)."""
    return t.get_recent_history(limit)


@mcp.tool()
def set_cooling_setpoint(value: float) -> dict:
    """Propose a new cooling setpoint (C); it will be validated/clamped against safety constraints."""
    return t.set_cooling_setpoint(value)


@mcp.tool()
def set_heating_setpoint(value: float) -> dict:
    """Propose a new heating setpoint (C); it will be validated/clamped against safety constraints."""
    return t.set_heating_setpoint(value)


@mcp.tool()
def apply_control_action(
    action: str,
    cooling_setpoint: float | None = None,
    heating_setpoint: float | None = None,
    reason: str = "",
    expected_effect: str = "",
    confidence: float = 0.5,
) -> dict:
    """
    Apply a full structured control decision (action, setpoints, reason,
    expected_effect, confidence). Validated/clamped before being recorded.
    `action` must be one of: change_cooling_setpoint, change_heating_setpoint,
    change_both_setpoints, no_action.
    """
    return t.apply_control_action(
        action=action,
        cooling_setpoint=cooling_setpoint,
        heating_setpoint=heating_setpoint,
        reason=reason,
        expected_effect=expected_effect,
        confidence=confidence,
    )


if __name__ == "__main__":
    logger.info("Starting Eco-Loop MCP server (stdio transport)...")
    mcp.run()
