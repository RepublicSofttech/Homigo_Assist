"""Thin client for the Homigo main API.

The assistant always acts *as the signed-in user* by forwarding their own token, so Homigo's
own permission rules (customer sees only their bookings, partner only their business, ...) apply.
"""
import hashlib
import logging

import requests
from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)


class HomigoError(Exception):
    def __init__(self, message, status=400, code="ERROR", data=None):
        super().__init__(message)
        self.message, self.status, self.code, self.data = message, status, code, data or {}


class HomigoClient:
    def __init__(self, token=None):
        self.token = token or None
        self.base = settings.HOMIGO_API_URL

    # ---- low level ----
    def _request(self, method, path, params=None, json=None):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Token {self.token}"
        try:
            r = requests.request(method, f"{self.base}{path}", params=params, json=json, headers=headers, timeout=settings.HOMIGO_TIMEOUT)
        except requests.RequestException as e:
            log.warning("Homigo API unreachable: %s", e)
            raise HomigoError("Homigo service is not reachable right now.", 503, "UPSTREAM_DOWN")
        if r.status_code >= 400:
            try:
                body = r.json()
            except ValueError:
                body = {}
            msg = body.get("message") or body.get("detail") or "Request failed."
            if body.get("field_errors"):
                msg += " " + "; ".join(f"{k}: {', '.join(map(str, v)) if isinstance(v, list) else v}" for k, v in body["field_errors"].items())
            raise HomigoError(msg, r.status_code, body.get("code", "ERROR"), body)
        if r.status_code == 204 or not r.content:
            return {}
        return r.json()

    def get(self, path, **params):
        return self._request("GET", path, params={k: v for k, v in params.items() if v not in (None, "")})

    def post(self, path, data=None):
        return self._request("POST", path, json=data or {})

    def patch(self, path, data=None):
        return self._request("PATCH", path, json=data or {})

    @staticmethod
    def results(data):
        return data.get("results", data) if isinstance(data, dict) else data

    # ---- identity ----
    def me(self):
        """Returns the Homigo user for this token (cached 5 min), or None for guests / invalid tokens."""
        if not self.token:
            return None
        key = "me:" + hashlib.sha256(self.token.encode()).hexdigest()
        cached = cache.get(key)
        if cached is not None:
            return cached or None
        try:
            user = self.get("/me/")
        except HomigoError as e:
            if e.status in (401, 403):
                cache.set(key, {}, 60)
                return None
            raise
        cache.set(key, user, 300)
        return user


def role_of(user):
    if not user:
        return "guest"
    t = user.get("user_type") or "customer"
    return "admin" if t == "admin" or user.get("admin_role") else t
