"""Thin wrapper around PySWMM execution for reuse outside HydroCoupler.

Kept separate from ``core.py`` so the API and CLI layers can run a plain
SWMM simulation (no coupling) when they just need a quick model check.
"""
import logging
from pathlib import Path
from typing import Any, Dict

try:
    from pyswmm import Output, Simulation
except ImportError:  # pragma: no cover
    Simulation = None
    Output = None

logger = logging.getLogger(__name__)


def run_plain_simulation(swmm_input_path: Path) -> Dict[str, Any]:
    """Run a SWMM simulation with no external inflow injection.

    Useful as a sanity check that a ``.inp`` file is valid before handing it
    to :class:`~src.coupler.core.HydroCoupler`.

    Args:
        swmm_input_path: Path to the SWMM ``.inp`` file.

    Returns:
        Dict with ``steps`` (number of timesteps executed) and ``status``.

    Raises:
        RuntimeError: If pyswmm is not installed.
        FileNotFoundError: If the input file doesn't exist.
    """
    if Simulation is None:
        raise RuntimeError("pyswmm is not installed. Install it with `pip install pyswmm`.")

    swmm_input_path = Path(swmm_input_path)
    if not swmm_input_path.exists():
        raise FileNotFoundError(f"SWMM input file not found: {swmm_input_path}")

    step_count = 0
    with Simulation(str(swmm_input_path)) as sim:
        for _ in sim:
            step_count += 1

    logger.info("Plain simulation completed: %d steps", step_count)
    return {"steps": step_count, "status": "completed"}


def extract_binary_results(swmm_input_path: Path) -> Dict[str, Any]:
    """Extract summary results from a SWMM run's binary ``.out`` file.

    Assumes the ``.out`` file sits alongside the ``.inp`` file with the same
    stem (SWMM's default behavior).

    Args:
        swmm_input_path: Path to the SWMM ``.inp`` file that was simulated.

    Returns:
        Dict of extracted series/metadata. Empty if the ``.out`` file is
        missing or pyswmm's Output API isn't available.
    """
    if Output is None:
        raise RuntimeError("pyswmm is not installed. Install it with `pip install pyswmm`.")

    out_path = Path(swmm_input_path).with_suffix(".out")
    if not out_path.exists():
        logger.warning("No .out file found at %s", out_path)
        return {}

    results: Dict[str, Any] = {}
    with Output(str(out_path)) as out:
        results["nodes"] = list(out.nodes)
        results["links"] = list(out.links)
        results["start"] = str(out.start)
        results["end"] = str(out.end)

    return results
