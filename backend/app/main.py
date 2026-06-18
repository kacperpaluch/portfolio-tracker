"""FastAPI — API portfolio trackera + serwowanie frontendu."""
from __future__ import annotations

import tempfile
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from . import allocation as allocation_mod
from . import backup as backup_mod
from . import cash as cash_mod
from . import history as history_mod
from . import instruments as instruments_mod
from . import portfolio as portfolio_mod
from . import prices as prices_mod
from . import summary as summary_mod
from . import importer
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


@app.post("/api/prices/import")
async def import_prices_csv(
    isin: str = Form(...),
    file: UploadFile = File(...),
    currency: str | None = Form(None),
) -> dict:
    """Wgrywa dzienne ceny waloru z CSV (format stooq: Data,…,Zamkniecie) do cache.

    Ratunek, gdy provider (Yahoo) nie oddaje poprawnej historii dla danego ISIN —
    np. mało płynny ETN na GPW. `currency` jest wymagana do wyceny (CSV jej nie niesie):
    przekaż ją, albo ustaw wcześniej na instrumencie. Po imporcie „Backfill" nie jest potrzebny.
    """
    content = await file.read()
    with db_session() as conn:
        exists = conn.execute("SELECT 1 FROM instruments WHERE isin = ?", (isin,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Instrument not found")
        try:
            return prices_mod.import_prices(conn, isin, content, currency=currency)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/instruments")
def get_instruments() -> list[dict]:
    with db_session() as conn:
        return instruments_mod.list_instruments(conn)


class InstrumentUpdate(BaseModel):
    ticker: str | None = None
    currency: str | None = None
    source: str | None = None
    category: str | None = None
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
            category=payload.category,
            active=payload.active,
        )
    if updated is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return updated


@app.get("/api/allocation")
def get_allocation() -> dict:
    """Porównanie alokacji docelowej z rzeczywistą (grupy + gotówka)."""
    with db_session() as conn:
        return allocation_mod.compute(conn)


class TargetAllocationIn(BaseModel):
    targets: dict[str, float]


@app.put("/api/allocation")
def put_allocation(payload: TargetAllocationIn) -> dict:
    """Ustawia model docelowy (kategoria -> docelowy %)."""
    with db_session() as conn:
        allocation_mod.set_targets(conn, payload.targets)
        return allocation_mod.compute(conn)


@app.get("/api/portfolio")
def get_portfolio(refresh: bool = False) -> dict:
    with db_session() as conn:
        result = portfolio_mod.value_positions(conn, refresh=refresh)
        totals = result["totals"]
        etf_value = totals["value_pln_partial"]
        portfolio_value = totals.get("portfolio_value_pln") or (etf_value + totals.get("cash_pln", 0))
        totals["xirr"] = history_mod.portfolio_xirr(conn, etf_value, portfolio_value)
        totals["twr"] = history_mod.portfolio_twr(conn)
        totals["returns"] = history_mod.portfolio_returns(conn)
        return result


@app.get("/api/summary")
def get_summary() -> dict:
    """Zwięzły digest portfela (wartość, P/L, zmiana D/D, zwroty, alokacja vs cel).

    Pod powiadomienia/n8n — gotowy „jednym GET-em". Czyta z cache; odpalaj po cronie.
    """
    with db_session() as conn:
        return summary_mod.build(conn)


@app.get("/api/history")
def get_history(benchmark_rate: float = 0.05) -> list[dict]:
    with db_session() as conn:
        return history_mod.portfolio_history(conn, benchmark_rate=benchmark_rate)


@app.get("/api/daily-changes")
def get_daily_changes() -> list[dict]:
    """Dzienna zmiana wartości portfela (zysk/strata D/D, bez wpływu wpłat)."""
    with db_session() as conn:
        return history_mod.portfolio_daily_changes(conn)


@app.get("/api/drawdown")
def get_drawdown() -> dict:
    """Obsunięcie portfela (drawdown) na indeksie TWR: krzywa „pod wodą" + max/bieżące DD."""
    with db_session() as conn:
        return history_mod.portfolio_drawdown(conn)


@app.get("/api/export/daily-changes.csv")
def export_daily_changes_csv() -> Response:
    with db_session() as conn:
        csv_text = backup_mod.daily_changes_csv(conn)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="zmiany-dzienne-{date.today().isoformat()}.csv"'},
    )


@app.post("/api/backfill")
def backfill() -> dict:
    """Pobiera pełną historię cen i kursów NBP od daty pierwszej transakcji."""
    with db_session() as conn:
        return history_mod.backfill_all(conn)


@app.get("/api/export/transactions.csv")
def export_transactions_csv() -> Response:
    with db_session() as conn:
        csv_text = backup_mod.transactions_csv(conn)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="transakcje-{date.today().isoformat()}.csv"'},
    )


@app.get("/api/export/db")
def export_db() -> FileResponse:
    """Pobranie spójnej kopii całej bazy SQLite (do pliku tymczasowego, bez retencji serwerowej)."""
    tmp = Path(tempfile.gettempdir()) / f"portfolio-{date.today().isoformat()}.db"
    backup_mod.backup_database(dest=tmp)
    return FileResponse(tmp, media_type="application/octet-stream", filename=tmp.name)


@app.post("/api/backup-now")
def backup_now() -> dict:
    """Tworzy backup bazy po stronie serwera (do BACKUP_DIR, z retencją)."""
    path = backup_mod.backup_database()
    return {"file": path.name, "dir": str(path.parent), "backups": backup_mod.list_backups()}


@app.get("/api/backups")
def get_backups() -> dict:
    return {"dir": str(backup_mod.BACKUP_DIR), "backups": backup_mod.list_backups()}


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


class TransactionIn(BaseModel):
    ts: str
    isin: str
    name: str | None = None
    type: str  # 'BUY' | 'SELL'
    quantity: float
    price_pln: float
    commission_pln: float = 0.0


@app.post("/api/transactions")
def add_transaction(payload: TransactionIn) -> dict:
    """Dodaje pojedynczą transakcję ręcznie (idempotentnie, jak import)."""
    with db_session() as conn:
        try:
            return importer.add_transaction(
                conn,
                ts=payload.ts,
                isin=payload.isin,
                name=payload.name,
                tx_type=payload.type,
                quantity=payload.quantity,
                price_pln=payload.price_pln,
                commission_pln=payload.commission_pln,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/transactions/{tx_id}")
def delete_transaction(tx_id: int) -> dict:
    with db_session() as conn:
        ok = importer.delete_transaction(conn, tx_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Transakcja nie znaleziona")
    return {"deleted": tx_id}


@app.get("/api/instruments/{isin}/history")
def get_instrument_history(isin: str) -> dict:
    """Dzienna historia waloru: cena natywna, kurs NBP, cena w PLN, posiadana ilość."""
    with db_session() as conn:
        result = history_mod.instrument_history(conn, isin)
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return result


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
    """Odświeża bieżące ceny i kursy FX + dociąga luki w historii (np. po awarii sieci)."""
    with db_session() as conn:
        result = history_mod.refresh_latest(conn)
    return {"updated_prices": result["prices"], "updated_fx": result["fx"],
            "gap_prices": result["gap_prices"], "gap_fx": result["gap_fx"],
            "instruments": result["instruments"]}


# Serwowanie zbudowanego frontendu (jeśli istnieje katalog frontend/dist).
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
