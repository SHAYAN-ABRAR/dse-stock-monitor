"""
ai_analyzer.py
--------------
Lightweight AI / anomaly detection on the recent price series.

Three independent detectors, combined into one verdict:
    1. Rule-based  : >X% move (default 2%) between consecutive polls
                     -> "Sudden spike" / "Sudden drop"
    2. Statistical : robust z-score of the latest price vs recent history
    3. Model-based : IsolationForest over the recent window (scikit-learn)

The analyzer is intentionally cheap (<10 ms typical) and is executed on a
worker thread by the scheduler so it can NEVER block scraping or
notifications.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque, List, Optional, Tuple

import numpy as np

from config import AppConfig

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import IsolationForest

    SKLEARN_AVAILABLE = True
except ImportError:  # app still works with rule + statistical detectors
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not installed; IsolationForest disabled.")


@dataclass
class AnalysisResult:
    """Verdict of one analysis pass."""

    is_anomaly: bool = False
    note: str = "Normal"            # e.g. "Sudden spike (+2.4%)"
    pct_change: float = 0.0
    z_score: float = 0.0
    model_flagged: bool = False
    samples: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


class PriceAnalyzer:
    """Maintains a rolling price window and flags abnormal movements."""

    MIN_SAMPLES_FOR_MODEL = 10  # IsolationForest needs some history

    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self._prices: Deque[float] = deque(maxlen=max(10, cfg.ai_history_size))
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def add_and_analyze(self, price: float) -> AnalysisResult:
        """
        Append the new price and analyze the window. Thread-safe and
        exception-proof: any internal error returns a 'Normal' verdict
        rather than propagating into the monitor loop.
        """
        try:
            with self._lock:
                previous = self._prices[-1] if self._prices else None
                self._prices.append(price)
                window: List[float] = list(self._prices)
            return self._analyze(price, previous, window)
        except Exception as exc:
            logger.error("AI analysis failed: %s", exc)
            return AnalysisResult(note=f"AI error: {exc}")

    def get_history(self) -> List[float]:
        with self._lock:
            return list(self._prices)

    # ------------------------------------------------------------------
    def _analyze(self, price: float, previous: Optional[float],
                 window: List[float]) -> AnalysisResult:
        pct_change = 0.0
        if previous and previous > 0:
            pct_change = (price - previous) / previous * 100.0

        z_score = self._robust_z(price, window)
        model_flagged = self._isolation_forest_flag(window)

        # --- combine the three detectors --------------------------------
        threshold = self.cfg.ai_spike_threshold_pct
        notes: List[str] = []

        if pct_change > threshold:
            notes.append(f"Sudden spike (+{pct_change:.2f}% in one interval)")
        elif pct_change < -threshold:
            notes.append(f"Sudden drop ({pct_change:.2f}% in one interval)")

        if abs(z_score) > 3.0 and len(window) >= 5:
            notes.append(f"Statistical outlier (z={z_score:.1f})")

        if model_flagged:
            notes.append("IsolationForest flagged abnormal movement")

        is_anomaly = bool(notes)
        return AnalysisResult(
            is_anomaly=is_anomaly,
            note="; ".join(notes) if notes else "Normal",
            pct_change=pct_change,
            z_score=z_score,
            model_flagged=model_flagged,
            samples=len(window),
        )

    @staticmethod
    def _robust_z(price: float, window: List[float]) -> float:
        """Median/MAD based z-score (robust to the outlier itself)."""
        if len(window) < 5:
            return 0.0
        arr = np.asarray(window, dtype=float)
        median = float(np.median(arr))
        mad = float(np.median(np.abs(arr - median)))
        if mad < 1e-9:
            return 0.0
        return 0.6745 * (price - median) / mad

    def analyze_series(self, prices: List[float]) -> AnalysisResult:
        """
        Stateless analysis of an externally-owned price series (newest last).

        Used by the multi-stock monitor, which keeps one rolling window per
        tracked stock and feeds the recent slice here. Never raises.
        """
        try:
            window = [float(p) for p in prices if p is not None]
            if not window:
                return AnalysisResult(note="No data", samples=0)
            price = window[-1]
            previous = window[-2] if len(window) >= 2 else None
            return self._analyze(price, previous, window)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("analyze_series failed: %s", exc)
            return AnalysisResult(note=f"AI error: {exc}")

    def _isolation_forest_flag(self, window: List[float]) -> bool:
        """True when IsolationForest marks the latest point as an outlier."""
        if not SKLEARN_AVAILABLE or len(window) < self.MIN_SAMPLES_FOR_MODEL:
            return False
        try:
            X = np.asarray(window, dtype=float).reshape(-1, 1)
            model = IsolationForest(
                n_estimators=50, contamination=0.1, random_state=42
            )
            model.fit(X)
            return bool(model.predict(X[-1].reshape(1, -1))[0] == -1)
        except Exception as exc:
            logger.warning("IsolationForest error: %s", exc)
            return False
