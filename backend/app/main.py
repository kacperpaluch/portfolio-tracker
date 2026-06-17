"""FastAPI — API portfolio trackera + serwowanie frontendu."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import cash as cash_mod
from . import history as history_mod
from . import instruments as instruments_mod
from . import portfolio as portfolio_mod
from . import prices as prices_mod
from . import fx as fx_mod
from .db import db_session, init_db
from .importer import import_transactions

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start crona dopiero przy realnym uruchomieniu serwera (nie w testach/imporcie modułu).
    from .scheduler import start_scheduler

    scheduler = start_scheduler()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Portfolio Tracker", lifespan=lifespan)

# CORS — pozwala na dev frontendu (Vite) pod innym portem.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicjalizacja schematu przy załadowaniu modułu — niezależna od cyklu lifespan,
# więc działa też pod TestClient bez bloku `with`.
init_db()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/import")
async def import_csv(file: UploadFile = File(...)) -> dict:
    content = await file.read()
    with db_session() as conn:
        return import_transactions(conn, content)


@app.get("/api/instruments")
def get_instruments() -> list[dict]:
    with db_session() as conn:
        return instruments_mod.list_instruments(conn)


class InstrumentUpdate(BaseModel):
    ticker: str | None = None
    currency: str | None = None
    source: str | None = None
    active: bool | None = None


@app.put("/api/instruments/{isin}")
def put_instrument(isin: str, payload: InstrumentUpdate) -> dict:
    with db_session() as conn:
        updated = instruments_mod.update_instrument(
            conn,
            isin,
            ticker=payload.ticker,
            currency=payload.currency,
            source=payload.source,
            active=payload.active,
        )
    if updated is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return updated


@app.get("/api/portfolio")
def get_portfolio(refresh: bool = False) -> dict:
    with db_session() as conn:
        result = portfolio_mod.value_positions(conn, refresh=refresh)
        totals = result["totals"]
        etf_value = totals["value_pln_partial"]
        portfolio_value = totals.get("portfolio_value_pln") or (etf_value + totals.get("cash_pln", 0))
        totals["xirr"] = history_mod.portfolio_xirr(conn, etf_value, portfolio_value)
        totals["twr"] = history_mod.portfolio_twr(conn)
        return result


@app.get("/api/history")
def get_history(benchmark_rate: float = 0.05) -> list[dict]:
    with db_session() as conn:
        return history_mod.portfolio_history(conn, benchmark_rate=benchmark_rate)


@app.post("/api/backfill")
def backfill() -> dict:
    """Pobiera pełną historię cen i kursów NBP od daty pierwszej transakcji."""
    with db_session() as conn:
        return history_mod.backfill_all(conn)


@app.get("/api/transactions")
def get_transactions() -> list[dict]:
    """Historia transakcji (z nazwą instrumentu), od najnowszych."""
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT t.id, t.ts, t.type, t.quantity, t.price_pln, t.value_pln,
                   t.commission_pln, t.isin, i.name, i.ticker
              FROM transactions t
              LEFT JOIN instruments i ON i.isin = t.isin
             ORDER BY t.ts DESC, t.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


@app.get("/api/cash")
def get_cash() -> dict:
    with db_session() as conn:
        return {
            "balance_pln": cash_mod.balance(conn),
            "net_deposits_pln": cash_mod.deposits_total(conn),
            "flows": cash_mod.list_external(conn),
        }


class CashFlowIn(BaseModel):
    ts: str
    kind: str  # 'deposit' | 'withdrawal'
    amount: float
    note: str | None = None


@app.post("/api/cash")
def add_cash(payload: CashFlowIn) -> dict:
    with db_session() as conn:
        try:
            return cash_mod.add_flow(conn, payload.ts, payload.kind, payload.amount, payload.note)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/cash/{flow_id}")
def delete_cash(flow_id: int) -> dict:
    with db_session() as conn:
        ok = cash_mod.delete_flow(conn, flow_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Operacja gotówkowa nie znaleziona")
    return {"deleted": flow_id}


@app.post("/api/refresh")
def refresh_data() -> dict:
    """Odświeża bieżące ceny i kursy FX dla aktywnych, skonfigurowanych instrumentów."""
    with db_session() as conn:
        instruments = [
            i for i in instruments_mod.list_instruments(conn)
            if i["active"] and not i["needs_config"]
        ]
        updated_prices = 0
        for inst in instruments:
            if prices_mod.fetch_latest(conn, inst):
                updated_prices += 1
        currencies = {i["currency"] for i in instruments if i["currency"] and i["currency"] != "PLN"}
        updated_fx = 0
        for cur in currencies:
            try:
                fx_mod.get_rate(conn, cur)
                updated_fx += 1
            except Exception:
                pass
    return {"updated_prices": updated_prices, "updated_fx": updated_fx,
            "instruments": len(instruments)}


# Serwowanie zbudowanego frontendu (jeśli istnieje katalog frontend/dist).
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
