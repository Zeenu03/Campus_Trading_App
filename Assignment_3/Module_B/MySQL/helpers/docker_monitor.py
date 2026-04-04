"""Background thread that polls `docker stats` and records a CPU/memory time series.

Provides start() / stop() / get_series() / get_peak() API so any scenario
can track container load during its execution window.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from typing import Dict, List, Optional


def _parse_cpu(cpu_str: str) -> float:
    """'12.34%' → 12.34"""
    try:
        return float(cpu_str.replace("%", "").strip())
    except Exception:
        return 0.0


def _parse_mem_mb(mem_str: str) -> float:
    """'210.5MiB / 7.77GiB' → 210.5"""
    try:
        part = mem_str.split("/")[0].strip().upper()
        for suffix, factor in [("GIB", 1024), ("GB", 1024), ("MIB", 1), ("MB", 1), ("KIB", 1/1024), ("KB", 1/1024)]:
            if suffix in part:
                return float(part.replace(suffix, "").strip()) * factor
        return 0.0
    except Exception:
        return 0.0


class DockerMonitor:
    """
    Polls `docker stats <container> --no-stream` every `interval_s` seconds
    in a daemon thread, building a time series of CPU% and memory MB.
    """

    def __init__(
        self, container: str = "campus_a3_mysql", interval_s: float = 1.0
    ) -> None:
        self.container = container
        self.interval_s = interval_s
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._series: List[Dict] = []
        self._lock = threading.Lock()
        self.running = False

    def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        with self._lock:
            self._series.clear()
        self.running = True
        self._thread = threading.Thread(target=self._poll, daemon=True, name="DockerMonitor")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _poll(self) -> None:
        while not self._stop_event.is_set():
            try:
                result = subprocess.run(
                    [
                        "docker", "stats", self.container,
                        "--no-stream",
                        "--format", "{{json .}}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=4,
                )
                if result.returncode == 0 and result.stdout.strip():
                    raw = json.loads(result.stdout.strip())
                    point = {
                        "timestamp": time.time(),
                        "cpu_pct": _parse_cpu(raw.get("CPUPerc", "0%")),
                        "mem_mb": _parse_mem_mb(raw.get("MemUsage", "0MiB")),
                        "container": raw.get("Name", self.container),
                    }
                    with self._lock:
                        self._series.append(point)
            except Exception:
                pass
            time.sleep(self.interval_s)

    def get_series(self) -> List[Dict]:
        with self._lock:
            return list(self._series)

    def get_peak(self) -> Dict:
        series = self.get_series()
        if not series:
            return {"cpu_pct": 0.0, "mem_mb": 0.0, "avg_cpu_pct": 0.0, "avg_mem_mb": 0.0, "samples": 0}
        return {
            "cpu_pct": round(max(p["cpu_pct"] for p in series), 2),
            "mem_mb": round(max(p["mem_mb"] for p in series), 2),
            "avg_cpu_pct": round(sum(p["cpu_pct"] for p in series) / len(series), 2),
            "avg_mem_mb": round(sum(p["mem_mb"] for p in series) / len(series), 2),
            "samples": len(series),
        }
