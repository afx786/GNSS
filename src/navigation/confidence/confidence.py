"""Confidence estimation (D-S10).

Confidence is derived from the filter's estimated position error and the
navigation mode, and additionally degrades smoothly as a GNSS outage grows
longer (unless map constraints / sensor consistency provide support):

    effective_error = max(position_error, drift_rate * gnss_age)
    effective_error *= (1 - 0.5 * support)
    confidence      = exp(-effective_error / reference_error) * mode_factor

``support`` in [0, 1] captures corroboration from map matching (a recent
successful snap to the road network) or sensor consistency; it slows the
outage degradation but can never raise confidence above the filter-based
value.
"""

from __future__ import annotations

import math


class ConfidenceEstimator:
    def __init__(
        self,
        reference_error_m: float = 10.0,
        drift_rate_mps: float = 0.3,
        minimum: float = 0.0,
        maximum: float = 1.0,
        fusion_factor: float = 1.05,
        dead_reckoning_factor: float = 0.95,
    ):
        self.reference_error_m = float(reference_error_m)
        self.drift_rate_mps = float(drift_rate_mps)
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.fusion_factor = float(fusion_factor)
        self.dead_reckoning_factor = float(dead_reckoning_factor)

    def estimate(
        self,
        position_error_m: float,
        mode: str,
        gnss_age_s: float | None = None,
        support: float = 0.0,
    ) -> float:
        if not math.isfinite(float(position_error_m)):
            return self.minimum

        effective_error = max(float(position_error_m), 0.0)

        # Confidence must degrade with outage duration while in dead
        # reckoning; the linear drift bound is a conservative proxy until the
        # filter covariance (which also grows) can be trusted fully.
        if gnss_age_s is not None and gnss_age_s > 0.0:
            drift_error = self.drift_rate_mps * float(gnss_age_s)
            effective_error = max(effective_error, drift_error)

        # Corroboration (recent map match / consistent sensors) slows the
        # degradation; it never improves on the filter-based value.
        clamped = min(max(float(support), 0.0), 1.0)
        effective_error *= 1.0 - 0.5 * clamped

        confidence = math.exp(
            -effective_error / max(self.reference_error_m, 1e-6)
        )

        if mode == "GNSS_INS_FUSION":
            confidence *= self.fusion_factor
        elif mode == "DEAD_RECKONING":
            confidence *= self.dead_reckoning_factor

        return min(self.maximum, max(self.minimum, confidence))