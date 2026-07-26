# Eco-Loop Building Agents

**Autonomous AI Building Energy Optimization using EnergyPlus + Open-Source LLM + MCP**

A complete, runnable hackathon project that turns a simulated building into
a live, self-correcting, closed-loop system: an open-source LLM agent
observes real EnergyPlus simulation data through genuine MCP (Model
Context Protocol) tool calls, reasons about comfort/energy trade-offs, and
issues HVAC setpoint changes — validated by a deterministic safety layer —
every control interval, with **no human intervention** during the run.

# Eco-Loop Building Agents

Autonomous Physical AI for building energy optimization using EnergyPlus,
MCP, and an open-source LLM.

## 🎥 PoC Demo Video

**[▶ Watch the 3-Minute Eco-Loop PoC Demo](YOUR_GOOGLE_DRIVE_LINK)**

> Demonstrates the EnergyPlus simulation, autonomous AI control,
> MCP integration, dashboard, and baseline-vs-AI results.

## Overview
...

## Table of Contents

- [Problem Statement](#problem-statement)
- [Architecture](#architecture)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Folder Structure](#folder-structure)
- [Prerequisites](#prerequisites)
- [Windows Setup](#windows-setup)
- [macOS / Linux Setup](#macos--linux-setup)
- [Configuring Ollama (Open-Source LLM)](#configuring-ollama-open-source-llm)
- [Running the Project](#running-the-project)
- [Dashboard](#dashboard)
- [Troubleshooting](#troubleshooting)
- [Testing](#testing)

## Problem Statement

Traditional Building Management Systems rely on fixed rules and schedules
and cannot continuously adapt to changing weather, occupancy, energy
demand, and comfort requirements. This project demonstrates a live
operational Physical AI proof-of-concept: an autonomous, self-correcting
control loop built on a real building-energy simulator.

## Architecture

```
EnergyPlus Simulation
      ↓
Sensor Layer (zone temp, occupancy, energy, PMV, setpoints...)
      ↓
MCP Server / Tools (get_building_state, apply_control_action, ...)
      ↓
Open-Source LLM Agent (Ollama / any OpenAI-compatible endpoint)
      ↓
Structured Decision (JSON, Pydantic-validated)
      ↓
Deterministic Constraint Validator (safety/comfort bounds)
      ↓
Actuator Layer (EMS actuators on setpoint schedules)
      ↓
EnergyPlus (repeat automatically)
```

Full details, sequence, and Mermaid diagrams: **`docs/ARCHITECTURE.md`**.

## Features

- Real EnergyPlus Python API integration (no faked simulation output).
- Genuine MCP server + client (stdio subprocess, official `mcp` SDK).
- Open-source LLM agent (Ollama by default; any OpenAI-compatible
  self-hosted endpoint supported).
- Pydantic-validated structured decisions, with self-correction:
  malformed JSON → retry → deterministic fallback controller.
- Deterministic, configurable safety/comfort constraint layer the LLM
  can never bypass.
- Baseline vs. AI experiment comparison with real, computed metrics
  (never fabricated).
- Streamlit dashboard with overview cards, timeseries charts, and a full
  agent decision audit log.
- One-command demo (`scripts/run_demo.py`) and an environment checker
  (`scripts/check_setup.py`).
- Unit tests for constraints, schemas, metrics, and MCP tools that run
  with no EnergyPlus/LLM required.

## Technology Stack

| Layer | Technology |
|---|---|
| Simulation | EnergyPlus (official Python API, `pyenergyplus`) |
| Building model editing | `eppy` |
| Agent protocol | Model Context Protocol (`mcp` Python SDK, `FastMCP`) |
| LLM | Open-source, self-hosted (Ollama default: Qwen2.5 / Llama 3.1 / Mistral) |
| Validation | Pydantic v2 |
| Dashboard | Streamlit + Plotly |
| Data | pandas, numpy |
| Language | Python 3.11 (3.10+ supported) |
| Tests | pytest |

## Folder Structure

```
eco-loop-building-agents/
    README.md
    requirements.txt
    .env.example
    .gitignore
    app/
        main.py                    - entry point / logging setup
        config.py                  - environment-driven configuration
        simulation/
            energyplus_runner.py   - EnergyPlus Python API wrapper + control loop hook
            sensors.py             - reads/normalizes EnergyPlus state
            actuators.py           - writes setpoints via EMS actuators
        agent/
            building_agent.py      - MCP client + LLM orchestration
            llm_client.py          - OpenAI-compatible LLM client (Ollama default)
            prompts.py             - system/user prompt construction
            schemas.py             - Pydantic data contracts
            fallback_controller.py - deterministic rule-based fallback
        mcp_server/
            server.py               - FastMCP server (stdio subprocess)
            tools.py                - tool implementations + state store
        control/
            closed_loop.py         - baseline/AI experiment runners
            constraints.py         - deterministic safety validator
        analytics/
            metrics.py              - per-run metric calculations
            comparison.py            - baseline vs AI comparison
    dashboard/
        app.py                     - Streamlit dashboard
    models/
        baseline.idf               - single-zone building model
        README.md
    weather/
        README.md                  - where/how to get an .epw file
    data/                           - generated CSV/JSON results (gitignored)
    logs/                           - generated log files (gitignored)
    scripts/
        check_setup.py
        run_baseline.py
        run_ai.py
        compare_results.py
        run_demo.py
    tests/
        test_constraints.py
        test_agent_schema.py
        test_metrics.py
        test_tools.py
    docs/
        ARCHITECTURE.md
        SYSTEM_REPORT.md
        DEMO_SCRIPT.md
        PRESENTATION_CONTENT.md
```

## Prerequisites

You need to install these **manually** (they cannot be pip-installed):

1. **Python 3.11** (3.10+ works) — https://www.python.org/downloads/
2. **EnergyPlus 23.x or 24.x** — https://energyplus.net/downloads
   (ships the `pyenergyplus` Python API inside its install folder)
3. **Ollama** (recommended open-source LLM runner) — https://ollama.com/download
4. An EnergyPlus weather file (`.epw`) for your location — see
   `weather/README.md`

## Windows Setup

Open the project folder in VS Code, then in its integrated terminal:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` in VS Code and set at minimum:

```
ENERGYPLUS_HOME=C:\EnergyPlusV24-1-0
WEATHER_FILE=weather/USA_CA_San.Francisco.Intl.AP.724940_TMY3.epw
```

(Adjust the EnergyPlus path to wherever the installer put it, and the
weather file name to whatever you downloaded into `weather/` — see
`weather/README.md`.)

Then:

```bat
python scripts\check_setup.py
python scripts\run_baseline.py
python scripts\run_ai.py
python scripts\compare_results.py
python scripts\run_demo.py

streamlit run dashboard\app.py
```

## macOS / Linux Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```
ENERGYPLUS_HOME=/usr/local/EnergyPlus-24-1-0
WEATHER_FILE=weather/USA_CA_San.Francisco.Intl.AP.724940_TMY3.epw
```

Then:

```bash
python scripts/check_setup.py
python scripts/run_baseline.py
python scripts/run_ai.py
python scripts/compare_results.py
python scripts/run_demo.py

streamlit run dashboard/app.py
```

## Configuring Ollama (Open-Source LLM)

1. **Install** Ollama from https://ollama.com/download and make sure it's running
   (`ollama serve`, or it starts automatically after installation).
2. **Pull a model** (tool-calling-capable instruct models work best):

   ```
   ollama pull qwen2.5:7b-instruct
   ```

   Alternatives: `llama3.1:8b`, `mistral:7b-instruct`.

3. **Environment variables** (already set to sane Ollama defaults in
   `.env.example`):

   ```
   LLM_PROVIDER=ollama
   LLM_BASE_URL=http://localhost:11434
   LLM_MODEL=qwen2.5:7b-instruct
   LLM_TIMEOUT_SECONDS=60
   LLM_API_KEY=
   ```

4. **Verify the connection**:

   ```
   python scripts/check_setup.py
   ```

   Look for `[PASS] LLM reachable (ollama @ http://localhost:11434)`.

5. **Switch models**: pull the new model with `ollama pull <name>`, then
   set `LLM_MODEL=<name>` in `.env`. No code changes needed.

6. **Using a different self-hosted, OpenAI-compatible server** (vLLM, LM
   Studio, text-generation-webui): set `LLM_PROVIDER=openai_compatible`
   and point `LLM_BASE_URL` at that server's `/v1`-style base URL; set
   `LLM_API_KEY` if it requires one.

## Running the Project

| Command | What it does |
|---|---|
| `python scripts/check_setup.py` | Validates Python, packages, EnergyPlus, weather file, IDF, LLM connection, and write permissions |
| `python scripts/run_baseline.py` | Runs EnergyPlus with fixed schedules; writes `data/baseline_results.csv` |
| `python scripts/run_ai.py` | Runs the full autonomous closed loop; writes `data/ai_results.csv` + `data/agent_decisions.csv` |
| `python scripts/compare_results.py` | Computes baseline-vs-AI metrics into `data/metrics.json` |
| `python scripts/run_demo.py` | Runs all of the above in sequence and prints final metrics — the one-command demo |
| `streamlit run dashboard/app.py` | Opens the interactive dashboard |

## Dashboard

```
streamlit run dashboard/app.py
```

Shows: overview cards (baseline/AI energy, savings %, peak demand
reduction, average temperature, comfort compliance), timeseries charts
(energy, temperature, setpoints, PMV, occupancy, AI actions), and the
full agent decision log table. If the underlying CSV/JSON files don't
exist yet, the dashboard tells you exactly which script to run first.


## Troubleshooting

**EnergyPlus not found**
Set `ENERGYPLUS_HOME` in `.env` to your actual install directory (the
folder that directly contains `energyplus.exe`/`energyplus` and a
`pyenergyplus` subfolder). Re-run `python scripts/check_setup.py`.

**`pyenergyplus` import failure**
Usually means `ENERGYPLUS_HOME` doesn't point at a valid EnergyPlus ≥ 9.5
install, or you're running a Python version/architecture mismatched with
your EnergyPlus build. Confirm the folder contains a `pyenergyplus/`
subdirectory.

**Invalid IDF**
If EnergyPlus rejects `models/baseline.idf` due to a version mismatch,
run the `IDFVersionUpdater` tool that ships with your EnergyPlus
installation to upgrade the file, or check `data/*/eplusout.err` for the
exact error EnergyPlus reported.

**Missing EPW**
Download a weather file from https://energyplus.net/weather and place it
in `weather/`, then update `WEATHER_FILE` in `.env` — see
`weather/README.md`.

**Ollama unavailable**
Make sure `ollama serve` is running and `LLM_BASE_URL` matches (default
`http://localhost:11434`). `python scripts/check_setup.py` reports this
explicitly.

**Model missing**
`ollama pull <model_name>` the model referenced by `LLM_MODEL` in `.env`.

**MCP connection failure**
`BuildingAgent` spawns `python -m app.mcp_server.server` as a subprocess;
make sure `python` on your PATH inside the active virtual environment can
run that module standalone (`python -m app.mcp_server.server` should
start without error and wait on stdio).

**LLM malformed JSON**
Expected and handled: the agent retries once with an error hint, then
uses the deterministic fallback controller. Check `logs/agent.log` for
the specific validation error if decisions look wrong.

**Simulation crash**
Check `data/baseline_run/eplusout.err` or `data/ai_run/eplusout.err` (the
per-run EnergyPlus output directories) and `logs/errors.log`. A single
bad control-step callback is caught and logged without crashing the run;
a hard EnergyPlus engine failure will raise `EnergyPlusRunError` with the
exit code and point you at the same `.err` file.

## Testing

```
pytest tests/ -v
```

All tests run without EnergyPlus, Ollama, or network access — they cover
constraint validation, agent decision schema validation, metrics/energy
savings calculations, and MCP tool logic directly.
