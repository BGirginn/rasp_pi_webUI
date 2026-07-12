"""
AdGuard Home client for DNS filtering integration.
"""

import re
from typing import Any, Dict, List, Optional

import httpx

from config import settings


MANAGED_START = "# pi-control-managed-start"
MANAGED_END = "# pi-control-managed-end"
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)(?:[a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,63}$"
)


class AdGuardHomeError(Exception):
    """Raised when AdGuard Home cannot complete the requested operation."""


class AdGuardHomeClient:
    """Small async wrapper around the AdGuard Home control API."""

    def __init__(self) -> None:
        self.base_url = settings.adguard_base_url.rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(settings.adguard_admin_user and settings.adguard_admin_password)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not self.configured:
            raise AdGuardHomeError("AdGuard Home credentials are not configured")

        timeout = httpx.Timeout(5.0, connect=2.0)
        auth = (settings.adguard_admin_user, settings.adguard_admin_password)
        url = f"{self.base_url}/{path.lstrip('/')}"

        try:
            async with httpx.AsyncClient(timeout=timeout, auth=auth) as client:
                response = await client.request(method, url, json=json, params=params)
        except httpx.ConnectError as exc:
            raise AdGuardHomeError("AdGuard Home is not reachable") from exc
        except httpx.RequestError as exc:
            raise AdGuardHomeError(f"AdGuard Home request failed: {exc}") from exc

        if response.status_code == 401:
            raise AdGuardHomeError("AdGuard Home rejected the configured credentials")
        if response.status_code == 404:
            raise AdGuardHomeError("AdGuard Home endpoint was not found")
        if response.status_code >= 400:
            detail = response.text.strip() or response.reason_phrase
            raise AdGuardHomeError(f"AdGuard Home returned {response.status_code}: {detail}")

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    async def status(self) -> Dict[str, Any]:
        if not self.configured:
            return {
                "installed": False,
                "managed": False,
                "error": "AdGuard Home credentials are not configured. Reinstall with --with-adguard or set ADGUARD_ADMIN_USER and ADGUARD_ADMIN_PASSWORD.",
            }

        try:
            status = await self._request("GET", "status")
        except AdGuardHomeError as exc:
            message = str(exc)
            return {
                "installed": "credentials" in message.lower(),
                "managed": False,
                "error": message,
            }

        filtering = await self._optional("GET", "filtering/status")
        safebrowsing = await self._optional("GET", "safebrowsing/status")
        parental = await self._optional("GET", "parental/status")
        querylog = await self._optional("GET", "querylog_info")

        return {
            "installed": True,
            "managed": True,
            "version": status.get("version"),
            "dns_address": "0.0.0.0:53",
            "web_address": "127.0.0.1:3000",
            "protection_enabled": bool(status.get("protection_enabled")),
            "filtering_enabled": bool(filtering.get("enabled", status.get("protection_enabled"))),
            "safebrowsing_enabled": bool(safebrowsing.get("enabled")),
            "parental_enabled": bool(parental.get("enabled")),
            "querylog_enabled": bool(querylog.get("enabled", True)),
            "raw": status,
        }

    async def _optional(self, method: str, path: str) -> Dict[str, Any]:
        try:
            result = await self._request(method, path)
            return result if isinstance(result, dict) else {}
        except AdGuardHomeError:
            return {}

    async def set_protection(self, enabled: bool) -> Dict[str, Any]:
        await self._request("POST", "protection", json={"enabled": enabled})
        return await self.status()

    async def set_safebrowsing(self, enabled: bool) -> Dict[str, bool]:
        await self._request("POST", "safebrowsing/enable" if enabled else "safebrowsing/disable", json={})
        return {"enabled": enabled}

    async def set_parental(self, enabled: bool) -> Dict[str, bool]:
        await self._request("POST", "parental/enable" if enabled else "parental/disable", json={})
        return {"enabled": enabled}

    async def get_rules(self) -> Dict[str, List[str]]:
        data = await self._request("GET", "filtering/status")
        rules = data.get("user_rules") or []
        return _parse_managed_rules(rules)

    async def set_rules(self, blocked_domains: List[str], allowed_domains: List[str]) -> Dict[str, List[str]]:
        blocked = _normalize_domains(blocked_domains)
        allowed = _normalize_domains(allowed_domains)
        data = await self._request("GET", "filtering/status")
        current_rules = data.get("user_rules") or []
        next_rules = _merge_managed_rules(current_rules, blocked, allowed)
        await self._request("POST", "filtering/set_rules", json={"rules": next_rules})
        return {"blocked_domains": blocked, "allowed_domains": allowed}

    async def querylog(self, limit: int = 50, blocked_only: bool = False) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": max(1, min(limit, 200))}
        if blocked_only:
            params["response_status"] = "filtered"
        data = await self._request("GET", "querylog", params=params)
        return {
            "items": data.get("data") or [],
            "oldest": data.get("oldest"),
        }

    async def coverage(self, limit: int = 200) -> Dict[str, Any]:
        data = await self.querylog(limit=limit)
        clients: Dict[str, Dict[str, Any]] = {}
        for item in data.get("items", []):
            client = item.get("client") or item.get("client_id") or "unknown"
            question = item.get("question") or {}
            domain = question.get("name") or item.get("domain") or ""
            blocked = bool(item.get("reason") or item.get("rule") or item.get("filterId"))
            elapsed = item.get("elapsedMs")
            timestamp = item.get("time") or item.get("timestamp") or item.get("date")

            summary = clients.setdefault(client, {
                "client": client,
                "queries": 0,
                "blocked": 0,
                "last_seen": None,
                "sample_domains": [],
            })
            summary["queries"] += 1
            if blocked:
                summary["blocked"] += 1
            if timestamp and not summary["last_seen"]:
                summary["last_seen"] = timestamp
            if domain and domain not in summary["sample_domains"] and len(summary["sample_domains"]) < 5:
                summary["sample_domains"].append(domain)
            if elapsed is not None:
                summary["last_elapsed_ms"] = elapsed

        client_list = sorted(
            clients.values(),
            key=lambda item: (item["queries"], item["blocked"]),
            reverse=True,
        )
        return {
            "clients": client_list,
            "client_count": len(client_list),
            "sample_size": len(data.get("items", [])),
        }

    async def check(self, domain: str) -> Dict[str, Any]:
        normalized = _normalize_domain(domain)
        data = await self._request("GET", "filtering/check_host", params={"name": normalized})
        reason = data.get("reason", "")
        return {
            "domain": normalized,
            "blocked": reason.startswith("Filtered"),
            "reason": reason,
            "rule": data.get("rule") or (data.get("rules") or [{}])[0].get("text"),
            "raw": data,
        }

    async def clear_cache(self) -> Dict[str, bool]:
        await self._request("POST", "cache_clear", json={})
        return {"cleared": True}


def _normalize_domain(domain: str) -> str:
    normalized = domain.strip().lower().rstrip(".")
    if not DOMAIN_RE.match(normalized):
        raise ValueError(f"Invalid domain: {domain}")
    return normalized


def _normalize_domains(domains: List[str]) -> List[str]:
    seen = set()
    normalized = []
    for domain in domains:
        value = _normalize_domain(domain)
        if value not in seen:
            normalized.append(value)
            seen.add(value)
    return normalized


def _parse_managed_rules(rules: List[str]) -> Dict[str, List[str]]:
    managed = False
    blocked: List[str] = []
    allowed: List[str] = []

    for rule in rules:
        if rule == MANAGED_START:
            managed = True
            continue
        if rule == MANAGED_END:
            break
        if not managed:
            continue
        if rule.startswith("@@||") and rule.endswith("^"):
            allowed.append(rule[4:-1])
        elif rule.startswith("||") and rule.endswith("^"):
            blocked.append(rule[2:-1])

    return {"blocked_domains": blocked, "allowed_domains": allowed}


def _merge_managed_rules(current_rules: List[str], blocked: List[str], allowed: List[str]) -> List[str]:
    outside: List[str] = []
    in_managed_block = False

    for rule in current_rules:
        if rule == MANAGED_START:
            in_managed_block = True
            continue
        if rule == MANAGED_END:
            in_managed_block = False
            continue
        if not in_managed_block:
            outside.append(rule)

    managed_rules = [MANAGED_START]
    managed_rules.extend(f"||{domain}^" for domain in blocked)
    managed_rules.extend(f"@@||{domain}^" for domain in allowed)
    managed_rules.append(MANAGED_END)
    return outside + managed_rules


adguard_home_client = AdGuardHomeClient()
