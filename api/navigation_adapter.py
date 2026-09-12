"""Thin, engine-faithful adapter between the HTTP API and ``IDREngine``.

Each navigation session owns exactly one ``IDREngine`` plus the ML window
buffers that feed it, mirroring the cadence used in offline evaluation
(``src/engine/engine_trip_runner.py``):

* D-T3/D-T4/D-T5 correction window (6-channel [ax, ay, az, gx, gy, gz]) is
  evaluated once per 100 IMU samples and pushed via ``engine.update_ml``.
* The D-T2 speed model (9-channel accel/gyro/mag window owned by the engine)
  is evaluated on the same cadence.
* Vehicle constraints (non-holonomic + ZUPT) are applied per sample exactly
  like ``run_trip`` does.

The adapter never fabricates data: every value in the response comes from the
engine state produced by the fused sensor/GNSS inputs.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from pathlib import Path
from typing import Optional

from src.engine.engine_trip_runner import (
    ML_FEATURE_COLUMNS,
    _IMUWindowBuffer,
    build_engine,
    load_yaml,
)
from src.navigation.engine.idr_engine import IDREngine
from src.navigation.engine.model_interface import (
    FallbackMLInference,
    MLInference,
    TrainedMLInference,
)
from src.navigation.interfaces.messages import (
    GNSSSample,
    IMUSample,
)

logger = logging.getLogger("api.adapter")

#: Engine mode strings that mean "a fix is available right now".
VALID_MODES = frozenset(
    {
        "GNSS_INS_FUSION",
        "GNSS_INS_DEGRADED",
        "RECOVERING",
        "DEAD_RECKONING",
    }
)

#: 6-channel layout consumed by the D-T3/D-T4/D-T5 models.
CORRECTION_COLUMNS = ["accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z"]


def _resolve(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        from api.config import repo_root

        candidate = repo_root() / p
        if candidate.exists():
            return candidate
    return p


def _build_config(
    navigation_config: str,
    fusion_config: str,
    map_matching_config: str,
) -> dict:
    """Fuse the repo config files into the dict shape ``build_engine`` expects."""
    config = load_yaml(_resolve(navigation_config)) or {}
    fusion = load_yaml(_resolve(fusion_config)) or {}
    if "fusion" in fusion:
        config["fusion"] = fusion["fusion"]
    if "fusion" not in config and "filter_type" in fusion:
        config["fusion"] = fusion
    map_cfg = load_yaml(_resolve(map_matching_config)) or {}
    if "map_matching" in map_cfg:
        config["map_matching"] = map_cfg["map_matching"]
    return config


def _sanitised_heading(text_value) -> Optional[float]:
    """Convert a compass bearing (radians) into a finite heading or None."""
    if text_value is None:
        return None
    try:
        value = float(text_value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _degrees_to_radians(degrees) -> Optional[float]:
    if degrees is None:
        return None
    try:
        value = float(degrees)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return math.radians(value)


class NavigationSessionAdapter:
    """One live engine instance plus its ML window buffers."""

    def __init__(
        self,
        session_id: str,
        initial_latitude: float,
        initial_longitude: float,
        initial_accuracy: float = 10.0,
        initial_heading_deg: Optional[float] = None,
        config: Optional[dict] = None,
        ml_inference: Optional[MLInference] = None,
    ) -> None:
        self.session_id = session_id
        self._window_samples = 100

        self._config = config or {}
        self._engine = self._build_engine()
        self._ml_inference = ml_inference if ml_inference is not None else FallbackMLInference()

        # Seed the filter origin so position output is always geo-referenced.
        heading = _degrees_to_radians(initial_heading_deg) or 0.0
        self._engine.initialize(
            float(initial_latitude),
            float(initial_longitude),
            heading,
        )

        # D-T3/D-T4/D-T5 correction window: once per WINDOW_SIZE IMU samples.
        self._correction_buffer = _IMUWindowBuffer(CORRECTION_COLUMNS)
        self._speed_window: deque = deque(maxlen=self._window_samples)

        self._received_gnss = False
        self._last_gnss_timestamp: Optional[float] = None
        self._last_imu_timestamp: Optional[float] = None

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def _build_engine(self) -> IDREngine:
        try:
            self._engine_build_status = "built"
            return build_engine(self._config)
        except Exception as error:  # noqa: BLE001 - surfaced by the route layer
            logger.error("engine build failed for session %s: %s", self.session_id, error)
            self._engine_build_status = f"error: {error}"
            raise

    # ------------------------------------------------------------------ #
    # Runtime
    # ------------------------------------------------------------------ #

    def update(
        self,
        imu_samples: list[IMUSample],
        gnss: Optional[GNSSSample],
    ) -> dict:
        """Feed a batch of IMU samples (+ optional GNSS fix) into the engine.

        Returns the JSON-style engine state dict (see ``get_state_dict``).
        """
        engine = self._engine

        for sample in imu_samples:
            if self._last_imu_timestamp is not None:
                dt = sample.timestamp - self._last_imu_timestamp
                if dt <= 0.0:
                    # Out-of-order or duplicated sample: skip the prediction
                    # but keep sampling for the ML window (harmless, cheap).
                    self._last_imu_timestamp = sample.timestamp
                    self._feed_windows(sample)
                    continue
            self._last_imu_timestamp = sample.timestamp
            engine.update_imu(sample)
            self._feed_windows(sample)

        if gnss is not None:
            engine.update_gnss(gnss)
            self._received_gnss = True
            self._last_gnss_timestamp = gnss.timestamp

        return engine.get_state_dict()

    def state_dict(self) -> dict:
        return self._engine.get_state_dict()

    def close(self) -> None:
        """Best-effort release of model artifacts (idempotent)."""
        try:
            self._engine.reset()
        except Exception as error:  # noqa: BLE001
            logger.warning("engine reset failed for %s: %s", self.session_id, error)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _feed_windows(self, sample: IMUSample) -> None:
        """Push the 6-channel correction window and the 9-channel speed row."""
        correction = {
            "accel_x": sample.accelerometer[0],
            "accel_y": sample.accelerometer[1],
            "accel_z": sample.accelerometer[2],
            "gyro_x": sample.gyroscope[0],
            "gyro_y": sample.gyroscope[1],
            "gyro_z": sample.gyroscope[2],
        }
        self._correction_buffer.push(correction)

        # Cadence: exactly one ML evaluation per WINDOW_SIZE IMU samples —
        # non-overlapping windows, identical to the offline training/eval loop.
        if self._correction_buffer._pushes % self._window_samples == 0:
            window = self._correction_buffer.as_window()
            if window is not None:
                output = self._evaluate_correction(sample.timestamp, window)
                self._engine.update_ml(output)

            # D-T2 speed update: the engine owns the trained speed model
            # (built when ml.enabled), evaluated on the 9-channel window.
            engine_ml = self._engine.ml_inference
            if not isinstance(engine_ml, FallbackMLInference):
                speed_window = self._stack_window(self._speed_window)
                if speed_window is not None:
                    try:
                        output = engine_ml.evaluate(sample.timestamp, speed_window)
                        self._engine.update_ml(output)
                    except Exception as error:  # noqa: BLE001
                        logger.warning("ML speed update failed: %s", error)

        mag = sample.magnetometer
        features: dict[str, float] = {
            "accel_x_cal": sample.accelerometer[0],
            "accel_y_cal": sample.accelerometer[1],
            "accel_z_cal": sample.accelerometer[2],
            "gyro_x_cal": sample.gyroscope[0],
            "gyro_y_cal": sample.gyroscope[1],
            "gyro_z_cal": sample.gyroscope[2],
            "mag_x_cal": float(mag[0]) if mag is not None else 0.0,
            "mag_y_cal": float(mag[1]) if mag is not None else 0.0,
            "mag_z_cal": float(mag[2]) if mag is not None else 0.0,
        }
        row = [features.get(col) or 0.0 for col in ML_FEATURE_COLUMNS]
        self._speed_window.append(row)

    def _evaluate_correction(self, timestamp: float, window) -> object:
        if isinstance(self._ml_inference, FallbackMLInference):
            return self._ml_inference.evaluate(timestamp, window)
        try:
            self._bind_ml_context(self._ml_inference, self._engine)
            return self._ml_inference.evaluate(timestamp, window)
        except Exception as error:  # noqa: BLE001
            logger.warning("correction ML evaluation failed: %s", error)
            return FallbackMLInference().evaluate(timestamp, window)

    @staticmethod
    def _bind_ml_context(ml_inference: MLInference, engine: IDREngine) -> None:
        """Bind live engine state as provider callbacks (mirrors run_trip)."""
        if not hasattr(ml_inference, "bind"):
            return

        def heading_provider():
            return float(engine.state.heading_rad)

        def speed_provider():
            return float(
                math.hypot(
                    engine.state.velocity_east_mps, engine.state.velocity_north_mps
                )
            )

        def gnss_age_provider():
            try:
                return float(engine.fusion.gnss_age(engine.state.timestamp))
            except Exception:  # noqa: BLE001
                return 0.0

        ml_inference.bind(
            heading_provider=heading_provider,
            speed_provider=speed_provider,
            gnss_age_provider=gnss_age_provider,
        )

    @staticmethod
    def _stack_window(window_rows: deque):
        import numpy as np

        rows = list(window_rows)
        if not rows or len(rows) != 100:
            return None
        return np.asarray(rows, dtype=np.float64)[np.newaxis, :, :]

    @property
    def engine(self) -> IDREngine:
        return self._engine

    @property
    def received_gnss(self) -> bool:
        return self._received_gnss

    @property
    def last_gnss_timestamp(self) -> Optional[float]:
        return self._last_gnss_timestamp


def is_valid_mode(mode: str) -> bool:
    return mode in VALID_MODES


def build_ml_inference_for_api(repo_root_dir: Path, model_directory: str) -> MLInference:
    """Build the D-T3/D-T4/D-T5 inference against the given model dir.

    Falls back to ``FallbackMLInference`` when artifacts are missing so the
    API keeps running classically (never crashes because ML is unavailable).
    """
    model_dir = Path(model_directory)
    if model_dir.is_absolute() is False:
        model_dir = repo_root_dir / model_dir

    common = dict(repo_root=repo_root_dir)

    paths = {
        "vibration": model_dir / "vibration_classifier.joblib",
        "imu_correction": model_dir / "imu_correction.joblib",
        "error_model": model_dir / "error_model.joblib",
    }

    if not all(path.exists() for path in paths.values()):
        logger.warning(
            "ML artifacts missing under %s; running classical only.", model_dir
        )
        return FallbackMLInference()

    try:
        inference = TrainedMLInference(
            vibration_path=str(paths["vibration"]),
            imu_correction_path=str(paths["imu_correction"]),
            error_model_path=str(paths["error_model"]),
            **common,
        )
        if inference.available:
            logger.info("TrainedMLInference initialized (D-T3/D-T4/D-T5).")
            return inference
    except Exception as error:  # noqa: BLE001
        logger.warning("TrainedMLInference init failed: %s", error)

    return FallbackMLInference()