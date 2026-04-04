"""Thread-safe per-operation latency and outcome tracker."""
from __future__ import annotations

import threading
from typing import Any, Dict, List


class OperationMetrics:
    """
    Records (ok, elapsed_ms, endpoint) tuples from concurrent threads.
    All public methods are thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ops_ok: int = 0
        self._ops_fail: int = 0
        self._latencies_ms: List[float] = []
        self._per_endpoint: Dict[str, List[float]] = {}

    def record(self, ok: bool, elapsed_ms: float, endpoint: str = "default") -> None:
        with self._lock:
            if ok:
                self._ops_ok += 1
            else:
                self._ops_fail += 1
            self._latencies_ms.append(elapsed_ms)
            self._per_endpoint.setdefault(endpoint, []).append(elapsed_ms)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            total = self._ops_ok + self._ops_fail
            lats = list(self._latencies_ms)
            per_ep = {ep: list(v) for ep, v in self._per_endpoint.items()}

        def _stats(lat_list: List[float]) -> Dict[str, float]:
            if not lat_list:
                return {"avg_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0, "min_ms": 0.0}
            s = sorted(lat_list)
            p99_idx = max(0, int(len(s) * 0.99) - 1)
            return {
                "avg_ms": round(sum(s) / len(s), 2),
                "p99_ms": round(s[p99_idx], 2),
                "max_ms": round(s[-1], 2),
                "min_ms": round(s[0], 2),
            }

        return {
            "ops_total": total,
            "ops_ok": self._ops_ok,
            "ops_fail": self._ops_fail,
            "success_rate": round(self._ops_ok / total, 4) if total else 0.0,
            **_stats(lats),
            "per_endpoint": {ep: _stats(v) for ep, v in per_ep.items()},
        }

    def reset(self) -> None:
        with self._lock:
            self._ops_ok = 0
            self._ops_fail = 0
            self._latencies_ms.clear()
            self._per_endpoint.clear()

    @property
    def raw_latencies(self) -> List[float]:
        with self._lock:
            return list(self._latencies_ms)
