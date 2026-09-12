# HTTP API — Navigation Service

The FastAPI service in `api/` exposes the `IDREngine` (GNSS-INS fusion +
dead reckoning + ML corrections) over HTTP so the mobile app can offload the
online navigation loop to a backend.

## Conventions

| Rule | Detail |
|---|---|
| Base URL | `https://<host>` — see `docs/deployment.md`, or `http://<dev-host>:8000` locally |
| JSON | All fields are `camelCase` (they map 1:1 onto the TypeScript client) |
| Units | timestamps in **epoch seconds**, angles in **degrees** (compass, 0 = North), distances in **meters**, speed in **m/s** |
| Non-finite numbers | `NaN`/`Infinity` are never sent or received. Invalid numeric JSON (e.g. `NaN` in a request) is rejected with `400`; validator failures return `422` with sanitized detail. Every response is JSON-safe by construction |
| IDs | `sessionId` is a 32-hex string generated server-side |

## Modes

The engine reports a `mode` in every `NavigationState`:

| Mode | Meaning |
|---|---|
| `UNINITIALIZED` | No position estimate yet |
| `DEAD_RECKONING` | GNSS unavailable — position from IMU only |
| `GNSS_INS_FUSION` | GNSS + INS fused (healthy) |
| `GNSS_INS_DEGRADED` | Fusion running with reduced trust in GNSS |
| `RECOVERING` | GNSS has just returned; fusion re-locking |

## Endpoints

### `GET /health`

Liveness probe. `200` with `{"status": "ok", "environment": "...", "version": "..."}`.

### `GET /health/models`

`200` with per-model availability (`{"status": "ok", "models": [{"name", "available"}]}`).
A model is `available` when its artifacts exist and load; `false` does not
block sessions (the engine falls back to classical equations of motion).

### `GET /ready`

Readiness — `204` when the app can serve requests.

### `POST /navigation/sessions`

Create a session from the **first known GNSS fix** (an origin is required —
dead reckoning cannot bootstrap itself).

Request:

```json
{
  "latitude": 25.0667,
  "longitude": 55.3,
  "accuracy": 5.0,
  "headingDeg": 90.0,
  "timestamp": 1700000000.0
}
```

Response `201`:

```json
{
  "sessionId": "6279f5ca40af4752b5869c931656a5a2",
  "state": { "timestamp": 1700000000.0, "latitude": 25.0667, "longitude": 55.3, "mode": "DEAD_RECKONING", "...": "see NavigationState" }
}
```

The initial mode is `DEAD_RECKONING` until the first GNSS update arrives.

### `POST /navigation/sessions/{sessionId}/update`

Send one **batch of buffered IMU samples** plus the **most recent GNSS fix**
(single request/response per flush interval, e.g. 1 s).

Request:

```json
{
  "samples": [
    {
      "timestamp": 1700000001.0,
      "accelerometer": { "x": 0.1, "y": 0.2, "z": 9.81 },
      "gyroscope": { "x": 0.0, "y": 0.0, "z": 0.008 },
      "magnetometer": { "x": 12.0, "y": -4.0, "z": 40.0 },
      "headingDeg": 92.0
    }
  ],
  "gnss": { "timestamp": 1700000001.0, "latitude": 25.06671, "longitude": 55.30005, "accuracy": 4.0, "speedMps": 5.0, "headingDeg": 91.0 }
}
```

* `samples` defaults to `[]`. `gnss` is optional; **omit it (or send `null`) during a blackout** — the backend keeps dead-reckoning from IMU alone.
* Do **not** resend a stale GNSS fix; include one only when it is fresh.
* Response `200` is the latest `NavigationState`.
* The engine health monitor flips to `DEAD_RECKONING` once no GNSS fix has arrived for > 3 s.

### `GET /navigation/sessions/{sessionId}`

`200` with the session's latest state. `404` when unknown.

### `DELETE /navigation/sessions/{sessionId}`

Close the session and release engine resources. `204`. `404` when unknown.

## NavigationState

```json
{
  "timestamp": 1700000020.0,
  "latitude": 25.06698,
  "longitude": 55.30084,
  "speedMps": 5.1,
  "headingDeg": 90.4,
  "confidence": 0.82,
  "positionErrorM": 3.9,
  "mode": "DEAD_RECKONING"
}
```

`latitude`/`longitude` are `null` while `UNINITIALIZED`. `confidence` and
`positionErrorM` are `null` when the estimator cannot produce them.

## Errors

All errors are JSON: `{"detail": "..."}`.

| Status | Meaning |
|---|---|
| `400` | Malformed JSON body (e.g. `NaN`) |
| `404` | Unknown `sessionId` |
| `409` | Session limit reached (`MAX_SESSIONS`, 32 default) |
| `422` | Validation error (sanitized, non-finite inputs never echoed) |
| `500` | Unhandled error — body is always the generic `"Internal server error. Please retry."` (no traceback/leaks) |

## Example flow (blackout → recovery)

```
POST /navigation/sessions        # seed with first fix
while streaming:
  POST .../update  {samples, gnss}   # healthy → GNSS_INS_FUSION
  POST .../update  {samples, gnss: null}  # tunnel → DEAD_RECKONING
  POST .../update  {samples, gnss}   # exiting → RECOVERING → GNSS_INS_FUSION
DELETE /navigation/sessions/{id}
```

See the E2E scenario in `tests/api/test_integration_engine.py` and the
TypeScript client `android-app/services/api/navigationApi.ts`.