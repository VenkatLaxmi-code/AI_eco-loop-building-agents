"""
EnergyPlusRunner: thin, robust wrapper around the official EnergyPlus
Python API (pyenergyplus).

The pyenergyplus package ships INSIDE an EnergyPlus installation (it is
not a pip package), so it is imported lazily and its folder is added to
sys.path from ENERGYPLUS_API_PATH / ENERGYPLUS_HOME. This lets the rest
of the codebase (config, schemas, tests, dashboard) import cleanly even
on a machine where EnergyPlus is not yet installed.
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from app.agent.schemas import BuildingState, ValidatedAction
from app.config import settings
from app.simulation.actuators import ActuatorController
from app.simulation.sensors import SensorReader

logger = logging.getLogger("energyplus_runner")


class EnergyPlusNotFoundError(RuntimeError):
    """Raised when the EnergyPlus installation / Python API cannot be located."""


class EnergyPlusRunError(RuntimeError):
    """Raised when the EnergyPlus simulation itself fails or returns a non-zero exit code."""


@dataclass
class RunResult:
    mode: str
    exit_code: int
    states: List[BuildingState] = field(default_factory=list)
    decisions: List[dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    output_dir: Optional[Path] = None


def _import_pyenergyplus():
    """
    Locate and import the pyenergyplus package from the configured
    EnergyPlus installation. Raises EnergyPlusNotFoundError with a clear,
    actionable message if it cannot be found - the caller (control loop /
    check_setup script) is responsible for surfacing this to the user
    instead of crashing the whole process.
    """
    api_path = settings.energyplus.api_path
    if not api_path:
        raise EnergyPlusNotFoundError(
            "ENERGYPLUS_HOME / ENERGYPLUS_API_PATH is not set in your .env file. "
            "Point it at your EnergyPlus installation directory, e.g. "
            "C:\\EnergyPlusV24-1-0 on Windows."
        )

    candidate = Path(api_path)
    if not candidate.exists():
        raise EnergyPlusNotFoundError(
            f"EnergyPlus path '{candidate}' does not exist. Check ENERGYPLUS_HOME "
            "in your .env file."
        )

    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

    try:
        from pyenergyplus.api import EnergyPlusAPI  # type: ignore
    except ImportError as exc:
        raise EnergyPlusNotFoundError(
            "Could not import 'pyenergyplus'. This module ships inside the "
            f"EnergyPlus installation folder, not via pip. Checked '{candidate}'. "
            "Verify ENERGYPLUS_HOME points at a valid EnergyPlus >= 9.5 install "
            "that contains a 'pyenergyplus' subfolder."
        ) from exc

    return EnergyPlusAPI


DecisionCallback = Callable[[BuildingState, List[BuildingState], List[dict]], ValidatedAction]


class EnergyPlusRunner:
    """
    Runs one EnergyPlus simulation (baseline or AI-controlled) and, when a
    decision_callback is supplied, closes the loop every
    `control_interval_minutes` of simulated time by asking the callback
    for a new (already-validated) setpoint action and pushing it back
    into the simulation via EMS actuators.
    """

    def __init__(
        self,
        idf_path: str,
        epw_path: str,
        output_dir: str,
        zone_name: Optional[str] = None,
        control_interval_minutes: int = 15,
        mode: str = "baseline",
        decision_callback: Optional[DecisionCallback] = None,
    ) -> None:
        self.idf_path = settings.resolve(idf_path)
        self.epw_path = settings.resolve(epw_path)
        self.output_dir = settings.resolve(output_dir)
        self.zone_name = zone_name or settings.energyplus.zone_name
        self.control_interval_minutes = control_interval_minutes
        self.mode = mode
        self.decision_callback = decision_callback

        self.sensor_reader = SensorReader(zone_name=self.zone_name)
        self.actuators = ActuatorController()

        self.sim_start: datetime = datetime(2024, settings.control.run_period_start_month,
                                             settings.control.run_period_start_day)
        self._last_control_minute: Optional[float] = None
        self._api = None
        self._state = None

        self.result = RunResult(mode=mode, exit_code=-1, output_dir=self.output_dir)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate_inputs(self) -> None:
        if not self.idf_path.exists():
            raise FileNotFoundError(f"IDF file not found: {self.idf_path}")
        if not self.epw_path.exists():
            raise FileNotFoundError(
                f"Weather file (EPW) not found: {self.epw_path}. "
                "Download one from https://energyplus.net/weather and set "
                "WEATHER_FILE in your .env file."
            )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Apply SIMULATION_DAYS / RUN_PERIOD_START_* from .env into the IDF's
    # RunPeriod object using eppy, so the run length is configurable
    # without ever hand-editing the IDF file.
    # ------------------------------------------------------------------
    def _prepare_idf_with_run_period(self) -> Path:
        try:
            from eppy.modeleditor import IDF as EppyIDF
        except ImportError:
            logger.warning("eppy not installed; running IDF as-is with its built-in RunPeriod.")
            return self.idf_path

        idd_path = Path(settings.energyplus.home) / "Energy+.idd"
        if not idd_path.exists():
            logger.warning(
                "Energy+.idd not found at %s; running IDF as-is with its built-in RunPeriod.",
                idd_path,
            )
            return self.idf_path

        try:
            if EppyIDF.getiddname() is None:
                EppyIDF.setiddname(str(idd_path))
            idf = EppyIDF(str(self.idf_path))

            start_month = settings.control.run_period_start_month
            start_day = settings.control.run_period_start_day
            days = max(1, settings.control.simulation_days)

            from datetime import date, timedelta

            start_date = date(2024, start_month, start_day)
            end_date = start_date + timedelta(days=days - 1)

            run_periods = idf.idfobjects.get("RUNPERIOD", [])
            if run_periods:
                rp = run_periods[0]
                rp.Begin_Month = start_date.month
                rp.Begin_Day_of_Month = start_date.day
                rp.End_Month = end_date.month
                rp.End_Day_of_Month = end_date.day

            prepared_path = self.output_dir / f"_prepared_{self.mode}.idf"
            idf.saveas(str(prepared_path))
            logger.info(
                "Prepared IDF with RunPeriod %s -> %s (%d day(s)): %s",
                start_date, end_date, days, prepared_path,
            )
            return prepared_path
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Could not adjust RunPeriod via eppy (%s); running IDF as-is.", exc
            )
            return self.idf_path

    # ------------------------------------------------------------------
    # Callback registered with EnergyPlus - fires every zone timestep
    # ------------------------------------------------------------------
    def _on_zone_timestep(self, api_state) -> None:
        api = self._api
        try:
            if not self.sensor_reader.handles.resolved:
                if not self.sensor_reader.resolve_handles(api, api_state):
                    return
            if not self.actuators.handles.resolved:
                if not self.actuators.resolve_handles(api, api_state):
                    return
                # Seed the schedules with sane starting setpoints.
                self.actuators.initialize_defaults(api, api_state, 24.0, 21.0)

            current_state = self.sensor_reader.read_state(
                api,
                api_state,
                cooling_setpoint=self.actuators.current_cooling_setpoint,
                heating_setpoint=self.actuators.current_heating_setpoint,
                sim_start=self.sim_start,
            )
            if current_state is None:
                return

            # EnergyPlus calls this callback during warm-up as well.
            # Record the state, but do NOT invoke the LLM agent until
            # warm-up has completed and the actual simulation has begun.
            if api.exchange.warmup_flag(api_state):
                return

            self.result.states.append(current_state)

            if self.mode != "ai" or self.decision_callback is None:
                return

            elapsed_minutes = (
                (current_state.simulation_day - 1) * 24 * 60
                + current_state.simulation_hour * 60
                + api.exchange.minutes(api_state)
            )
            if (
                self._last_control_minute is not None
                and elapsed_minutes - self._last_control_minute < self.control_interval_minutes
            ):
                return
            self._last_control_minute = elapsed_minutes

            validated_action = self.decision_callback(
                current_state, self.result.states, self.result.decisions
            )
            self.actuators.apply(
                api, api_state, validated_action.cooling_setpoint, validated_action.heating_setpoint
            )
        except Exception as exc:  # noqa: BLE001 - a single bad timestep must not crash EnergyPlus
            msg = f"Error in zone-timestep callback at step: {exc}"
            logger.exception(msg)
            self.result.errors.append(msg)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(self) -> RunResult:
        self.validate_inputs()
        EnergyPlusAPI = _import_pyenergyplus()

        self._api = EnergyPlusAPI()
        self._state = self._api.state_manager.new_state()

        self._api.runtime.callback_begin_zone_timestep_after_init_heat_balance(
            self._state, self._on_zone_timestep
        )

        def _collect_error(message: str) -> None:
            logger.error("EnergyPlus error: %s", message)
            self.result.errors.append(message)

        self._api.runtime.callback_message(self._state, _collect_error)

        prepared_idf = self._prepare_idf_with_run_period()

        args = [
            "-w", str(self.epw_path),
            "-d", str(self.output_dir),
            "-r",
            str(prepared_idf),
        ]

        logger.info(
            "Starting EnergyPlus (%s mode) idf=%s epw=%s out=%s",
            self.mode, prepared_idf, self.epw_path, self.output_dir,
        )

        exit_code = self._api.runtime.run_energyplus(self._state, args)
        self.result.exit_code = exit_code

        if exit_code != 0:
            raise EnergyPlusRunError(
                f"EnergyPlus exited with code {exit_code}. See {self.output_dir}/eplusout.err "
                "for details, and logs/simulation.log for the captured messages."
            )

        self._api.state_manager.delete_state(self._state)
        logger.info(
            "EnergyPlus run complete (%s mode). %d states captured, %d errors.",
            self.mode, len(self.result.states), len(self.result.errors),
        )
        return self.result
