"""
Eco-Loop Building Agents - Streamlit Dashboard.

Run with:
    streamlit run dashboard/app.py

Reads the CSV/JSON artifacts produced by scripts/run_demo.py (or
run_baseline.py + run_ai.py + compare_results.py individually) from the
data/ directory and renders overview cards, timeseries charts, and the
agent decision audit log.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

st.set_page_config(
    page_title="Eco-Loop Building Agents",
    page_icon="🏢",
    layout="wide",
)

DATA_DIR = settings.paths.data_dir


@st.cache_data(ttl=5)
def load_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


@st.cache_data(ttl=5)
def load_metrics() -> dict:
    path = DATA_DIR / "metrics.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def render_header() -> None:
    st.title("🏢 Eco-Loop Building Agents")
    st.caption(
        "Autonomous AI Building Energy Optimization — EnergyPlus + Open-Source LLM + MCP"
    )


def render_overview(metrics: dict) -> None:
    if not metrics:
        st.warning(
            "No results found yet. Run `python scripts/run_demo.py` "
            "(or run_baseline.py + run_ai.py + compare_results.py) to generate data."
        )
        return

    baseline = metrics.get("baseline", {})
    ai = metrics.get("ai", {})

    cols = st.columns(6)
    cols[0].metric("Baseline Energy", f"{baseline.get('total_energy_kwh', 0):.1f} kWh")
    cols[1].metric("AI Energy", f"{ai.get('total_energy_kwh', 0):.1f} kWh")

    savings = metrics.get("energy_savings_percent")
    cols[2].metric(
        "Energy Savings", f"{savings:.1f}%" if savings is not None else "N/A",
        delta=None if savings is None else f"{metrics.get('energy_savings_kwh', 0):.1f} kWh saved",
    )

    peak_reduction = metrics.get("peak_demand_reduction_percent")
    cols[3].metric(
        "Peak Demand Reduction",
        f"{peak_reduction:.1f}%" if peak_reduction is not None else "N/A",
    )
    cols[4].metric("Avg Zone Temp (AI)", f"{ai.get('average_zone_temperature_c', 0):.1f} °C")
    cols[5].metric("Comfort Compliance (AI)", f"{ai.get('comfort_compliance_percent', 0):.1f}%")


def render_energy_chart(baseline_df: pd.DataFrame, ai_df: pd.DataFrame) -> None:
    st.subheader("Energy Consumption Over Time")
    fig = go.Figure()
    if not baseline_df.empty:
        fig.add_trace(go.Scatter(
            x=baseline_df["timestamp"], y=baseline_df["total_electricity_w"],
            name="Baseline", line=dict(color="#EF553B"),
        ))
    if not ai_df.empty:
        fig.add_trace(go.Scatter(
            x=ai_df["timestamp"], y=ai_df["total_electricity_w"],
            name="AI-Controlled", line=dict(color="#00CC96"),
        ))
    fig.update_layout(xaxis_title="Time", yaxis_title="Total Electricity Demand (W)", height=380)
    st.plotly_chart(fig, use_container_width=True)


def render_baseline_vs_ai_bar(metrics: dict) -> None:
    if not metrics:
        return
    st.subheader("Baseline vs AI - Total Energy")
    fig = go.Figure(data=[
        go.Bar(
            x=["Baseline", "AI-Controlled"],
            y=[metrics["baseline"]["total_energy_kwh"], metrics["ai"]["total_energy_kwh"]],
            marker_color=["#EF553B", "#00CC96"],
            text=[f"{metrics['baseline']['total_energy_kwh']:.1f} kWh",
                  f"{metrics['ai']['total_energy_kwh']:.1f} kWh"],
            textposition="auto",
        )
    ])
    fig.update_layout(yaxis_title="Total Energy (kWh)", height=350)
    st.plotly_chart(fig, use_container_width=True)


def render_temperature_chart(ai_df: pd.DataFrame) -> None:
    st.subheader("Zone Temperature & Setpoints (AI Run)")
    if ai_df.empty:
        st.info("No AI run data yet.")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ai_df["timestamp"], y=ai_df["zone_temperature"], name="Zone Temp"))
    fig.add_trace(go.Scatter(x=ai_df["timestamp"], y=ai_df["cooling_setpoint"], name="Cooling Setpoint",
                              line=dict(dash="dash")))
    fig.add_trace(go.Scatter(x=ai_df["timestamp"], y=ai_df["heating_setpoint"], name="Heating Setpoint",
                              line=dict(dash="dash")))
    fig.update_layout(xaxis_title="Time", yaxis_title="Temperature (°C)", height=380)
    st.plotly_chart(fig, use_container_width=True)


def render_comfort_chart(ai_df: pd.DataFrame) -> None:
    st.subheader("Thermal Comfort (PMV) & Occupancy")
    if ai_df.empty or "pmv" not in ai_df.columns:
        st.info("No AI run data yet.")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ai_df["timestamp"], y=ai_df["pmv"], name="PMV"))
    fig.add_trace(go.Scatter(
        x=ai_df["timestamp"], y=ai_df["occupancy"], name="Occupancy",
        yaxis="y2", line=dict(color="#AB63FA"),
    ))
    fig.update_layout(
        xaxis_title="Time",
        yaxis=dict(title="PMV"),
        yaxis2=dict(title="Occupancy", overlaying="y", side="right"),
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_peak_demand_chart(baseline_df: pd.DataFrame, ai_df: pd.DataFrame) -> None:
    st.subheader("Peak Demand Comparison")
    peaks = []
    labels = []
    if not baseline_df.empty:
        peaks.append(baseline_df["total_electricity_w"].max())
        labels.append("Baseline")
    if not ai_df.empty:
        peaks.append(ai_df["total_electricity_w"].max())
        labels.append("AI-Controlled")
    if not peaks:
        st.info("No data yet.")
        return
    fig = go.Figure(data=[go.Bar(x=labels, y=peaks, marker_color=["#EF553B", "#00CC96"][: len(peaks)])])
    fig.update_layout(yaxis_title="Peak Demand (W)", height=320)
    st.plotly_chart(fig, use_container_width=True)


def render_actions_chart(decisions_df: pd.DataFrame) -> None:
    st.subheader("AI Actions Over Time")
    if decisions_df.empty:
        st.info("No agent decisions recorded yet.")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=decisions_df["timestamp"], y=decisions_df["new_cooling_setpoint"],
        name="Cooling Setpoint", mode="lines+markers",
    ))
    fig.add_trace(go.Scatter(
        x=decisions_df["timestamp"], y=decisions_df["new_heating_setpoint"],
        name="Heating Setpoint", mode="lines+markers",
    ))
    fig.update_layout(xaxis_title="Time", yaxis_title="Setpoint (°C)", height=380)
    st.plotly_chart(fig, use_container_width=True)


def render_decision_log(decisions_df: pd.DataFrame) -> None:
    st.subheader("Agent Decision Log")
    if decisions_df.empty:
        st.info("No agent decisions recorded yet. Run the AI experiment first.")
        return
    display_cols = [
        "timestamp", "action", "old_cooling_setpoint", "new_cooling_setpoint",
        "old_heating_setpoint", "new_heating_setpoint", "reason", "expected_effect",
        "result", "tool_used", "confidence", "source",
    ]
    display_cols = [c for c in display_cols if c in decisions_df.columns]
    st.dataframe(decisions_df[display_cols].sort_values("timestamp", ascending=False),
                 use_container_width=True, height=420)


def main() -> None:
    render_header()

    baseline_df = load_csv("baseline_results.csv")
    ai_df = load_csv("ai_results.csv")
    decisions_df = load_csv("agent_decisions.csv")
    metrics = load_metrics()

    render_overview(metrics)
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        render_energy_chart(baseline_df, ai_df)
        render_temperature_chart(ai_df)
        render_peak_demand_chart(baseline_df, ai_df)
    with col2:
        render_baseline_vs_ai_bar(metrics)
        render_comfort_chart(ai_df)
        render_actions_chart(decisions_df)

    st.divider()
    render_decision_log(decisions_df)

    with st.sidebar:
        st.header("Run Controls")
        st.markdown(
            "This dashboard is **read-only**. Generate/refresh data from a terminal:\n\n"
            "```\npython scripts/run_demo.py\n```\n"
            "or step by step:\n\n"
            "```\npython scripts/run_baseline.py\npython scripts/run_ai.py\n"
            "python scripts/compare_results.py\n```"
        )
        if st.button("🔄 Refresh data"):
            st.cache_data.clear()
            st.rerun()


if __name__ == "__main__":
    main()
