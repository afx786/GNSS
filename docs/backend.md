# Backend — Navigation HTTP Service

The `api/` package is a stateless, deployable FastAPI service that hosts the
research `IDREngine` behind a small HTTP surface. It follows the same D-*
architecture as the engine and keeps the mobile app thin.

## Layout

```
api/
  __init__.py            package metadata (version)
  config.py              Settings dataclass + repo_root()
  schemas.py             Pydantic request/response models (camelCase, JSON-safe)
  navigation_adapter.py  NavigationSessionAdapter — wraps one IDREngine
  session_manager.py     NavigationSessionManager — lifecycle + concurrency
  dependencies.py        FastAPI dependency providers
  main.py                create_app() factory + global handlers
  routes/
    health.py            /health, /health/models, /ready
    navigation.py        session CRUD + update stream
```

## Session adapter

`NavigationSessionAdapter` owns one `IDREngine` and mimics the exact update
order of the offline trip runner (`src/engine/engine_trip_runner.py`):

* every `update`: `update_imu` → prediction, IMU/gyro windows → constraints
  (`apply_non_holonomic_constraint`, `apply_zupt`) → `update_gnss`
* **every 100th IMU sample** the ML cadence fires, mirroring `run_trip`:
  * **correction path** — a 6-channel `[ax, ay, az, gx, gy, gz]` buffer feeds
    `TrainedMLInference` (`build_ml_inference_for_api`) → `engine.update_ml`
  * **speed path** — a 9-channel calibration window feeds the engine's own
    `ml_inference` (Composite/Speed model), never the fallback, on the same
    cadence

Engine config is merged from `configs/navigation_config.yaml`,
`configs/fusion_config.yaml`, and `configs/map_matching_config.yaml`
(`_build_config`), so the API behaves like the offline runs (EKF, ML enabled,
non-holonomic + ZUPT on). Map matching is effectively off when the road graph
geojson is absent.

## Session manager

`NavigationSessionManager` keeps adapters in memory (no DB):

* thread-safe (`RLock`), session ids are 32-hex (`uuid4().hex`)
* bounded (`MAX_SESSIONS`, default 32) — excess creates → `HTTP 409`
* idle sessions are pruned (configurable `session_idle_timeout_s`, default
  60 s); sessions also self-terminate after `session_max_age_s` (default 24 h)
* `SessionNotFoundError` → `404`

## Safety / robustness

* Responses are JSON-safe by construction — `NavigationStateResponse` builds
  coerce every non-finite float to `null`, and the validation-error handler
  sanitizes offending inputs (a `NaN` timestamp can never reach the wire).
* A custom `RequestValidationError` handler returns `422` with cleaned detail
  (the default handler would crash trying to serialize a `NaN` echoed input).
* Global `Exception` handler logs the traceback server-side but returns a
  fixed generic 500 — nothing leaks to clients.
* Pydantic `extra="ignore"` everywhere: forward-compatible requests.

## Dependencies

Pinned in `requirements.txt` (FastAPI, Uvicorn, Pydantic v2, NumPy/Pandas,
scikit-learn, joblib, PyYAML, PyArrow, PyTorch, XGBoost, SciPy, httpx for
tests). Python 3.13 (`runtime.txt`, Railway Nixpacks).

## Tests

```bash
python -m pytest tests/api -q        # HTTP + engine integration
python -m pytest -q                  # full repo
```

## Mobile integration

`android-app/services/api/navigationApi.ts` is the generated-by-hand,
typized client. `BackendIdrPositionProvider`
(`android-app/services/position/backendPositionProvider.ts`) buffers IMU at
~10 Hz, streams it with the freshest GNSS fix once per second, and re-emits
the server's fused estimate as a `hybrid` fix. When the backend is
unconfigured or unreachable the provider stays `lost` and the hybrid
supervisor rules on GNSS alone — no fabricated positions.