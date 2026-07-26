"""
BuildingAgent: the autonomous reasoning agent.

Responsibilities per control step:
  1. Push the latest EnergyPlus-derived BuildingState into the MCP server
     (push_building_state).
  2. Gather context by calling MCP tools (get_building_state,
     get_comfort_metrics, get_energy_consumption, get_occupancy,
     get_current_setpoints, get_recent_history, get_simulation_errors).
  3. Ask the open-source LLM to reason over that context and return a
     structured decision.
  4. Validate the LLM's JSON against the AgentDecision schema; on
     failure, retry once with an error hint, then fall back to the
     deterministic fallback controller.
  5. Submit the final decision through the apply_control_action MCP
     tool, which runs it through the deterministic constraint validator.
  6. Return a ValidatedAction to the closed-loop controller, which is
     the only thing ever written into EnergyPlus.

The MCP server runs as a real subprocess (app/mcp_server/server.py)
communicating over stdio using the official MCP Python SDK - every tool
call below is a genuine MCP request/response, not a direct function call.
A persistent background asyncio event loop keeps one long-lived
ClientSession open for the whole simulation run so each control step is
fast, while still calling `_on_zone_timestep` synchronously as EnergyPlus
requires.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
from pathlib import Path
from typing import List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.agent.fallback_controller import detect_oscillation, fallback_decision
from app.agent.llm_client import LLMClient, LLMConnectionError, LLMResponseError
from app.agent.prompts import SYSTEM_PROMPT, build_user_prompt, constraints_summary_text
from app.agent.schemas import AgentDecision, BuildingState, ValidatedAction
from app.config import settings

logger = logging.getLogger("building_agent")


class BuildingAgent:
    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm = llm_client or LLMClient()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._session: Optional[ClientSession] = None
        self._session_cm = None
        self._stdio_cm = None
        self._ready = threading.Event()
        self.decisions_log: List[dict] = []

    # ------------------------------------------------------------------
    # Lifecycle: start/stop the background event loop + MCP subprocess
    # ------------------------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=30):
            raise RuntimeError("Timed out starting the Eco-Loop MCP server subprocess.")
        logger.info("BuildingAgent MCP session ready.")

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_init())
        self._loop.run_forever()

    async def _async_init(self) -> None:
        project_root = settings.paths.project_root
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server.server"],
            cwd=str(project_root),
        )
        self._stdio_cm = stdio_client(server_params)
        read_stream, write_stream = await self._stdio_cm.__aenter__()
        self._session_cm = ClientSession(read_stream, write_stream)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()
        self._ready.set()

    def stop(self) -> None:
        if self._loop is None:
            return

        async def _shutdown():
            if self._session_cm is not None:
                await self._session_cm.__aexit__(None, None, None)
            if self._stdio_cm is not None:
                await self._stdio_cm.__aexit__(None, None, None)

        fut = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
        try:
            fut.result(timeout=10)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error during MCP session shutdown: %s", exc)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    # ------------------------------------------------------------------
    # Tool-call helpers (run coroutines on the background loop, block for result)
    # ------------------------------------------------------------------
    def _call_tool(self, name: str, arguments: dict) -> dict:
        async def _call():
            result = await self._session.call_tool(name, arguments)
            if result.isError:
                text = result.content[0].text if result.content else "unknown MCP tool error"
                raise RuntimeError(f"MCP tool '{name}' returned an error: {text}")
            text_blocks = [c.text for c in result.content if hasattr(c, "text")]
            payload = text_blocks[0] if text_blocks else "{}"
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return {"raw": payload}

        fut = asyncio.run_coroutine_threadsafe(_call(), self._loop)
        return fut.result(timeout=30)

    # ------------------------------------------------------------------
    # Main per-control-step entry point (called synchronously by EnergyPlusRunner)
    # ------------------------------------------------------------------
    def decide(
        self,
        current_state: BuildingState,
        history: List[BuildingState],
        recent_decisions: List[dict],
    ) -> ValidatedAction:
        # 1) Push latest state into the MCP server's shared store.
        self._call_tool("push_building_state", {"state": json.loads(current_state.model_dump_json())})

        # 2) Gather context via MCP tools (demonstrates real tool-calling, not one giant prompt).
        comfort = self._call_tool("get_comfort_metrics", {})
        energy = self._call_tool("get_energy_consumption", {})
        occupancy = self._call_tool("get_occupancy", {})
        setpoints = self._call_tool("get_current_setpoints", {})
        history_payload = self._call_tool("get_recent_history", {"limit": 8})
        errors = self._call_tool("get_simulation_errors", {})

        logger.debug(
            "Context gathered via MCP tools: comfort=%s energy=%s occupancy=%s setpoints=%s errors=%d",
            comfort, energy, occupancy, setpoints, errors.get("count", 0),
        )

        # 3) Oscillation guard - if the last few decisions are thrashing, skip the LLM this step.
        if detect_oscillation(recent_decisions):
            logger.warning("Oscillation detected in recent decisions; using fallback controller.")
            decision = fallback_decision(current_state, history)
            return self._apply(decision, current_state)

        # 4) Ask the LLM for a decision, with one retry on malformed output.
        decision = self._get_llm_decision(current_state, history, recent_decisions)
        return self._apply(decision, current_state)

    def _get_llm_decision(
        self,
        current_state: BuildingState,
        history: List[BuildingState],
        recent_decisions: List[dict],
        _attempt: int = 1,
    ) -> AgentDecision:
        user_prompt = build_user_prompt(
            current_state, history, recent_decisions, constraints_summary_text()
        )
        try:
            raw = self.llm.generate_decision_json(SYSTEM_PROMPT, user_prompt)
            raw.setdefault("source", "llm")
            decision = AgentDecision.model_validate(raw)
            return decision
        except (LLMConnectionError,) as exc:
            logger.error("LLM unreachable (%s). Using fallback controller.", exc)
            return fallback_decision(current_state, history)
        except (LLMResponseError, ValueError) as exc:
            if _attempt < 2:
                logger.warning(
                    "LLM response failed validation (%s). Retrying once with error hint.", exc
                )
                hint = (
                    user_prompt
                    + f"\n\nNOTE: Your previous response was invalid: {exc}. "
                    "Respond again with ONLY the corrected JSON object."
                )
                try:
                    raw = self.llm.generate_decision_json(SYSTEM_PROMPT, hint)
                    raw.setdefault("source", "llm")
                    return AgentDecision.model_validate(raw)
                except Exception as retry_exc:  # noqa: BLE001
                    logger.error(
                        "LLM retry also failed (%s). Using fallback controller.", retry_exc
                    )
                    return fallback_decision(current_state, history)
            logger.error("LLM response invalid after retry (%s). Using fallback controller.", exc)
            return fallback_decision(current_state, history)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error calling LLM: %s", exc)
            return fallback_decision(current_state, history)

    def _apply(self, decision: AgentDecision, current_state: BuildingState) -> ValidatedAction:
        result = self._call_tool(
            "apply_control_action",
            {
                "action": decision.action.value,
                "cooling_setpoint": decision.cooling_setpoint,
                "heating_setpoint": decision.heating_setpoint,
                "reason": decision.reason,
                "expected_effect": decision.expected_effect,
                "confidence": decision.confidence,
            },
        )
        validated = ValidatedAction.model_validate(result)
        self.decisions_log.append(
            {
                "timestamp": current_state.timestamp.isoformat(),
                "action": decision.action.value,
                "old_cooling_setpoint": current_state.cooling_setpoint,
                "new_cooling_setpoint": validated.cooling_setpoint,
                "old_heating_setpoint": current_state.heating_setpoint,
                "new_heating_setpoint": validated.heating_setpoint,
                "reason": decision.reason,
                "expected_effect": decision.expected_effect,
                "result": "clamped" if validated.was_clamped else "applied_as_proposed",
                "tool_used": "apply_control_action",
                "confidence": decision.confidence,
                "source": decision.source,
            }
        )
        return validated
