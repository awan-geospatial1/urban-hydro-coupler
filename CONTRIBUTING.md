# Contributing to Urban Hydro-Coupler

Thanks for considering a contribution.

## Setup

```bash
git clone https://github.com/awan-geospatial1/urban-hydro-coupler.git
cd urban-hydro-coupler
pip install -e ".[dev]"
```

## Workflow

1. Create a branch off `develop` (or `main` if `develop` doesn't exist yet).
2. Make your change, with tests for new behavior.
3. Run the test suite and formatter/linter before opening a PR:
   ```bash
   pytest --cov=./ --cov-report=term-missing
   black src tests scripts
   ruff check src tests scripts
   ```
4. Open a pull request against `main` describing what changed and why.
   CI (`.github/workflows/tests.yml`) must pass.

## Code style

- Format with `black` (line length 100).
- Lint with `ruff`.
- Type hints on public functions/methods.
- Docstrings on every public class/function (Google style, as used
  throughout `src/coupler/`).

## Timezone handling

Any code touching timestamps must normalize to UTC — see
`docs/architecture.md` for why. PRs that introduce naive-datetime handling
of Wflow or SWMM timestamps will be asked to fix this before merge.

## Reporting issues

Please include: Python version, OS, the SWMM `.inp` and Wflow CSV you used
(or a minimal repro), and the full traceback.
