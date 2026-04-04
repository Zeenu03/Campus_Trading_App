"""Shared ScenarioResult dataclass used by all scenario modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ScenarioResult:
    """Holds the outcome of a single stress scenario."""

    name: str
    spec_requirement: str
    passed: bool
    metrics: Dict[str, Any]
    invariants: Dict[str, Any]
    docker_stats_peak: Dict[str, Any] = field(default_factory=dict)
    docker_time_series: list = field(default_factory=list)
    notes: str = ""
