# classifier-training

Trains the transaction category classifier served by `backend-service`'s
`/classify` route and publishes it straight to `backend-service/models/`
(`classifier.joblib` + `label_encoder.joblib`) — the directory `classify.py`
loads from and that the backend Docker image copies in at build time.

Shares the root `.venv` like every other service in this repo.

## Retrain flow

```bash
conda activate /Users/himanshusingh/Developer/budget-tracker/budget_tracker_api/.venv

# 1. Pull the latest prod data snapshot and regenerate db_backup/csv_exports/
python db_backup/restore_latest_backup.py

# 2. First time only
pip install -r classifier-training/requirements.txt

# 3. Retrain — overwrites backend-service/models/*.joblib
python classifier-training/train.py

# 4. Sanity-check predictions locally before shipping
python classifier-training/test.py
```

`train.py` reads `db_backup/csv_exports/budget_tracker.csv`, embeds
descriptions with `sentence-transformers` (`all-MiniLM-L6-v2`), compares a
few scikit-learn classifiers via cross-validation (macro F1), evaluates the
winner on a held-out test set, then refits it on 100% of the data before
saving.

`test.py` loads the freshly saved artifacts using the same code path as
`backend-service/app/routers/classify.py`, so its output reflects exactly
what production will serve.

The running backend-service caches models in-process, so a live server won't
pick up a retrained model until it's restarted/redeployed — use the
`deploy-to-pi` skill (or restart locally) to ship an updated model.
