# Intelligent Dead Reckoning

**AI-ML based Intelligent Dead Reckoning system for seamless navigation**  
**Smart India Hackathon 2024 — Problem Statement 26168**  
**Organization: Indian Space Research Organisation (ISRO)**

---

## Problem Statement

Develop an AI/ML-enhanced Intelligent Dead Reckoning system that transforms a commodity smartphone into a vehicle positioning system capable of maintaining accurate navigation during GNSS-denied environments (tunnels, urban canyons, parking structures, dense foliage) using **only smartphone-generated sensor data**.

---

## Project Objective

Build a production-ready **Intelligent Dead Reckoning Engine (IDREngine)** :

1. Runs entirely on smartphone sensor streams (accelerometer, gyroscope, magnetometer, GNSS)
2. Maintains navigation state during GNSS outages through learned inertial navigation
3. Fuses GNSS and INS optimally when both are available
4. Applies map matching and kinematic constraints for drift correction
5. Exposes a clean interface for Phase 2 mobile application integration

---

## What We Are Building

A **smartphone-only** dead reckoning system with the following pipeline:

```
Smartphone Sensors
       ↓
Preprocessing & Calibration
       ↓
AI/ML Models (Speed, Vibration, IMU Correction, Fusion Correction)
       ↓
Inertial Navigation (Dead Reckoning)
       ↓
GNSS + INS Fusion (EKF/UKF)
       ↓
Map Matching + Non-Holonomic Constraints
       ↓
Final Navigation State (Position / Velocity / Heading + Confidence)
       ↓
Evaluation & Benchmarking
```

---

## Smartphone-Only Constraint

**The runtime system MUST rely ONLY on smartphone-generated data:**

| Sensor | Used at Runtime |
|--------|-----------------|
| Accelerometer | ✅ Yes |
| Gyroscope | ✅ Yes |
| Magnetometer/Compass | ✅ Yes |
| Smartphone GNSS/GPS | ✅ Yes (when available) |
| Sensor timestamps | ✅ Yes |

**The system must NOT require:**
- OBD-II / CAN / ECU data
- Wheel-speed sensors
- Vehicle telemetry
- Vehicle IMU
- Vehicle GPS
- Any physical connection to the vehicle

---

## IO-VNBD Dataset Strategy

The **IO-VNBD dataset** contains both smartphone-side and vehicle-side sensor data. Our strategy:

- **Smartphone data** → Primary input for training and runtime inference
- **Vehicle-side data** → **NEVER** a runtime dependency
- **Vehicle-side/reference data** → Used **offline only** for:
  - Ground truth trajectory generation
  - Model supervision (speed, heading, position labels)
  - Evaluation benchmarks
  - GNSS blackout scenario validation

---

## Core Architecture

```
Smartphone Sensors
       ↓
Data / Preprocessing
       ↓
Calibration & Alignment
       ↓
AI / ML Models
       ↓
Inertial Navigation
       ↓
+------------------+------------------+
|                  |                  |
GNSS Available   GNSS Unavailable   |
|                  |                  |
↓                  ↓                  |
GNSS + INS      Dead Reckoning       |
Fusion             |                  |
|                  |                  |
+------------------+------------------+
       ↓
Map Matching
       ↓
Kinematic Constraints
       ↓
Final Navigation State
       ↓
Position / Velocity / Heading + Confidence
```

---

## System Modes

| Mode | Trigger | Method |
|------|---------|--------|
| **GNSS + INS Fusion** | GNSS available, good quality | EKF/UKF with AI-enhanced measurement models |
| **Dead Reckoning** | GNSS denied / degraded | Pure INS propagated with AI velocity & heading |
| **Map-Matched DR** | GNSS denied + map available | HMM map matching + non-holonomic constraints |
| **Re-localization** | GNSS re-acquired | Smooth state transition with covariance reset |

---

## AI/ML Strategy

Four complementary learned components:

| Model | Purpose | Input | Output |
|-------|---------|-------|--------|
| **Speed Estimator** | Replace wheel-speed sensor | IMU window (accel, gyro) | Vehicle speed (m/s) |
| **Vibration Classifier** | Context awareness | IMU window | Surface/vehicle state class |
| **IMU Error Corrector** | Reduce sensor bias/drift | Raw IMU + context | Corrected IMU measurements |
| **Fusion Corrector** | Improve EKF/UKF innovation | Filter residuals + context | Corrected innovation / covariance |

All models export to **ONNX/TFLite** for on-device inference.

---

## Phase 1 Scope (Current)

✅ **In Scope:**
- Data engineering: IO-VNBD pipeline, smartphone extraction, synchronization
- Preprocessing: cleaning, filtering, resampling, coordinate transforms, calibration
- GNSS blackout simulation & scenario generation
- ML/DL models: speed estimation, vibration classification, IMU correction, fusion correction
- Navigation backend: INS, dead reckoning, EKF/UKF, error-state filter
- GNSS+INS fusion with measurement models
- Map matching: road graph, HMM matcher, non-holonomic constraints
- Confidence/uncertainty estimation
- IDREngine integration interface
- Evaluation framework: metrics, experiments, baselines
- Experiment tracking & documentation

❌ **Out of Scope (Phase 2):**
- Android application
- Mobile UI / map frontend
- Real-time on-device optimization
- Background location services
- Battery optimization
- App store deployment

---

## Phase 2 Scope (Future)

- Android application consuming `IDREngine`
- Mapbox / Google Maps / OSM frontend integration
- Real-time sensor streaming from Android SensorManager
- On-device model inference (TFLite/ONNX Runtime Mobile)
- Background navigation service
- Battery-aware sensor scheduling
- Offline map tile management
- User-facing navigation UI

> **Status:** the mobile app (`android-app/`) exists and already streams
> sensors to the HTTP navigation service (`api/`) — see the *Navigation HTTP
> Service* section. On-device inference and offline tiles remain future work.

---

## Team Ownership

| Member | Ownership | Primary Directories |
|--------|-----------|---------------------|
| **Aaqib** (30%) | Data Engineering, IO-VNBD Pipeline, Preprocessing, Calibration, Simulation, App Part | `data/`, `src/data/`, `src/preprocessing/`, `src/calibration/`, `src/simulation/` |
| **Tanishk** (30%) | ML/DL Models, Training, Evaluation, Export | `src/models/`, `models/` |
| **Shatakshi** (30%) | Navigation Backend, INS, Fusion, Map Matching, IDR Engine | `src/navigation/`, `src/fusion/`, `src/map_matching/`, `src/confidence/`, `src/engine/` |
| **Atharv** (10%) | Research Support, Testing, Integration, Evaluation, Documentation | `tests/`, `evaluation/`, `research/` |

---

## Repository Structure

```
intelligent-dead-reckoning/
├── configs/                 # YAML configuration files
├── data/                    # Dataset pipeline (raw → interim → processed → splits)
├── notebooks/               # Jupyter notebooks for exploration & experiments
├── src/                     # Core Python source code
│   ├── data/                # Dataset loading, smartphone extraction, schema
│   ├── preprocessing/       # Cleaning, filtering, sync, transforms
│   ├── calibration/         # Sensor calibration, phone alignment
│   ├── simulation/          # GNSS blackout, noise injection
│   ├── models/              # ML/DL models (baselines + 4 learned components)
│   ├── navigation/          # INS, dead reckoning, navigation engine
│   ├── fusion/              # EKF, UKF, error-state, GNSS+INS fusion
│   ├── map_matching/        # Road graph, HMM, constraints
│   ├── confidence/          # Uncertainty, drift, confidence scoring
│   ├── engine/              # IDREngine interfaces
│   └── utils/               # Logging, metrics, geo, timestamps, viz
├── models/                  # Model artifacts (checkpoints, exported, metadata)
├── scripts/                 # CLI entry points for pipeline stages
├── evaluation/              # Metrics, experiments, results, plots
├── tests/                   # Unit & integration tests
├── api/                     # FastAPI navigation service (HTTP wrapper over IDREngine)
├── android-app/             # Phase 2 mobile app (Expo) — consumes the HTTP API
├── docs/                    # Technical documentation
├── research/                # Papers, benchmarks, experiments, findings
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── pyproject.toml
├── .env.example
├── railway.toml             # Railway/Nixpacks deploy config
├── Procfile                 # Optional process metadata
└── runtime.txt              # Python 3.13 pin for Railway
```

---

## Navigation HTTP Service

Ships the `IDREngine` as a deployable FastAPI service so the mobile app keeps
the online fusion loop on the backend (sensor streams in, fused
GNSS-INS/dead-reckoned state out).

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
python -m pytest tests/api -q     # HTTP + engine integration tests
```

* `docs/http_api.md` — the HTTP contract (modes, endpoints, error model)
* `docs/backend.md` — architecture (adapter, session manager, ML wiring)
* `docs/deployment.md` — Railway/Nixpacks deployment + env vars
* `android-app/` — Expo client with `navigationApi.ts` + a backend-driven
  position provider that dead-reckons through GNSS blackouts

---

## Development Philosophy

- **Modular, testable, documented** — each component independently verifiable
- **Configuration-driven** — all hyperparameters in YAML, not hardcoded
- **Reproducible** — fixed seeds, versioned data splits, experiment tracking
- **Smartphone-first** — every design decision validated against commodity sensors
- **No vehicle dependency** — vehicle data only for offline supervision/evaluation
- **Phase-gated** — Phase 1 completes the engine; Phase 2 builds the app

---

## Evaluation Strategy

We will systematically compare:

1. **Naive INS** — double integration, no correction
2. **Classical EKF/UKF** — standard GNSS+INS fusion
3. **AI Velocity** — learned speed replaces integration
4. **AI Correction** — learned IMU error correction
5. **AI + Fusion** — learned models inside filter loop
6. **AI + Fusion + Map Matching** — full pipeline with constraints

**Metrics:**
- Position error (RMSE, CEP50, CEP95)
- Drift percentage (per km / per minute)
- Velocity MAE / RMSE
- Heading error (degrees)
- Final displacement error
- Inference latency (ms)
- Model size (MB)
- Update frequency (Hz)

---

## Target Benchmarks

| Scenario | Target Position Error | Target Drift |
|----------|----------------------|--------------|
| Open sky (GNSS) | < 3 m | N/A |
| Urban canyon (partial GNSS) | < 10 m | < 5% |
| Tunnel (60s blackout) | < 15 m | < 10% |
| Extended tunnel (120s) | < 30 m | < 15% |
| Parking structure | < 20 m | < 10% |

---

## Current Project Status

**Engine:** complete and tested — `IDREngine` with GNSS-INS fusion (EKF),
dead reckoning, health/outage state machine, ML corrections (speed + IMU),
non-holonomic/ZUPT constraints, confidence estimation. Full repo test suite
green (`python -m pytest -q`).

**Navigation HTTP Service:** live — `api/` wraps `IDREngine` behind FastAPI
(session CRUD, IMU/GNSS update stream, model health, sanitized errors).
Streams a real GNSS→fusion→blackout→dead-reckoning→recovery cycle end-to-end.

**Mobile app:** initial backend integration shipped — Expo client with
`navigationApi.ts` and a `BackendIdrPositionProvider` that dead-reckons
through GNSS blackouts; mobile jest + tsc pass.

**Next Steps:**
1. Deploy the navigation service (Railway) and set
   `EXPO_PUBLIC_NAVIGATION_API_URL` in the app
2. Field-test the blackout handoff on-device (tunnel/parking)
3. On-device inference (TFLite) and offline tiles

---

## Future Roadmap

| Milestone | Target |
|-----------|--------|
| Data pipeline operational | Week 1-2 |
| Preprocessing + calibration | Week 2-3 |
| Baseline INS + EKF working | Week 3-4 |
| Speed estimation model trained | Week 4-5 |
| IMU correction model trained | Week 5-6 |
| Fusion correction model trained | Week 6-7 |
| Map matching integrated | Week 7-8 |
| Full IDREngine evaluation | Week 8-9 |
| Phase 2 Android app kickoff | Week 10+ |

---

**License:** MIT — see [LICENSE](LICENSE)  
**Contact:** SIH 2024 Team — ISRO PS 26168
