# Trained models

This directory holds trained ML surrogate models produced by
[`scripts/train_surrogate.py`](../scripts/train_surrogate.py), e.g.
`flood_surrogate.joblib`.

These files are generated artifacts (not checked into version control —
see `.gitignore`). Regenerate them with:

```bash
python scripts/train_surrogate.py \
    --swmm data/raw/example_model.inp \
    --node Node1 \
    --n-scenarios 60 \
    --out models/flood_surrogate.joblib
```

The API's `/predict` endpoint and the dashboard's "⚡ Instant AI Risk
Screening" panel both look for `models/flood_surrogate.joblib` by default.
