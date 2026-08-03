"""Testy providerów cen bez połączeń sieciowych i bez prawdziwych kluczy API."""
from __future__ import annotations

import sqlite3

import pytest

from app import prices
from app.db import SCHEMA


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


@pytest.fixture(autouse=True)
def no_provider_wait(monkeypatch):
    monkeypatch.setattr(prices, "_wait_for_provider", lambda provider: None)
    monkeypatch.setattr(prices.time, "sleep", lambda seconds: None)


def _db(source: str, ticker: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO instruments "
        "(isin, name, ticker, currency, source, active, needs_config) "
        "VALUES ('IE0003XJA0J9', 'Test ETF', ?, 'EUR', ?, 1, 0)",
        (ticker, source),
    )
    return conn


def test_eodhd_fetches_latest_and_history(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "test-eodhd-key")
    calls = []

    def fake_get(url, *, params, timeout):
        calls.append((url, params, timeout))
        assert params["api_token"] == "test-eodhd-key"
        if "/real-time/" in url:
            return FakeResponse({"timestamp": 1785759600, "close": 12.638})
        return FakeResponse([
            {"date": "2026-07-30", "close": 12.478},
            {"date": "2026-07-31", "close": 12.558},
        ])

    monkeypatch.setattr(prices.httpx, "get", fake_get)
    conn = _db("eodhd", "WEBN.XETRA")
    instrument = dict(conn.execute("SELECT * FROM instruments").fetchone())

    assert prices.fetch_history(conn, instrument, "2026-07-30", "2026-08-03") == 2
    assert prices.fetch_latest(conn, instrument) == ("2026-08-03", 12.638)
    rows = conn.execute(
        "SELECT date, price, source FROM prices ORDER BY date"
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("2026-07-30", 12.478, "eodhd"),
        ("2026-07-31", 12.558, "eodhd"),
        ("2026-08-03", 12.638, "eodhd"),
    ]
    assert calls[0][1]["from"] == "2026-07-30"
    assert calls[0][1]["to"] == "2026-08-03"


def test_alpha_vantage_fetches_latest_and_compact_history(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-alpha-key")

    def fake_get(url, *, params, timeout):
        assert url == "https://www.alphavantage.co/query"
        assert params["apikey"] == "test-alpha-key"
        if params["function"] == "GLOBAL_QUOTE":
            return FakeResponse({
                "Global Quote": {
                    "05. price": "41.9200",
                    "07. latest trading day": "2026-07-31",
                }
            })
        return FakeResponse({
            "Time Series (Daily)": {
                "2026-07-31": {"4. close": "41.9200"},
                "2026-07-30": {"4. close": "41.8250"},
                "2026-01-01": {"4. close": "30.0000"},
            }
        })

    monkeypatch.setattr(prices.httpx, "get", fake_get)
    conn = _db("alphavantage", "TSWE.DEX")
    instrument = dict(conn.execute("SELECT * FROM instruments").fetchone())

    assert prices.fetch_history(conn, instrument, "2026-07-30", "2026-08-03") == 2
    assert prices.fetch_latest(conn, instrument) == ("2026-07-31", 41.92)
    assert prices.latest_cached_price(conn, "IE0003XJA0J9") == ("2026-07-31", 41.92)


def test_api_provider_without_key_does_not_call_network(monkeypatch):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    monkeypatch.setattr(
        prices.httpx,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network called")),
    )
    conn = _db("eodhd", "WEBN.XETRA")
    instrument = dict(conn.execute("SELECT * FROM instruments").fetchone())

    assert prices.provider_configured("eodhd") is False
    assert prices.fetch_latest(conn, instrument) is None
    assert prices.fetch_history(conn, instrument, "2026-01-01", "2026-08-03") == 0


def test_automatic_providers_do_not_overwrite_manual_csv(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "test-key")
    monkeypatch.setattr(
        prices.httpx,
        "get",
        lambda *args, **kwargs: FakeResponse([{"date": "2026-07-31", "close": 99.0}]),
    )
    conn = _db("eodhd", "WEBN.XETRA")
    conn.execute(
        "INSERT INTO prices (isin, date, price, source) "
        "VALUES ('IE0003XJA0J9', '2026-07-31', 12.5, 'csv')"
    )
    instrument = dict(conn.execute("SELECT * FROM instruments").fetchone())

    prices.fetch_history(conn, instrument, "2026-07-31", "2026-07-31")

    row = conn.execute(
        "SELECT price, source FROM prices WHERE isin = 'IE0003XJA0J9' AND date = '2026-07-31'"
    ).fetchone()
    assert tuple(row) == (12.5, "csv")


def test_retries_after_rate_limit(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "test-key")
    responses = [
        FakeResponse({}, status_code=429, headers={"Retry-After": "0"}),
        FakeResponse({"timestamp": 1785759600, "close": 12.638}),
    ]
    monkeypatch.setattr(prices.httpx, "get", lambda *args, **kwargs: responses.pop(0))

    assert prices._eodhd_last("WEBN.XETRA") == ("2026-08-03", 12.638, None)
    assert responses == []


def test_alpha_retries_throttle_payload(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    responses = [
        FakeResponse({"Note": "rate limit"}),
        FakeResponse({
            "Global Quote": {
                "05. price": "41.9200",
                "07. latest trading day": "2026-07-31",
            }
        }),
    ]
    monkeypatch.setattr(prices.httpx, "get", lambda *args, **kwargs: responses.pop(0))

    assert prices._alpha_last("TSWE.DEX") == ("2026-07-31", 41.92, None)
    assert responses == []


def test_searches_eodhd_by_isin(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "test-key")
    monkeypatch.setattr(prices.httpx, "get", lambda *args, **kwargs: FakeResponse([{
        "Code": "WEBN", "Exchange": "XETRA", "Name": "Amundi Prime ACWI",
        "Country": "Germany", "Currency": "EUR", "ISIN": "IE0003XJA0J9", "Type": "ETF",
    }]))

    assert prices.search_symbols("eodhd", "IE0003XJA0J9") == [{
        "symbol": "WEBN.XETRA", "name": "Amundi Prime ACWI", "exchange": "XETRA",
        "region": "Germany", "currency": "EUR", "isin": "IE0003XJA0J9", "type": "ETF",
    }]


def test_searches_alpha_by_name(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    monkeypatch.setattr(prices.httpx, "get", lambda *args, **kwargs: FakeResponse({
        "bestMatches": [{
            "1. symbol": "TSWE.DEX", "2. name": "VanEck World Equal Weight",
            "3. type": "ETF", "4. region": "Frankfurt", "8. currency": "EUR",
        }]
    }))

    assert prices.search_symbols("alphavantage", "VanEck World Equal Weight") == [{
        "symbol": "TSWE.DEX", "name": "VanEck World Equal Weight", "exchange": "",
        "region": "Frankfurt", "currency": "EUR", "isin": "", "type": "ETF",
    }]
