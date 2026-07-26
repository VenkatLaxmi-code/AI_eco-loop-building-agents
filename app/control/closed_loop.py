"""
Autonomous closed-loop controller.

Wires together:
    EnergyPlusRunner (simulation + sensors + actuators)
        <-> BuildingAgent (MCP tools + LLM reasoning)
        <-> constraint validation (inside the MCP tools, defense-in-depth)

and produces the CSV/JSON artifacts consumed by the dashboard and by
scripts/compare_results.py.
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import List, Optional

from app.agent.building_agent import BuildingAgent
from app.agent.schemas import BuildingState, ValidatedAction
from app.config import settings
from app.simulation.energyplus_runner import EnergyPlusRunner, RunResult

logger = logging.getLogger("closed_loop")


def run_baseline_experiment() -> RunResult:
    """
    Runs EnergyPlus with its native fixed schedules (no AI intervention).
    This represents a conventional, rule-based Building Management System.
    """
    output_dir = settings.paths.data_dir / "baseline_run"
    runner = EnergyPlusRunner(
        idf_path=settings.energyplus.baseline_idf,
        epw_path=settings.energyplus.weather_file,
        output_dir=str(output_dir),
        zone_name=settings.energyplus.zone_name,
        control_interval_minutes=settings.control.control_interval_minutes,
        mode="baseline",
        decision_callback=None,
    )
    result = runner.run()
    _write_states_csv(result.states, settings.paths.data_dir / "baseline_results.csv")
    return result


def run_ai_experiment() -> RunResult:
    """
    Runs EnergyPlus with the autonomous LLM agent in the loop, closing
    the loop every CONTROL_INTERVAL_MINUTES of simulated time.
    """
    agent = BuildingAgent()
    agent.start()
    try:
        def decision_callback(
            current_state: BuildingState,
            history: List[BuildingState],
            recent_decisions: List[dict],
        ) -> ValidatedAction:
            return agent.decide(current_state, history, recent_decisions)

        output_dir = settings.paths.data_dir / "ai_run"
        runner = EnergyPlusRunner(
            idf_path=settings.energyplus.ai_idf,
            epw_path=settings.energyplus.weather_file,
            output_dir=str(output_dir),
            zone_name=settings.energyplus.zone_name,
            control_interval_minutes=settings.control.control_interval_minutes,
            mode="ai",
            decision_callback=decision_callback,
        )
        result = runner.run()
        result.decisions = agent.decisions_log
        _write_states_csv(result.states, settings.paths.data_dir / "ai_results.csv")
        _write_decisions_csv(result.decisions, settings.paths.data_dir / "agent_decisions.csv")
        return result
    finally:
        agent.stop()


# --------------------------------------------------------------------
# CSV / JSON export helpers
# --------------------------------------------------------------------
def _write_states_csv(states: List[BuildingState], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not states:
        logger.warning("No states captured; writing empty file with header only: %s", path)
    fieldnames = list(BuildingState.model_fields.keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in states:
            row = json.loads(s.model_dump_json())
            writer.writerow(row)
    logger.info("Wrote %d rows to %s", len(states), path)


def _write_decisions_csv(decisions: List[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp", "action", "old_cooling_setpoint", "new_cooling_setpoint",
        "old_heating_setpoint", "new_heating_setpoint", "reason", "expected_effect",
        "result", "tool_used", "confidence", "source",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in decisions:
            writer.writerow({k: d.get(k, "") for k in fieldnames})
    logger.info("Wrote %d decision rows to %s", len(decisions), path)
