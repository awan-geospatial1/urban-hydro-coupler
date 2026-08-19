"""Tests for src.coupler.model_runner.

These skip automatically if pyswmm isn't installed, so the suite stays
runnable in lightweight environments (e.g. CI without the SWMM engine).
"""
from pathlib import Path

import pytest

pyswmm = pytest.importorskip("pyswmm")

from src.coupler.model_runner import extract_binary_results, run_plain_simulation  # noqa: E402


def test_run_plain_simulation_missing_file_raises(tmp_path: Path):
    """A missing .inp file should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        run_plain_simulation(tmp_path / "missing.inp")


def test_run_plain_simulation_executes(sample_swmm_path: Path):
    """The bundled sample model should run and report completed status."""
    result = run_plain_simulation(sample_swmm_path)
    assert result["status"] == "completed"
    assert result["steps"] > 0


def test_extract_binary_results_missing_out_file_returns_empty(tmp_path: Path):
    """No .out file alongside the .inp should return an empty dict, not raise."""
    fake_inp = tmp_path / "model.inp"
    fake_inp.write_text("[TITLE]\n")
    assert extract_binary_results(fake_inp) == {}
