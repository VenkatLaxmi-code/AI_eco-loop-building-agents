# 3-Minute Demo Script — Eco-Loop Building Agents

Total runtime target: **≤ 3:00**. Have a terminal (for the live console
run) and a browser tab (for the dashboard) ready before you start the
timer. Run `python scripts/run_demo.py` a first time BEFORE the actual
demo so results already exist, then re-run a short live segment (or use
`--quick`/short `SIMULATION_DAYS=1`) during the timed window so the
audience sees fresh, real output.

## 0:00 – 0:20 — Problem + Solution

> "Buildings run on fixed schedules that can't adapt to real occupancy or
> weather. Eco-Loop replaces that with an autonomous agent: an
> open-source LLM that watches a live EnergyPlus simulation through MCP
> tools and adjusts HVAC setpoints every control interval — no human in
> the loop."

## 0:20 – 0:45 — Architecture

Show `docs/ARCHITECTURE.md`'s diagram (or say it out loud):

> "EnergyPlus produces real sensor data every timestep. A sensor layer
> normalizes it. An MCP server exposes it as tools. The LLM agent calls
> those tools, reasons, and returns a structured decision. A deterministic
> constraint validator clamps anything unsafe. Only then does it reach
> the actuator layer and go back into EnergyPlus."

## 0:45 – 1:45 — LIVE Closed-Loop Run

Run:

```
python scripts/run_ai.py
```

Narrate the console output as it streams, pointing out real log lines
like:

```
INFO | energyplus_runner | Starting EnergyPlus (ai mode) idf=... epw=... out=...
INFO | mcp.tools | push_building_state: t=2024-07-01T14:00:00 zone_temp=25.20 occ=6.0
DEBUG | building_agent | Context gathered via MCP tools: comfort={...} energy={...} ...
INFO | mcp.tools | apply_control_action: action=change_cooling_setpoint cooling=25.10 heating=21.00 clamped=False
INFO | energyplus_runner | EnergyPlus run complete (ai mode). 288 states captured, 0 errors.
```

Call out explicitly:

> "That's a real MCP tool call — `apply_control_action` — not a mocked
> function. And the reason field there is the agent's own explanation."

## 1:45 – 2:30 — Dashboard + Baseline Comparison

Run (in a second terminal, or beforehand):

```
streamlit run dashboard/app.py
```

Walk through:
- Overview cards: baseline energy, AI energy, energy savings %.
- Energy-over-time chart: baseline vs. AI overlay.
- Zone temperature + setpoints chart (comfort maintained).
- Agent Decision Log table: timestamp, reason, expected effect, result.

## 2:30 – 3:00 — Savings, Comfort, Conclusion

> "Across this run, the AI-controlled building used [X]% less total
> energy than the fixed-schedule baseline, while keeping comfort
> compliance at [Y]% — the numbers on screen are from the actual
> simulation you just watched, not canned data. Eco-Loop shows a
> complete closed loop — EnergyPlus, an open-source LLM, and MCP tool
> calling — working together with zero manual intervention."

## Fallback if EnergyPlus/LLM isn't available live

If a live run isn't possible in the room, use pre-generated
`data/*.csv` / `data/metrics.json` from an earlier `run_demo.py` and open
straight to the dashboard — the console-log narration in 0:45–1:45 can
be shown from `logs/agent.log` / `logs/mcp.log` instead of a live stream.
