from __future__ import annotations

import sqlite3

from app.analytics import build
from app.db import SCHEMA


def test_analytics_attributes_open_profit():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO instruments "
        "(isin, name, ticker, currency, source, category, active, needs_config) "
        "VALUES ('A', 'ETF A', 'A.WA', 'PLN', 'test', 'Akcje', 1, 0)"
    )
    conn.execute(
        "INSERT INTO transactions "
        "(ts, isin, type, quantity, price_pln, value_pln, commission_pln, import_hash) "
        "VALUES ('2026-01-01T10:00:00', 'A', 'BUY', 10, 100, 1000, 5, 'h1')"
    )
    conn.execute(
        "INSERT INTO prices (isin, date, price, source) VALUES ('A', '2026-07-31', 120, 'test')"
    )
    conn.commit()

    result = build(conn)
    assert result["instruments"][0]["total_pl_pln"] == 200
    assert result["categories"][0]["category"] == "Akcje"
    assert result["categories"][0]["total_pl_pln"] == 200
    assert result["activity"]["commissions_pln"] == 5
