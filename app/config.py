"""
Central configuration for Eco-Loop Building Agents.

All configuration is loaded from environment variables (via a .env file)
so that no secrets, absolute paths, or machine-specific values are ever
hardcoded in source code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root, wherever the process is launched from.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class EnergyPlusConfig:
    home: str = field(default_factory=lambda: os.getenv("ENERGYPLUS_HOME", ""))
    api_path: str = field(
        default_factory=lambda: os.getenv("ENERGYPLUS_API_PATH")
        or os.getenv("ENERGYPLUS_HOME", "")
    )
    weather_file: str = field(
        default_factory=lambda: os.getenv("WEATHER_FILE", "weather/example.epw")
    )
    baseline_idf: str = field(
        default_factory=lambda: os.getenv("BASELINE_IDF", "models/baseline.idf")
    )
    ai_idf: str = field(
        default_factory=lambda: os.getenv("AI_IDF", "models/baseline.idf")
    )
    zone_name: str = field(default_factory=lambda: os.getenv("ZONE_NAME", "MAIN_ZONE"))


@dataclass(frozen=True)
class LLMConfig:
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "ollama"))
    base_url: str = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "http://localhost:11434")
    )
    model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL", "qwen2.5:7b-instruct")
    )
    timeout_seconds: int = field(
        default_factory=lambda: _get_int("LLM_TIMEOUT_SECONDS", 60)
    )
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))


@dataclass(frozen=True)
class ControlConfig:
    control_interval_minutes: int = field(
        default_factory=lambda: _get_int("CONTROL_INTERVAL_MINUTES", 15)
    )
    simulation_days: int = field(
        default_factory=lambda: _get_int("SIMULATION_DAYS", 3)
    )
    run_period_start_month: int = field(
        default_factory=lambda: _get_int("RUN_PERIOD_START_MONTH", 7)
    )
    run_period_start_day: int = field(
        default_factory=lambda: _get_int("RUN_PERIOD_START_DAY", 1)
    )


@dataclass(frozen=True)
class ConstraintsConfig:
    cooling_setpoint_min: float = field(
        default_factory=lambda: _get_float("COOLING_SETPOINT_MIN", 22.0)
    )
    cooling_setpoint_max: float = field(
        default_factory=lambda: _get_float("COOLING_SETPOINT_MAX", 28.0)
    )
    heating_setpoint_min: float = field(
        default_factory=lambda: _get_float("HEATING_SETPOINT_MIN", 18.0)
    )
    heating_setpoint_max: float = field(
        default_factory=lambda: _get_float("HEATING_SETPOINT_MAX", 22.0)
    )
    min_deadband_c: float = field(
        default_factory=lambda: _get_float("MIN_DEADBAND_C", 1.5)
    )
    max_setpoint_change_per_interval: float = field(
        default_factory=lambda: _get_float("MAX_SETPOINT_CHANGE_PER_INTERVAL", 1.0)
    )
    pmv_min: float = field(default_factory=lambda: _get_float("PMV_MIN", -0.85))
    pmv_max: float = field(default_factory=lambda: _get_float("PMV_MAX", 0.85))
    occupied_temp_min: float = field(
        default_factory=lambda: _get_float("OCCUPIED_TEMP_MIN", 20.0)
    )
    occupied_temp_max: float = field(
        default_factory=lambda: _get_float("OCCUPIED_TEMP_MAX", 27.0)
    )


@dataclass(frozen=True)
class PathsConfig:
    project_root: Path = _PROJECT_ROOT
    data_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT / os.getenv("DATA_DIR", "data")
    )
    log_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT / os.getenv("LOG_DIR", "logs")
    )


@dataclass(frozen=True)
class Settings:
    energyplus: EnergyPlusConfig = field(default_factory=EnergyPlusConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    constraints: ConstraintsConfig = field(default_factory=ConstraintsConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    def ensure_directories(self) -> None:
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.paths.log_dir.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative_path: str) -> Path:
        """Resolve a path from .env relative to the project root."""
        p = Path(relative_path)
        if p.is_absolute():
            return p
        return self.paths.project_root / p


settings = Settings()
settings.ensure_directories()
