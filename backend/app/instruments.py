"""Obsługa instrumentów: tworzenie z importu, znany seed walut/źródeł, edycja mapowań."""
from __future__ import annotations

import sqlite3

# Seed znanych instrumentów z portfela: ticker (zweryfikowany w yfinance), waluta
# wykryta z notowania i źródło. Waluta i tak jest auto-synchronizowana przy pobraniu
# ceny, a ticker można w każdej chwili zmienić w UI. GPW notowane przez sufiks .WA (PLN).
SEED: dict[str, dict[str, str]] = {
    "IE000716YHJ7": {"ticker": "FWIA.DE", "currency": "EUR", "source": "yfinance"},        # Invesco FTSE All-World
    "IE0003XJA0J9": {"ticker": "WEBN.DE", "currency": "EUR", "source": "yfinance"},        # Amundi Prime All Country World
    "IE00BMW42181": {"ticker": "ESIH.L", "currency": "GBP", "source": "yfinance"},         # iShares MSCI Europe Health Care
    "IE00B43HR379": {"ticker": "IUHC.L", "currency": "USD", "source": "yfinance"},         # iShares S&P 500 Health Care
    "IE00BYZK4669": {"ticker": "AGED.L", "currency": "USD", "source": "yfinance"},         # iShares Ageing Population
    "IE000OEF25S1": {"ticker": "MWEP.L", "currency": "GBP", "source": "yfinance"},         # Invesco MSCI World Equal Weight (GBx)
    "LU0659579147": {"ticker": "XBAK.DE", "currency": "EUR", "source": "yfinance"},        # Xtrackers MSCI Pakistan Swap
    "PLPZUMW00018": {"ticker": "ETFPZUWORLD.WA", "currency": "PLN", "source": "yfinance"}, # ETF PZU World (GPW)
    "SE0024738389": {"ticker": "ETNVCOIN50.WA", "currency": "PLN", "source": "yfinance"},  # ETNVCOIN50 (GPW)
}


def ensure_instrument(conn: sqlite3.Connection, isin: str, name: str) -> None:
    """Tworzy instrument przy pierwszym imporcie, jeśli jeszcze nie istnieje.

    Korzysta z seedu walut/źródeł dla znanych ISIN-ów. needs_config zależy od tego,
    czy znamy ticker (na starcie nie znamy — użytkownik uzupełnia ręcznie).
    """
    row = conn.execute("SELECT isin FROM instruments WHERE isin = ?", (isin,)).fetchone()
    if row is not None:
        return
    seed = SEED.get(isin, {})
    ticker = seed.get("ticker")
    needs_config = 0 if (ticker and seed.get("currency") and seed.get("source")) else 1
    conn.execute(
        """
        INSERT INTO instruments (isin, name, imported_name, ticker, currency, source, active, needs_config)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (isin, name, name, ticker, seed.get("currency"), seed.get("source"), needs_config),
    )


def list_instruments(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM instruments ORDER BY needs_config DESC, name").fetchall()
    return [dict(r) for r in rows]


def update_instrument(
    conn: sqlite3.Connection,
    isin: str,
    *,
    ticker: str | None,
    currency: str | None,
    source: str | None,
    category: str | None = None,
    active: bool | None = None,
    name: str | None = None,
) -> dict | None:
    """Aktualizuje mapowanie instrumentu. needs_config wyłączamy, gdy komplet danych."""
    existing = conn.execute("SELECT * FROM instruments WHERE isin = ?", (isin,)).fetchone()
    if existing is None:
        return None
    name_val = (name or "").strip() or existing["name"]
    ticker = (ticker or "").strip() or None
    currency = (currency or "").strip().upper() or None
    source = (source or "").strip().lower() or None
    category = (category or "").strip() or None
    needs_config = 0 if (ticker and currency and source) else 1
    active_val = existing["active"] if active is None else int(active)
    conn.execute(
        """
        UPDATE instruments
           SET name = ?, ticker = ?, currency = ?, source = ?, category = ?, active = ?, needs_config = ?
         WHERE isin = ?
        """,
        (name_val, ticker, currency, source, category, active_val, needs_config, isin),
    )
    return dict(conn.execute("SELECT * FROM instruments WHERE isin = ?", (isin,)).fetchone())
