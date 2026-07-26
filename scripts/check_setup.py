#!/usr/bin/env python
"""
Validates that the local environment is ready to run Eco-Loop Building
Agents, and prints clear PASS/FAIL messages for each check.

Usage:
    python scripts/check_setup.py
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"

results: list[tuple[str, bool]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    tag = PASS if ok else FAIL
    print(f"[{tag}] {label}" + (f" - {detail}" if detail else ""))
    results.append((label, ok))


def warn(label: str, detail: str = "") -> None:
    print(f"[{WARN}] {label}" + (f" - {detail}" if detail else ""))


def main() -> int:
    print("=" * 70)
    print("Eco-Loop Building Agents - Environment Check")
    print("=" * 70)

    # 1) Python version
    py_ok = sys.version_info >= (3, 10)
    check("Python version >= 3.10", py_ok, f"found {sys.version.split()[0]}")

    # 2) Required Python packages
    required_packages = [
        "pydantic", "dotenv", "mcp", "streamlit", "pandas", "numpy",
        "plotly", "eppy", "tenacity", "requests", "loguru",
    ]
    for pkg in required_packages:
        try:
            importlib.import_module(pkg)
            check(f"Python package '{pkg}' importable", True)
        except ImportError as exc:
            check(f"Python package '{pkg}' importable", False, str(exc))

    # 3) .env exists
    env_path = settings.paths.project_root / ".env"
    check(".env file exists", env_path.exists(), str(env_path))

    # 4) EnergyPlus installation
    ep_home = settings.energyplus.home
    ep_home_ok = bool(ep_home) and Path(ep_home).exists()
    check("ENERGYPLUS_HOME points to an existing folder", ep_home_ok, ep_home or "(not set)")

    # 5) EnergyPlus Python API importable
    if ep_home_ok:
        sys.path.insert(0, ep_home)
        try:
            import pyenergyplus.api  # type: ignore  # noqa: F401
            check("pyenergyplus (EnergyPlus Python API) importable", True)
        except ImportError as exc:
            check("pyenergyplus (EnergyPlus Python API) importable", False, str(exc))
    else:
        check("pyenergyplus (EnergyPlus Python API) importable", False, "ENERGYPLUS_HOME invalid, skipped")

    # 6) Weather file
    epw_path = settings.resolve(settings.energyplus.weather_file)
    check("Weather file (.epw) found", epw_path.exists(), str(epw_path))
    if not epw_path.exists():
        warn(
            "No .epw file found",
            "Download one for your location from https://energyplus.net/weather "
            "and update WEATHER_FILE in .env",
        )

    # 7) IDF files
    baseline_idf = settings.resolve(settings.energyplus.baseline_idf)
    check("Baseline IDF found", baseline_idf.exists(), str(baseline_idf))

    # 8) LLM connection
    try:
        from app.agent.llm_client import LLMClient
        client = LLMClient()
        llm_ok = client.check_connection()
        check(
            f"LLM reachable ({settings.llm.provider} @ {settings.llm.base_url})",
            llm_ok,
            f"model={settings.llm.model}",
        )
        if not llm_ok:
            warn(
                "LLM not reachable",
                "Start Ollama ('ollama serve') and pull a model "
                f"('ollama pull {settings.llm.model}'), or configure LLM_BASE_URL "
                "for your OpenAI-compatible server.",
            )
    except Exception as exc:  # noqa: BLE001
        check("LLM reachable", False, str(exc))

    # 9) Write permissions
    try:
        test_file = settings.paths.data_dir / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
        check("data/ directory is writable", True)
    except Exception as exc:  # noqa: BLE001
        check("data/ directory is writable", False, str(exc))

    try:
        test_file = settings.paths.log_dir / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
        check("logs/ directory is writable", True)
    except Exception as exc:  # noqa: BLE001
        check("logs/ directory is writable", False, str(exc))

    print("=" * 70)
    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    print(f"Summary: {passed}/{total} checks passed.")
    if passed < total:
        print(
            "Some checks failed. The dashboard and core logic still work "
            "without EnergyPlus/LLM, but running real experiments requires "
            "all checks above to pass. See README.md 'Troubleshooting'."
        )
        return 1
    print("Environment looks good. You can run: python scripts/run_demo.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
