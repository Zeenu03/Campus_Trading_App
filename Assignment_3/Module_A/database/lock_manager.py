"""
Lock management scaffolding for Assignment 3 Module A.

Phase 0 keeps this intentionally simple: exclusive locks per resource id.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Set


@dataclass
class TxLockSet:
    """Tracks resources held by a transaction."""

    resources: Set[str] = field(default_factory=set)


class LockManager:
    """Exclusive resource lock manager with transaction ownership tracking."""

    def __init__(self):
        self._global = threading.RLock()
        self._locks: Dict[str, threading.Lock] = {}     # resource_id -> lock
        self._owners: Dict[str, str] = {}                # resource_id -> tx_id
        self._tx_resources: Dict[str, TxLockSet] = defaultdict(TxLockSet) # tx_id -> TxLockSet

    def _resource_lock(self, resource_id: str) -> threading.Lock:
        with self._global:
            if resource_id not in self._locks:
                self._locks[resource_id] = threading.Lock()
            return self._locks[resource_id]

    def acquire(self, tx_id: str, resource_id: str, timeout: float | None = None) -> bool:
        """Acquire exclusive lock for resource under a transaction id."""
        lock = self._resource_lock(resource_id)

        # Re-entrant behavior for same tx owner.
        with self._global:
            if self._owners.get(resource_id) == tx_id:
                self._tx_resources[tx_id].resources.add(resource_id)
                return True

        if timeout is None:
            acquired = lock.acquire()
        else:
            acquired = lock.acquire(timeout=timeout)

        if not acquired:
            return False

        with self._global:
            self._owners[resource_id] = tx_id
            self._tx_resources[tx_id].resources.add(resource_id)
        return True

    def release(self, tx_id: str, resource_id: str) -> None:
        """Release one lock owned by tx_id (no-op if not owner)."""
        with self._global:
            if self._owners.get(resource_id) != tx_id:
                return

            lock = self._locks[resource_id]
            del self._owners[resource_id]
            self._tx_resources[tx_id].resources.discard(resource_id)
            lock.release()

    def release_all(self, tx_id: str) -> None:
        """Release all locks held by tx_id."""
        with self._global:
            resources = list(self._tx_resources[tx_id].resources)

        for resource_id in resources:
            self.release(tx_id, resource_id)

        with self._global:
            self._tx_resources.pop(tx_id, None)
