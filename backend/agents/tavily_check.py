"""Bounded Tavily cross-checks for facility digital footprints."""

from __future__ import annotations

import json
import os
from threading import Lock
from typing import Any, Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv


TAVILY_SEARCH_URL = "https://api.tavily.com/search"
SEARCH_TIMEOUT_SECONDS = 10
MAX_RESULTS = 5

_result_cache: dict[tuple[str, str], dict[str, Any]] = {}
_source_urls: dict[tuple[str, str], tuple[str, ...]] = {}
_cache_lock = Lock()

load_dotenv()


def _cache_key(facility_name: str, city: str) -> tuple[str, str]:
    return (facility_name.strip().casefold(), city.strip().casefold())


def register_facility_source_urls(
    facility_name: str,
    city: str,
    source_urls: Iterable[str] | None,
) -> None:
    """Register a facility's known source URLs for independence comparison.

    The registry is process-local. Registering new URLs invalidates any cached
    check for the same facility so the comparison cannot use stale context.
    """
    key = _cache_key(facility_name, city)
    urls = tuple(
        str(url).strip() for url in (source_urls or ()) if str(url).strip()
    )
    with _cache_lock:
        _source_urls[key] = urls
        _result_cache.pop(key, None)


def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").strip().casefold().rstrip(".")
    return host[4:] if host.startswith("www.") else host


class _TavilyHttpClient:
    """Small Tavily REST client used to avoid a hard SDK dependency."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(
        self,
        *,
        query: str,
        max_results: int,
        timeout: int,
    ) -> dict[str, Any]:
        payload = json.dumps(
            {
                "api_key": self._api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
            }
        ).encode("utf-8")
        request = Request(
            TAVILY_SEARCH_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))


def _create_client(api_key: str) -> _TavilyHttpClient:
    return _TavilyHttpClient(api_key)


def _cache_result(key: tuple[str, str], result: dict[str, Any]) -> dict[str, Any]:
    with _cache_lock:
        _result_cache[key] = dict(result)
    return result


def _clear_process_state() -> None:
    """Clear process-local state for isolated tests."""
    with _cache_lock:
        _result_cache.clear()
        _source_urls.clear()


def check_facility_digital_footprint(facility_name: str, city: str) -> dict:
    """Cross-check one facility through Tavily and return a status dictionary.

    Caller gating is mandatory: invoke this utility only when ``capability`` is
    one of ICU, NICU, Trauma, or Oncology *and* ``evidence_status`` is verified
    or likely. This function deliberately does not implement that gate.

    Call :func:`register_facility_source_urls` first when the facility has known
    ``source_urls``. This keeps the required two-argument check API while
    allowing Tavily domains to be compared with the facility's own sources.
    Results are cached by normalized ``(facility_name, city)`` for this process.
    """
    key = _cache_key(facility_name, city)
    with _cache_lock:
        cached = _result_cache.get(key)
        known_urls = _source_urls.get(key, ())
    if cached is not None:
        return dict(cached)

    api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
    if not api_key:
        return {
            "status": "unavailable",
            "detail": "TAVILY_API_KEY is not configured",
        }

    query = f"{facility_name} {city} hospital"
    try:
        response = _create_client(api_key).search(
            query=query,
            max_results=MAX_RESULTS,
            timeout=SEARCH_TIMEOUT_SECONDS,
        )
        results = response.get("results", []) if isinstance(response, dict) else []
        results = results if isinstance(results, list) else []

        if not results:
            return _cache_result(
                key,
                {
                    "status": "no_digital_footprint",
                    "confidence_adjustment": -0.1,
                },
            )

        known_domains = {_domain(url) for url in known_urls if _domain(url)}
        for item in results:
            if not isinstance(item, dict):
                continue
            result_url = str(item.get("url") or "").strip()
            result_domain = _domain(result_url)
            if result_domain and result_domain not in known_domains:
                return _cache_result(
                    key,
                    {
                        "status": "independently_corroborated",
                        "confidence_adjustment": 0.05,
                        "corroborating_url": result_url,
                    },
                )

        return _cache_result(
            key,
            {
                "status": "no_new_corroboration",
                "confidence_adjustment": 0,
            },
        )
    except Exception as error:  # Tavily must never take down the agent.
        return _cache_result(key, {"status": "error", "detail": str(error)})
