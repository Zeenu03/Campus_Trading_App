"""Per-user HTTP client wrapping the Campus Trading REST API.

Uses requests.Session() so the session_id cookie is automatically stored
and replayed on every subsequent request — mirrors how a real browser works.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import requests


class CampusApiClient:
    """Session-aware HTTP client for a single campus trading user."""

    def __init__(self, base_url: str, metrics: Optional[Any] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.metrics = metrics
        self.member_id: Optional[int] = None
        self.email: Optional[str] = None

    # ── Internal ──────────────────────────────────────────────────

    def _req(
        self,
        method: str,
        path: str,
        endpoint: str = "",
        **kwargs: Any,
    ) -> Tuple[bool, int, Dict[str, Any]]:
        """Issue an HTTP request; return (ok, status_code, json_body)."""
        url = f"{self.base_url}{path}"
        t0 = time.monotonic()
        try:
            resp = self.session.request(method, url, timeout=15, **kwargs)
            elapsed = (time.monotonic() - t0) * 1000
            ok = resp.status_code < 400
            if self.metrics and endpoint:
                self.metrics.record(ok, elapsed, endpoint)
            try:
                data = resp.json()
            except Exception:
                data = {}
            return ok, resp.status_code, data
        except requests.RequestException as exc:
            elapsed = (time.monotonic() - t0) * 1000
            if self.metrics and endpoint:
                self.metrics.record(False, elapsed, endpoint)
            return False, 0, {"error": str(exc)}

    # ── Auth ──────────────────────────────────────────────────────

    def register(
        self,
        email: str,
        password: str,
        name: str,
        contact: str = "9876543210",
    ) -> Tuple[bool, Dict[str, Any]]:
        ok, _, data = self._req(
            "POST",
            "/auth/register",
            "register",
            json={
                "email": email,
                "password": password,
                "name": name,
                "contact_number": contact,
                "department": "CSE",
                "year_of_study": 2,
            },
        )
        return ok, data

    def login(self, email: str, password: str) -> Tuple[bool, Dict[str, Any]]:
        ok, _, data = self._req(
            "POST",
            "/auth/login",
            "login",
            json={"email": email, "password": password},
        )
        if ok:
            _, _, me = self._req("GET", "/auth/me")
            self.member_id = me.get("member_id")
            self.email = email
        return ok, data

    def me(self) -> Tuple[bool, Dict[str, Any]]:
        ok, _, data = self._req("GET", "/auth/me", "me")
        return ok, data

    # ── Catalog ───────────────────────────────────────────────────

    def get_categories(self) -> Tuple[bool, List[Dict[str, Any]]]:
        ok, _, data = self._req("GET", "/categories", "get_categories")
        return ok, (data if isinstance(data, list) else [])

    def get_listings(self, page: int = 1, page_size: int = 20) -> Tuple[bool, Any]:
        ok, _, data = self._req(
            "GET", f"/listings?page={page}&page_size={page_size}", "get_listings"
        )
        return ok, data

    def get_listing(self, listing_id: int) -> Tuple[bool, Dict[str, Any]]:
        ok, _, data = self._req("GET", f"/listings/{listing_id}", "get_listing")
        return ok, data

    def create_listing(
        self,
        title: str,
        description: str,
        asking_price: float,
        category_id: int,
        condition: str = "Good",
        is_negotiable: bool = True,
    ) -> Tuple[bool, Dict[str, Any]]:
        ok, _, data = self._req(
            "POST",
            "/listings",
            "create_listing",
            json={
                "category_id": category_id,
                "title": title,
                "description": description,
                "asking_price": asking_price,
                "is_negotiable": is_negotiable,
                "condition": condition,
            },
        )
        return ok, data

    # ── Offers ────────────────────────────────────────────────────

    def submit_offer(
        self, listing_id: int, offered_price: float
    ) -> Tuple[bool, Dict[str, Any]]:
        ok, _, data = self._req(
            "POST",
            f"/listings/{listing_id}/offers",
            "submit_offer",
            json={"offered_price": offered_price},
        )
        return ok, data

    def accept_offer(self, offer_id: int) -> Tuple[bool, Dict[str, Any]]:
        ok, _, data = self._req(
            "PUT", f"/offers/{offer_id}/accept", "accept_offer"
        )
        return ok, data

    def get_offers_for_listing(
        self, listing_id: int
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        ok, _, data = self._req(
            "GET", f"/listings/{listing_id}/offers", "get_offers"
        )
        return ok, (data if isinstance(data, list) else [])

    # ── Notifications & Transactions ─────────────────────────────

    def get_notifications(self) -> Tuple[bool, Any]:
        ok, _, data = self._req("GET", "/notifications", "get_notifications")
        return ok, data

    def get_transactions(self) -> Tuple[bool, Any]:
        ok, _, data = self._req("GET", "/transactions", "get_transactions")
        return ok, data
