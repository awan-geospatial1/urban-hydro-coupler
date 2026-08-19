"""Streamlit dashboard for the Urban Hydro-Coupler."""
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Add project root to path for local imports when run via `streamlit run`
sys.path.append(str(Path(__file__).parent.parent.parent))
from src.coupler.core import HydroCoupler  # noqa: E402
from src.ml.surrogate import FloodSurrogateModel  # noqa: E402

SURROGATE_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "flood_surrogate.joblib"

st.set_page_config(page_title="Urban Hydro-Coupler", page_icon="🌊", layout="wide")

st.title("🌊 Urban Hydro-Coupler")
st.markdown(
    """
**Bridge regional hydrology and urban drainage systems.**
Upload a SWMM model and Wflow output to simulate coupled urban flooding.
"""
)

with st.sidebar:
    st.header("⚙️ Configuration")

    swmm_file = st.file_uploader(
        "Upload SWMM Model (.inp)", type=["inp"], help="EPA SWMM input file"
    )
    wflow_file = st.file_uploader(
        "Upload Wflow Output (CSV)",
        type=["csv"],
        help="CSV with 'time' and 'streamflow' columns",
    )
    target_node = st.text_input(
        "Target SWMM Node for Inflow",
        value="Node1",
        help="Node name in your SWMM model to receive the inflow",
    )

    st.divider()

    with st.expander("🔧 Advanced Options"):
        st.checkbox("Interpolate missing Wflow data", value=True, key="interpolate_missing")
        st.checkbox("Clip negative flows to 0", value=True, key="clip_negative")

    run_button = st.button("🚀 Run Coupled Simulation", type="primary", use_container_width=True)

    st.divider()
    st.caption(
        "⚡ **AI Flood Risk Screening** predicts the outcome instantly from "
        "a trained ML surrogate model, without running SWMM. Train one "
        "with `scripts/train_surrogate.py`."
    )
    ml_button = st.button("⚡ Instant AI Risk Screening", use_container_width=True)

if run_button:
    if not swmm_file or not wflow_file:
        st.error("⚠️ Please upload both a SWMM model and a Wflow output file.")
    else:
        with st.spinner("🔄 Running coupled simulation..."):
            swmm_path = wflow_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".inp") as tmp_swmm:
                    tmp_swmm.write(swmm_file.getvalue())
                    swmm_path = Path(tmp_swmm.name)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_wflow:
                    tmp_wflow.write(wflow_file.getvalue())
                    wflow_path = Path(tmp_wflow.name)

                coupler = HydroCoupler(
                    swmm_input_path=swmm_path,
                    wflow_output_path=wflow_path,
                    target_node=target_node,
                )
                results = coupler.run_coupled_simulation()

                st.success("✅ Simulation completed successfully!")

                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("📊 Wflow Inflow Hydrograph")
                    wflow_data = pd.read_csv(wflow_path, parse_dates=["time"])
                    fig = px.line(
                        wflow_data,
                        x="time",
                        y="streamflow",
                        title="Streamflow from Regional Model",
                        labels={"time": "Time", "streamflow": "Flow (cms)"},
                    )
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    st.subheader("📈 Simulation Statistics")
                    st.metric("Simulation Time", f"{results.get('simulation_time', 0):.2f} seconds")
                    st.metric("Target Node", target_node)
                    flooding = results.get("flooding_summary", {})
                    if flooding:
                        st.metric("Max Depth", f"{flooding.get('max_depth', 0):.2f} m")

                with st.expander("📋 Detailed Results"):
                    st.json(
                        {
                            "flooding_summary": results.get("flooding_summary"),
                            "simulation_time": results.get("simulation_time"),
                        }
                    )

            except Exception as exc:
                st.error(f"❌ Simulation failed: {exc}")
                st.exception(exc)
            finally:
                for p in (swmm_path, wflow_path):
                    if p and p.exists():
                        os.unlink(p)

if ml_button:
    if not wflow_file:
        st.error("⚠️ Please upload a Wflow output file to screen.")
    elif not SURROGATE_MODEL_PATH.exists():
        st.warning(
            "⚠️ No trained surrogate model found. Train one first with:\n\n"
            "```\npython scripts/train_surrogate.py --swmm data/raw/example_model.inp "
            "--node Node1\n```"
        )
    else:
        with st.spinner("⚡ Screening scenario with the ML surrogate model..."):
            wflow_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_wflow:
                    tmp_wflow.write(wflow_file.getvalue())
                    wflow_path = Path(tmp_wflow.name)

                wflow_data = pd.read_csv(wflow_path, parse_dates=["time"])
                flow_series = wflow_data.set_index("time")["streamflow"].sort_index()

                model = FloodSurrogateModel.load(SURROGATE_MODEL_PATH)
                prediction = model.predict_from_series(flow_series)

                st.subheader("⚡ AI Flood Risk Screening")
                risk_color = {"low": "🟢", "medium": "🟡", "high": "🔴"}
                risk_level = prediction["risk_level"]

                col1, col2, col3 = st.columns(3)
                col1.metric("Predicted Max Depth", f"{prediction['predicted_max_depth']:.3f} m")
                col2.metric("Risk Level", f"{risk_color.get(risk_level, '')} {risk_level.upper()}")
                col3.metric(
                    "Model Validation R²",
                    f"{model.metrics_.get('r2', float('nan')):.2f}"
                    if model.metrics_
                    else "n/a",
                )
                st.caption(
                    "This is a fast ML approximation, not a physics-based result. "
                    "Confirm important scenarios with '🚀 Run Coupled Simulation' above."
                )
                with st.expander("📋 Hydrograph features used for this prediction"):
                    st.json(prediction["features"])
            except Exception as exc:
                st.error(f"❌ AI screening failed: {exc}")
                st.exception(exc)
            finally:
                if wflow_path and wflow_path.exists():
                    os.unlink(wflow_path)

st.divider()
st.caption(
    "Built with PySWMM, Streamlit | "
    "[GitHub Repository](https://github.com/awan-geospatial1/urban-hydro-coupler)"
)
