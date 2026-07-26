#!/usr/bin/env python
"""
Runs the AI experiment: EnergyPlus controlled autonomously, closed-loop,
by the LLM agent through MCP tools, with no human intervention.

Usage:
    python scripts/run_ai.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import configure_logging  # noqa: E402


def main() -> int:
    configure_logging()
    from app.control.closed_loop import run_ai_experiment
    from app.simulation.energyplus_runner import EnergyPlusNotFoundError, EnergyPlusRunError

    print("Running AI-controlled experiment (autonomous closed loop)...")
    print(f"Control interval: check .env CONTROL_INTERVAL_MINUTES")
    try:
        result = run_ai_experiment()
    except EnergyPlusNotFoundError as exc:
        print(f"\nERROR: EnergyPlus could not be located.\n{exc}\n")
        return 1
    except EnergyPlusRunError as exc:
        print(f"\nERROR: EnergyPlus simulation failed.\n{exc}\n")
        return 1
    except FileNotFoundError as exc:
        print(f"\nERROR: {exc}\n")
        return 1
    except RuntimeError as exc:
        print(f"\nERROR: {exc}\n")
        return 1

    print(f"AI run complete. Exit code={result.exit_code}. "
          f"States captured: {len(result.states)}. Decisions: {len(result.decisions)}. "
          f"Errors: {len(result.errors)}.")
    print("Results written to data/ai_results.csv and data/agent_decisions.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
