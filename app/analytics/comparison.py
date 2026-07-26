"""Baseline vs AI comparison: the headline numbers for the dashboard and report."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from app.analytics.metrics import summarize_run
from app.config import settings

logger = logging.getLogger("comparison")


def compute_savings_percent(baseline_kwh: float, ai_kwh: float) -> float:
    """
    energy_savings_percent = ((baseline_energy - ai_energy) / baseline_energy) * 100

    Returns 0.0 (rather than raising/NaN) when baseline_kwh is 0, since a
    zero-energy baseline makes a percentage reduction undefined/meaningless
    but must never crash the comparison pipeline.
    """
    if not baseline_kwh:
        return 0.0
    return round(((baseline_kwh - ai_kwh) / baseline_kwh) * 100.0, 2)


def _safe_percent(baseline: float, ai: float) -> Optional[float]:
    if baseline in (0, None):
        return None
    return compute_savings_percent(baseline, ai)


def load_results(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Results file not found: {csv_path}. Run the corresponding experiment first "
            "(scripts/run_baseline.py or scripts/run_ai.py)."
        )
    return pd.read_csv(csv_path)


def compare(
    baseline_csv: Optional[Path] = None,
    ai_csv: Optional[Path] = None,
) -> dict:
    baseline_csv = baseline_csv or (settings.paths.data_dir / "baseline_results.csv")
    ai_csv = ai_csv or (settings.paths.data_dir / "ai_results.csv")

    baseline_df = load_results(baseline_csv)
    ai_df = load_results(ai_csv)

    baseline_summary = summarize_run(baseline_df)
    ai_summary = summarize_run(ai_df)

    energy_savings_percent = _safe_percent(
        baseline_summary["total_energy_kwh"], ai_summary["total_energy_kwh"]
    )
    hvac_savings_percent = _safe_percent(
        baseline_summary["hvac_energy_kwh"], ai_summary["hvac_energy_kwh"]
    )
    peak_demand_reduction_percent = _safe_percent(
        baseline_summary["peak_demand_w"], ai_summary["peak_demand_w"]
    )

    metrics = {
        "baseline": baseline_summary,
        "ai": ai_summary,
        "energy_savings_kwh": round(
            baseline_summary["total_energy_kwh"] - ai_summary["total_energy_kwh"], 3
        ),
        "energy_savings_percent": energy_savings_percent,
        "hvac_energy_savings_percent": hvac_savings_percent,
        "peak_demand_reduction_percent": peak_demand_reduction_percent,
        "comfort_compliance_delta_percent": round(
            ai_summary["comfort_compliance_percent"] - baseline_summary["comfort_compliance_percent"], 2
        ),
    }

    out_path = settings.paths.data_dir / "metrics.json"
    out_path.write_text(json.dumps(metrics, indent=2))
    logger.info("Wrote comparison metrics to %s", out_path)
    return metrics
