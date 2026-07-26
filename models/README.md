# Building Model: `baseline.idf`

A single-zone office building model (5m x 5m x 3m, `MAIN_ZONE`) used for
**both** experiments:

- **Baseline run**: EnergyPlus operates the zone using its native
  `Schedule:Constant` cooling/heating setpoint schedules
  (`CLG_SETPOINT_SCHED` = 24 C, `HTG_SETPOINT_SCHED` = 21 C) — a
  conventional, fixed-schedule Building Management System.
- **AI run**: The exact same IDF is used, but `app/simulation/actuators.py`
  overrides those two schedules every control interval via EnergyPlus EMS
  actuators (`Schedule:Constant` / `Schedule Value`), driven by the
  autonomous agent's decisions. No IDF editing or restart is required.

## Key objects

| Object | Purpose |
|---|---|
| `Zone: MAIN_ZONE` | The single conditioned thermal zone |
| `People: MAIN_ZONE People` | Occupancy schedule (drives the `occupancy` sensor value) |
| `Schedule:Constant: CLG_SETPOINT_SCHED / HTG_SETPOINT_SCHED` | EMS-actuatable setpoint schedules |
| `ZoneControl:Thermostat` + `ThermostatSetpoint:DualSetpoint` | Ties the schedules to the zone thermostat |
| `ZoneHVAC:IdealLoadsAirSystem` | Ideal-loads HVAC (isolates control-strategy effects from a specific plant/equipment design) |
| `Output:Variable` | Zone air temperature, PMV, electricity, etc. — everything `app/simulation/sensors.py` reads |

## RunPeriod, weather, and simulation length

- `RunPeriod` in the IDF is a placeholder; at runtime,
  `app/simulation/energyplus_runner.py::_prepare_idf_with_run_period` uses
  `eppy` to rewrite the begin/end dates from your `.env` values
  (`RUN_PERIOD_START_MONTH`, `RUN_PERIOD_START_DAY`, `SIMULATION_DAYS`)
  and saves a `_prepared_<mode>.idf` copy into the run's output folder —
  the original `models/baseline.idf` is never modified.
- The weather file is supplied separately at the command line
  (`-w <epw>`), so `baseline.idf` works with **any** EPW — see
  `weather/README.md`.

## Verifying / editing this IDF

If you want to inspect or modify the geometry, open `baseline.idf` in:

- **IDF Editor** (ships with EnergyPlus on Windows), or
- **OpenStudio's IDF viewer**, or
- Any text editor (it's plain text).

If your installed EnergyPlus version is newer than the `Version,24.1;`
declared at the top of the file and it fails to run, use the
`IDFVersionUpdater` tool that ships with your EnergyPlus installation to
upgrade it — `scripts/check_setup.py` will tell you if EnergyPlus rejects
the file for this reason.
