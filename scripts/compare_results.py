#!/usr/bin/env python
"""
Computes and prints baseline vs AI energy/comfort metrics from the CSVs
produced by run_baseline.py and run_ai.py, and writes data/metrics.json
for the dashboard.

Usage:
    python scripts/compare_results.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import configure_logging  # noqa: E402


def main() -> int:
    configure_logging()
    from app.analytics.comparison import compare

    try:
        metrics = compare()
    except FileNotFoundError as exc:
        print(f"\nERROR: {exc}\n")
        return 1

    print("=" * 70)
    print("BASELINE vs AI - Eco-Loop Building Agents")
    print("=" * 70)
    print(f"Baseline total energy : {metrics['baseline']['total_energy_kwh']:.2f} kWh")
    print(f"AI total energy       : {metrics['ai']['total_energy_kwh']:.2f} kWh")
    if metrics["energy_savings_percent"] is not None:
        print(f"Energy savings        : {metrics['energy_savings_percent']:.2f}% "
              f"({metrics['energy_savings_kwh']:.2f} kWh)")
    if metrics["peak_demand_reduction_percent"] is not None:
        print(f"Peak demand reduction : {metrics['peak_demand_reduction_percent']:.2f}%")
    print(f"Baseline comfort compliance : {metrics['baseline']['comfort_compliance_percent']:.2f}%")
    print(f"AI comfort compliance       : {metrics['ai']['comfort_compliance_percent']:.2f}%")
    print("=" * 70)
    print("Full metrics written to data/metrics.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
