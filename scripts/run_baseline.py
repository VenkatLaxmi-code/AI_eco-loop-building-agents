#!/usr/bin/env python
"""
Runs the BASELINE experiment: EnergyPlus operating with its native
fixed-schedule setpoints (no AI control), representing a conventional
building management system.

Usage:
    python scripts/run_baseline.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import configure_logging  # noqa: E402


def main() -> int:
    configure_logging()
    from app.control.closed_loop import run_baseline_experiment
    from app.simulation.energyplus_runner import EnergyPlusNotFoundError, EnergyPlusRunError

    print("Running baseline experiment (fixed-schedule control)...")
    try:
        result = run_baseline_experiment()
    except EnergyPlusNotFoundError as exc:
        print(f"\nERROR: EnergyPlus could not be located.\n{exc}\n")
        return 1
    except EnergyPlusRunError as exc:
        print(f"\nERROR: EnergyPlus simulation failed.\n{exc}\n")
        return 1
    except FileNotFoundError as exc:
        print(f"\nERROR: {exc}\n")
        return 1

    print(f"Baseline run complete. Exit code={result.exit_code}. "
          f"States captured: {len(result.states)}. Errors: {len(result.errors)}.")
    print("Results written to data/baseline_results.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
