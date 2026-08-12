"""Real-time calorie session tracker.

Accumulates per-scan food detections from the live camera feed into a
thread-safe running summary: total kcal, per-food averages, and stability
(ignores transient blips by requiring a detection to be seen N times).
"""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _FoodStat:
    count: int = 0
    total_kcal: float = 0.0
    total_weight: float = 0.0
    total_protein: float = 0.0
    total_fat: float = 0.0
    total_carbs: float = 0.0


@dataclass
class CalorieSessionTracker:
    """Thread-safe accumulator for repeated food scans from the camera."""

    min_confirmations: int = 2
    max_history: int = 30
    _stats: dict[str, _FoodStat] = field(default_factory=dict)
    _seen: Counter = field(default_factory=Counter)
    _history: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add_scan(self, detections: list[dict[str, Any]]) -> None:
        """Feed one scan's detections into the session summary."""
        with self._lock:
            self._history.append(detections)
            if len(self._history) > self.max_history:
                self._history.pop(0)

            for det in detections:
                name = str(det.get("food_type", det.get("name", "unknown")))
                kcal = float(det.get("estimated_kcal", det.get("estimated_calories", 0)) or 0)
                weight = float(det.get("estimated_weight_grams", 0) or 0)
                macros = det.get("estimated_macros", {}) or {}
                stat = self._stats.setdefault(name, _FoodStat())
                stat.count += 1
                stat.total_kcal += kcal
                stat.total_weight += weight
                stat.total_protein += float(macros.get("protein", 0) or 0)
                stat.total_fat += float(macros.get("fat", 0) or 0)
                stat.total_carbs += float(macros.get("carbs", 0) or 0)
                self._seen[name] += 1

    def summary(self) -> dict[str, Any]:
        """Averaged, confirmation-filtered summary of the session."""
        with self._lock:
            confirmed = {
                name: stat
                for name, stat in self._stats.items()
                if self._seen[name] >= self.min_confirmations
            }
            total_kcal = sum(stat.total_kcal for stat in confirmed.values())
            total_weight = sum(stat.total_weight for stat in confirmed.values())
            foods = [
                {
                    "food_type": name,
                    "scans": stat.count,
                    "avg_kcal": round(stat.total_kcal / stat.count, 1),
                    "avg_weight_grams": round(stat.total_weight / stat.count, 1),
                    "avg_macros": {
                        "protein": round(stat.total_protein / stat.count, 1),
                        "fat": round(stat.total_fat / stat.count, 1),
                        "carbs": round(stat.total_carbs / stat.count, 1),
                    },
                }
                for name, stat in sorted(confirmed.items(), key=lambda kv: kv[1].total_kcal, reverse=True)
            ]
            return {
                "total_kcal": round(total_kcal, 1),
                "total_weight_grams": round(total_weight, 1),
                "foods": foods,
                "scans_total": len(self._history),
            }

    def reset(self) -> None:
        """Clear session data."""
        with self._lock:
            self._stats.clear()
            self._seen.clear()
            self._history.clear()
