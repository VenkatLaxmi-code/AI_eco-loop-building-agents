"""
Application entry point / shared logging configuration.

Most users will interact with this project through the scripts/ folder
(check_setup.py, run_baseline.py, run_ai.py, compare_results.py,
run_demo.py) rather than this module directly, but `python -m app.main`
runs the full baseline -> AI -> comparison pipeline in one process.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.config import settings


def configure_logging() -> None:
    settings.paths.log_dir.mkdir(parents=True, exist_ok=True)
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    root = logging.getLogger()
    root.setLevel(settings.log_level)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(log_format))
    root.addHandler(console)

    handlers = {
        "simulation": settings.paths.log_dir / "simulation.log",
        "agent": settings.paths.log_dir / "agent.log",
        "mcp": settings.paths.log_dir / "mcp.log",
        "errors": settings.paths.log_dir / "errors.log",
    }
    for logger_name, path in handlers.items():
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setFormatter(logging.Formatter(log_format))
        if logger_name == "errors":
            fh.setLevel(logging.ERROR)
            root.addHandler(fh)
        else:
            fh.setLevel(logging.DEBUG)
            logging.getLogger(logger_name).addHandler(fh)
            logging.getLogger(f"{logger_name}_alias").addHandler(fh)

    # Route module loggers into the right files by name prefix.
    logging.getLogger("energyplus_runner").addHandler(
        logging.FileHandler(handlers["simulation"], encoding="utf-8")
    )
    logging.getLogger("building_agent").addHandler(
        logging.FileHandler(handlers["agent"], encoding="utf-8")
    )
    logging.getLogger("mcp.tools").addHandler(
        logging.FileHandler(handlers["mcp"], encoding="utf-8")
    )
    logging.getLogger("mcp.server").addHandler(
        logging.FileHandler(handlers["mcp"], encoding="utf-8")
    )


def main() -> None:
    configure_logging()
    from app.control.closed_loop import run_ai_experiment, run_baseline_experiment
    from app.analytics.comparison import compare

    logging.info("Running baseline experiment...")
    run_baseline_experiment()

    logging.info("Running AI-controlled experiment...")
    run_ai_experiment()

    logging.info("Comparing results...")
    metrics = compare()
    logging.info("Final metrics: %s", metrics)


if __name__ == "__main__":
    main()
