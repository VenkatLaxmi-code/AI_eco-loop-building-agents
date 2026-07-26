# Weather Files (.epw)

EnergyPlus needs an **EPW** (EnergyPlus Weather) file to run any simulation.
Weather files are region-specific and too large/license-restricted to bundle
in this repository, so you need to download one for your location.

## 1. Download a weather file

1. Go to https://energyplus.net/weather
2. Pick a region (e.g. `North and Central America`) then a country/state/city.
3. Download the `.zip` for the nearest city (it contains a `.epw` and a `.stat`/`.ddy` file).
4. Extract the `.epw` file into this `weather/` folder.

Recommended starter file (used as the default in `.env.example`):
`USA_CA_San.Francisco.Intl.AP.724940_TMY3.epw`

Any `.epw` works — just make sure the path in `.env` (`WEATHER_FILE`) matches
the file you placed here, for example:

```
WEATHER_FILE=weather/USA_CA_San.Francisco.Intl.AP.724940_TMY3.epw
```

## 2. Verify it

Run:

```
python scripts/check_setup.py
```

It checks that `WEATHER_FILE` points at a file that actually exists and has
a `.epw` extension, and prints a clear PASS/FAIL for this step.

## Notes

- The building model (`models/baseline.idf`) is climate-agnostic — it does not
  hardcode a specific city, so any EPW works, though results (baseline energy,
  AI savings %) will naturally differ by climate.
- If you want to compare hot vs. mild climates, just download a second EPW and
  swap the `WEATHER_FILE` value between runs.
