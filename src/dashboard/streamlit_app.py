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

st.divider()
st.caption(
    "Built with PySWMM, Streamlit | "
    "[GitHub Repository](https://github.com/awan-geospatial1/urban-hydro-coupler)"
)
