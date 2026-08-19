"""Core coupling logic between a regional hydrological model (Wflow) and SWMM."""
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

try:
    from pyswmm import Nodes, Simulation
except ImportError:  # pragma: no cover - allows import without pyswmm installed
    Simulation = None
    Nodes = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HydroCoupler:
    """Couple a regional hydrological model (e.g. Wflow) output with SWMM.

    Ingests a streamflow time-series from a regional model and injects it as
    a dynamic inflow boundary condition into a SWMM model during simulation.

    Attributes:
        swmm_input_path: Path to the SWMM ``.inp`` file.
        wflow_output_path: Path to the Wflow model output CSV.
        target_node: SWMM node name to apply inflow to.
        wflow_flow: Loaded Wflow streamflow time-series, indexed by UTC time.

    Example:
        >>> coupler = HydroCoupler(
        ...     swmm_input_path=Path("data/raw/urban_model.inp"),
        ...     wflow_output_path=Path("data/processed/wflow_output.csv"),
        ...     target_node="Outfall1"
        ... )
        >>> results = coupler.run_coupled_simulation()
    """

    def __init__(
        self,
        swmm_input_path: Path,
        wflow_output_path: Path,
        target_node: str = "Node1",
    ):
        """Initialize the coupler.

        Args:
            swmm_input_path: Path to the SWMM ``.inp`` file.
            wflow_output_path: Path to the Wflow model output CSV.
            target_node: SWMM node name to apply the inflow to.

        Raises:
            FileNotFoundError: If either input file doesn't exist.
            ValueError: If the Wflow data is invalid.
        """
        self.swmm_input_path = Path(swmm_input_path)
        self.wflow_output_path = Path(wflow_output_path)
        self.target_node = target_node

        self._validate_paths()
        self.wflow_flow = self._load_wflow_flow()

        logger.info("HydroCoupler initialized with target node: %s", target_node)

    def _validate_paths(self) -> None:
        """Ensure input files exist and are readable."""
        if not self.swmm_input_path.exists():
            raise FileNotFoundError(f"SWMM input file not found: {self.swmm_input_path}")
        if not self.wflow_output_path.exists():
            raise FileNotFoundError(f"Wflow output file not found: {self.wflow_output_path}")
        logger.debug("All input paths validated successfully")

    def _load_wflow_flow(self) -> pd.Series:
        """Load and validate the Wflow streamflow time series.

        Critical considerations:
            1. Timezone handling — all times are converted to UTC.
            2. Missing data — gaps are linearly interpolated with a warning.
            3. Negative flows — clipped to zero (physically impossible).

        Returns:
            Time-series of streamflow with a UTC datetime index.

        Raises:
            ValueError: If the file can't be parsed or lacks required columns.
        """
        try:
            df = pd.read_csv(self.wflow_output_path, parse_dates=["time"])
        except Exception as exc:
            raise ValueError(f"Failed to read Wflow output: {exc}") from exc

        if "time" not in df.columns or "streamflow" not in df.columns:
            raise ValueError("Wflow output must have 'time' and 'streamflow' columns")

        if df.empty:
            raise ValueError("Wflow output file is empty")

        # CRITICAL: always normalize to UTC to avoid DST / local-time bugs
        df["time"] = pd.to_datetime(df["time"], utc=True)

        if df["streamflow"].isnull().any():
            null_count = df["streamflow"].isnull().sum()
            logger.warning("Found %d missing values in streamflow; interpolating", null_count)
            df["streamflow"] = df["streamflow"].interpolate(method="linear")

        if (df["streamflow"] < 0).any():
            neg_count = (df["streamflow"] < 0).sum()
            logger.warning("Found %d negative flow values; clipping to 0", neg_count)
            df["streamflow"] = df["streamflow"].clip(lower=0)

        return df.set_index("time")["streamflow"].sort_index()

    def _flow_for_time(self, current_time: datetime) -> float:
        """Get the Wflow flow value for a given simulation time.

        Falls back to the nearest available timestamp if there is no exact
        match, and returns 0.0 if the series is empty or lookup fails.

        Args:
            current_time: The current simulation time.

        Returns:
            Flow value (in the Wflow series' native units) to inject.
        """
        if self.wflow_flow.empty:
            return 0.0

        if current_time in self.wflow_flow.index:
            return float(self.wflow_flow.loc[current_time])

        try:
            idx = self.wflow_flow.index.get_indexer([current_time], method="nearest")[0]
            if idx != -1:
                return float(self.wflow_flow.iloc[idx])
        except Exception:  # pragma: no cover - defensive fallback
            logger.debug("Nearest-time lookup failed for %s", current_time, exc_info=True)

        return 0.0

    def run_coupled_simulation(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Run the coupled simulation: Wflow inflow -> SWMM.

        Loads the SWMM model, iterates through simulation timesteps,
        injects the Wflow flow at each timestep, and extracts results.

        Args:
            start_date: Optional start date override (reserved for future use).
            end_date: Optional end date override (reserved for future use).

        Returns:
            Dict with ``flooding_summary``, ``node_depths``, ``link_flows``,
            and ``simulation_time`` keys.

        Raises:
            RuntimeError: If pyswmm is not installed.
            KeyError: If the target node isn't present in the SWMM model.
        """
        if Simulation is None:
            raise RuntimeError(
                "pyswmm is not installed. Install it with `pip install pyswmm` "
                "to run coupled simulations."
            )

        logger.info("Starting coupled simulation for node: %s", self.target_node)
        results: Dict[str, Any] = {
            "flooding_summary": {},
            "node_depths": {},
            "link_flows": {},
            "simulation_time": None,
        }

        start_time = time.time()

        try:
            with Simulation(str(self.swmm_input_path)) as sim:
                try:
                    node = Nodes(sim)[self.target_node]
                except KeyError as exc:
                    raise KeyError(
                        f"Target node '{self.target_node}' not found in SWMM model"
                    ) from exc

                logger.info("Target node '%s' found", self.target_node)

                depth_series = []
                step_count = 0
                for _ in sim:
                    current_time = sim.current_time
                    step_count += 1

                    inflow_value = self._flow_for_time(current_time)
                    node.inflow(inflow_value)
                    depth_series.append((current_time, node.depth))

                    if step_count % 100 == 0:
                        logger.debug(
                            "Step %d: Time=%s, Inflow=%.2f, Depth=%.2f",
                            step_count,
                            current_time,
                            inflow_value,
                            node.depth,
                        )

                logger.info("Simulation complete. Extracting results...")

                results["node_depths"] = depth_series
                results["flooding_summary"] = {
                    "node": self.target_node,
                    "max_depth": max((d for _, d in depth_series), default=0.0),
                    "steps": step_count,
                    "status": "completed",
                }

        except Exception as exc:
            logger.error("Simulation failed: %s", exc)
            results["error"] = str(exc)
            raise

        results["simulation_time"] = time.time() - start_time
        logger.info("Simulation completed in %.2f seconds", results["simulation_time"])

        return results
