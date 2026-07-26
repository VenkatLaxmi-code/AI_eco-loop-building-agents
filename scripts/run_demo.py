#!/usr/bin/env python
"""
One-command demo: validates configuration, runs the baseline experiment,
runs the AI-controlled experiment (full autonomous closed loop), compares
results, and prints the final metrics - exactly what's needed to record
the 3-minute demo described in docs/DEMO_SCRIPT.md.

Usage:
    python scripts/run_demo.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import configure_logging  # noqa: E402


def _step(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main() -> int:
    configure_logging()

    _step("STEP 1/6 - Validating configuration")
    import scripts.check_setup as check_setup  # type: ignore
    setup_ok = check_setup.main() == 0
    if not setup_ok:
        print(
            "\nSetup check reported issues (see above). Continuing anyway - "
            "experiments will fail with a clear error if something critical "
            "(EnergyPlus / weather file) is missing.\n"
        )

    from app.control.closed_loop import run_baseline_experiment, run_ai_experiment
    from app.analytics.comparison import compare
    from app.simulation.energyplus_runner import EnergyPlusNotFoundError, EnergyPlusRunError

    _step("STEP 2/6 - Running BASELINE experiment (fixed-schedule control)")
    t0 = time.time()
    try:
        baseline_result = run_baseline_experiment()
    except (EnergyPlusNotFoundError, EnergyPlusRunError, FileNotFoundError) as exc:
        print(f"\nERROR during baseline run: {exc}\n")
        return 1
    print(f"Baseline complete in {time.time() - t0:.1f}s "
          f"({len(baseline_result.states)} states captured).")

    _step("STEP 3/6 - Running AI-CONTROLLED experiment (autonomous closed loop)")
    t0 = time.time()
    try:
        ai_result = run_ai_experiment()
    except (EnergyPlusNotFoundError, EnergyPlusRunError, FileNotFoundError, RuntimeError) as exc:
        print(f"\nERROR during AI run: {exc}\n")
        return 1
    print(f"AI run complete in {time.time() - t0:.1f}s "
          f"({len(ai_result.states)} states, {len(ai_result.decisions)} agent decisions).")

    _step("STEP 4/6 - Saving results")
    print("data/baseline_results.csv")
    print("data/ai_results.csv")
    print("data/agent_decisions.csv")

    _step("STEP 5/6 - Comparing baseline vs AI")
    metrics = compare()

    _step("STEP 6/6 - FINAL METRICS")
    print(f"Baseline total energy : {metrics['baseline']['total_energy_kwh']:.2f} kWh")
    print(f"AI total energy       : {metrics['ai']['total_energy_kwh']:.2f} kWh")
    if metrics["energy_savings_percent"] is not None:
        print(f"Energy savings        : {metrics['energy_savings_percent']:.2f}%")
    if metrics["peak_demand_reduction_percent"] is not None:
        print(f"Peak demand reduction : {metrics['peak_demand_reduction_percent']:.2f}%")
    print(f"Baseline comfort compliance : {metrics['baseline']['comfort_compliance_percent']:.2f}%")
    print(f"AI comfort compliance       : {metrics['ai']['comfort_compliance_percent']:.2f}%")

    print("\nData is ready for the dashboard. Launch it with:")
    print("    streamlit run dashboard/app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
