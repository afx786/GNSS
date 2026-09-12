# Deployment

The navigation service deploys as a single Railway service via Nixpacks.
Nothing is persisted (sessions live in memory), so containers are
stateless and can be scaled/replaced freely.

## Railway

1. Create a service from this repo (or push the branch/tag to a connected repo).
2. Build system: **Nixpacks** (set via `railway.toml` — no Nixpacks block
   needed to override; the defaults are fine). Python version comes from
   `runtime.txt` (`3.13`).
3. Start command (already in `railway.toml`):

   ```
   uvicorn api.main:app --host 0.0.0.0 --port $PORT
   ```

   Railway injects `$PORT`; health checks can target `/health` (the 
   `/ready` probe returns `204`).

4. Optional variables — all have safe defaults, so **no env is required**:

   | Variable | Default | Purpose |
   |---|---|---|
   | `NAV_SESSION_IDLE_TIMEOUT_S` | `60` | Prune sessions idle this long |
   | `NAV_SESSION_MAX_AGE_S` | `86400` | Absolute session lifetime |
   | `NAV_MAX_SESSIONS` | `32` | Concurrent session cap (`409` beyond) |

   See `.env.example` (repo root) for the complete list.

5. The build installs from `requirements.txt` (pinned) —
   `pytorch`/`xgboost` wheels are pulled from PyPI on the Nixpacks Linux
   image; model artifacts (`models/`) ship with the repo.

## Local

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Point the app at it with `EXPO_PUBLIC_NAVIGATION_API_URL` in
`android-app/.env` (see `android-app/.env.example`). When testing on a real
phone, use the dev machine's LAN IP, not `localhost`.

## Health-checks

* `GET /health` — `200` + `{"status":"ok","environment","version"}`
* `GET /ready` — `204`
* `GET /health/models` — per-model artifact availability (informational)

## Smoke test

With the server running:

```bash
python tests/api/...    # see tests/api/test_integration_engine.py
```