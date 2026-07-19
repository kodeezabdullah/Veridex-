"""Unit tests for the bounded Tavily facility cross-check."""

from unittest.mock import Mock

import pytest

import tavily_check


@pytest.fixture(autouse=True)
def clear_tavily_state(monkeypatch):
    tavily_check._clear_process_state()
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    yield
    tavily_check._clear_process_state()


def test_no_results_returns_no_digital_footprint(monkeypatch):
    client = Mock()
    client.search.return_value = {"results": []}
    monkeypatch.setattr(tavily_check, "_create_client", Mock(return_value=client))

    first = tavily_check.check_facility_digital_footprint("Example Hospital", "Pune")
    second = tavily_check.check_facility_digital_footprint("Example Hospital", "Pune")

    assert first == {
        "status": "no_digital_footprint",
        "confidence_adjustment": -0.1,
    }
    assert second == first
    client.search.assert_called_once_with(
        query="Example Hospital Pune hospital",
        max_results=5,
        timeout=10,
    )


def test_new_domain_returns_independent_corroboration(monkeypatch):
    tavily_check.register_facility_source_urls(
        "Example Hospital", "Pune", ["https://examplehospital.org/about"]
    )
    client = Mock()
    client.search.return_value = {
        "results": [{"url": "https://health-news.example/report"}]
    }
    monkeypatch.setattr(tavily_check, "_create_client", Mock(return_value=client))

    result = tavily_check.check_facility_digital_footprint(
        "Example Hospital", "Pune"
    )

    assert result == {
        "status": "independently_corroborated",
        "confidence_adjustment": 0.05,
        "corroborating_url": "https://health-news.example/report",
    }


def test_overlapping_domains_return_no_new_corroboration(monkeypatch):
    tavily_check.register_facility_source_urls(
        "Example Hospital", "Pune", ["https://examplehospital.org/about"]
    )
    client = Mock()
    client.search.return_value = {
        "results": [
            {"url": "https://www.examplehospital.org/icu"},
            {"url": "https://examplehospital.org/contact"},
        ]
    }
    monkeypatch.setattr(tavily_check, "_create_client", Mock(return_value=client))

    result = tavily_check.check_facility_digital_footprint(
        "Example Hospital", "Pune"
    )

    assert result == {
        "status": "no_new_corroboration",
        "confidence_adjustment": 0,
    }


def test_missing_api_key_returns_unavailable(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    client_factory = Mock()
    monkeypatch.setattr(tavily_check, "_create_client", client_factory)

    result = tavily_check.check_facility_digital_footprint(
        "Example Hospital", "Pune"
    )

    assert result == {
        "status": "unavailable",
        "detail": "TAVILY_API_KEY is not configured",
    }
    client_factory.assert_not_called()
