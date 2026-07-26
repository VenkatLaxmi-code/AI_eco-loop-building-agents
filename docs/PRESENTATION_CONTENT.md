# Presentation Content — Eco-Loop Building Agents

Copy/paste-ready content for hackathon slides. One section per slide.

---

## Slide 1 — Problem

- Buildings consume a large share of global energy.
- Traditional BMS: fixed schedules, static rules.
- Cannot adapt continuously to weather, occupancy, or demand changes.
- Result: wasted energy, or comfort sacrificed for savings (and often both).

---

## Slide 2 — Proposed Solution

**Eco-Loop Building Agents**: an autonomous, closed-loop AI system that
continuously optimizes HVAC setpoints in a live EnergyPlus simulation,
using an open-source LLM agent reasoning through real MCP tool calls —
with zero human intervention during operation.

---

## Slide 3 — Architecture

```
EnergyPlus → Sensor Layer → MCP Tools → LLM Agent →
Constraint Validator → Actuator Layer → EnergyPlus (repeat)
```

- Physics-based simulation (EnergyPlus), not a toy model.
- Every arrow above is a real, working code path — no shortcuts.

---

## Slide 4 — Technology Stack

- **Simulation**: EnergyPlus + official EnergyPlus Python API (`pyenergyplus`)
- **Building modeling**: `eppy` for programmatic IDF edits
- **Agent protocol**: Model Context Protocol (official `mcp` Python SDK, `FastMCP`)
- **LLM**: Open-source, self-hosted (Ollama by default — Qwen2.5 / Llama 3.1 / Mistral)
- **Validation**: Pydantic v2 schemas end-to-end
- **Dashboard**: Streamlit + Plotly
- **Language**: Python 3.11, fully typed, tested with pytest

---

## Slide 5 — Closed-Loop Workflow

1. Read EnergyPlus state (every zone timestep)
2. Collect sensor/performance metrics
3. Provide state + history to the agent
4. Agent evaluates comfort, occupancy, energy, demand
5. Agent selects an action (structured JSON)
6. Deterministic validator clamps to safe bounds
7. Apply setpoints to EnergyPlus via EMS actuators
8. Advance simulation, repeat automatically

---

## Slide 6 — MCP + LLM Agent

- 11 real MCP tools: `get_building_state`, `get_comfort_metrics`,
  `get_energy_consumption`, `get_occupancy`, `get_current_setpoints`,
  `get_recent_history`, `get_simulation_errors`,
  `set_cooling_setpoint`, `set_heating_setpoint`, `apply_control_action`,
  `push_building_state`.
- Runs as a genuine stdio subprocess — a persistent `ClientSession`, not
  a single giant prompt.
- LLM output validated against a Pydantic `AgentDecision` schema;
  malformed responses trigger a retry, then a deterministic fallback.

---

## Slide 7 — EnergyPlus Integration

- Official EnergyPlus Python API — live callbacks, not post-hoc log parsing.
- EMS actuators override two setpoint schedules at runtime.
- Same IDF drives both baseline and AI experiments; only the control
  strategy differs.
- `RunPeriod` configured per-run from `.env` via `eppy`.

---

## Slide 8 — Safety & Comfort Constraints

- Absolute setpoint bounds (min/max, configurable).
- Maximum setpoint change per control interval (rate limiting).
- Minimum heating/cooling deadband.
- PMV and occupied-zone temperature comfort bounds.
- **The LLM can never bypass this deterministic layer.**

---

## Slide 9 — Dashboard

- Overview cards: baseline/AI energy, savings %, peak demand reduction,
  average temperature, comfort compliance.
- Timeseries charts: energy, temperature, setpoints, PMV, occupancy,
  AI actions.
- Full agent decision log: timestamp, state, action, reason, expected
  effect, result, tool used.

---

## Slide 10 — Results

> Populate this slide from your own `data/metrics.json` after running
> `python scripts/run_demo.py` — real savings %, peak-demand reduction,
> and comfort compliance from your actual run.

---

## Slide 11 — Innovation

- Genuine multi-layer agentic system: real MCP protocol + real
  EnergyPlus Python API + real open-source LLM tool calling — not a
  simulated demo of any of the three.
- Deterministic safety layer that fully decouples "what the AI wants"
  from "what actually reaches the building."
- Self-correcting: handles LLM downtime, malformed output, and
  oscillating decisions without crashing or requiring a human.

---

## Slide 12 — Future Scope

- Multi-zone / multi-system buildings.
- Demand-response and time-of-use pricing awareness.
- Reinforcement learning on top of the logged decision history.
- Real building deployment via BACnet/Modbus instead of EnergyPlus actuators.
