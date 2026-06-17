# LLM Context — Portfolio Tracker

Dokument referencyjny dla osoby (lub modelu) rozbudowującej projekt. Opisuje stack,
zależności, architekturę, model danych, logikę domenową, konwencje i pułapki oraz
„gdzie co dopisać". Aktualny na commit `afbde8a`.

---

## 1. Czym jest projekt

Self-hostowany tracker portfela ETF dla inwestora kupującego przez polskie biuro
maklerskie (konto IKE). Importuje transakcje z CSV (lub dodaje ręcznie), pobiera wyceny,
przelicza waluty kursem NBP i liczy wartość, P/L (zrealizowany + niezrealizowany),
XIRR/TWR, benchmark, alokację docelową oraz atrybucję zysku (instrument vs waluta).
**Wszystko wyrażone w PLN.** Jeden użytkownik, brak autoryzacji (self-hosted w sieci domowej).

## 2. Stack i technologie

| Warstwa | Technologia | Uwagi |
|---|---|---|
| Język backendu | **Python 3.13** (obraz) / 3.14 (lokalnie) | celowo bez ORM — patrz pułapki |
| Web framework | **FastAPI** + **Uvicorn** | API + serwowanie zbudowanego frontendu |
| Baza | **SQLite** przez wbudowany `sqlite3` | plik, bez serwera; brak zależności ORM |
| Wyceny | **yfinance** (Yahoo Finance) | główne źródło; pokrywa Xetra `.DE`, LSE `.L`, GPW `.WA` |
| Wyceny (alt.) | **stooq** | opcja dla GPW; z IP datacenter bywa blokowany |
| Kursy walut | **NBP API** (api.nbp.pl, tabela A) | darmowe, bez klucza, tylko dni robocze |
| Harmonogram | **APScheduler** (BackgroundScheduler) | dzienne odświeżanie ~21:00 |
| Klient HTTP | **httpx** | zapytania do NBP/stooq |
| Frontend | **React 18** + **Vite 5** + **Recharts 2** | SPA, build serwowany statycznie |
| Konteneryzacja | **Docker** multi-stage, multi-arch (arm64+amd64) | obraz `kpa90/portfolio-tracker` |

## 3. Zależności

### Backend (`backend/requirements.txt`) — bezpośrednie

| Pakiet | Po co |
|---|---|
| `fastapi` | framework API |
| `uvicorn[standard]` | serwer ASGI |
| `python-multipart` | obsługa uploadu pliku (`POST /api/import`) |
| `yfinance` | pobieranie cen instrumentów |
| `httpx` | HTTP do NBP i stooq |
| `apscheduler` | cron dziennego odświeżania |

**Ciężkie zależności tranzytywne:** `yfinance` ciągnie `pandas` + `numpy` (duże). To główny
powód rozmiaru obrazu i czasu builda. Jeśli kiedyś zależy na lekkości — yfinance można by
zastąpić bezpośrednim klientem HTTP do API cen (wtedy pandas/numpy znikają).

### Frontend (`frontend/package.json`)

| Pakiet | Po co |
|---|---|
| `react`, `react-dom` | UI |
| `recharts` | wykresy (Area/Line/Composed) |
| `vite`, `@vitejs/plugin-react` | bundler/dev server |

Brak routera, brak biblioteki stanu — cały stan w `App.jsx` (`useState`). Świadomie proste.

### Usługi zewnętrzne (bez kluczy API)

- **Yahoo Finance** — nieoficjalne, przez `yfinance`. Może się zmienić/zepsuć.
- **NBP** — oficjalne, stabilne, rate-limit łagodny.
- **stooq** — opcjonalne; blokuje IP datacenter (działa z IP domowego).

## 4. Architektura i moduły

```
backend/app/
  main.py        # FastAPI: WSZYSTKIE endpointy, lifespan (start crona), serwowanie frontend/dist
  db.py          # połączenie SQLite, SCHEMA (CREATE IF NOT EXISTS), _migrate(), db_session()
  importer.py    # parse_csv (CP1250), import_transactions, add_transaction, delete_transaction
  instruments.py # ensure_instrument (+ SEED ISIN->ticker), list/update_instrument
  prices.py      # yfinance/stooq: fetch_latest/fetch_history, auto-detekcja waluty (GBx->GBP), cache
  fx.py          # NBP: get_rate (lookback), backfill_range, cache w fx_rates
  cash.py        # księga gotówki: balance/has_external, add/delete flow, record/remove_trade_cash
  portfolio.py   # compute_positions (średni koszt + zrealizowany), value_positions (sumy)
  history.py     # backfill_all, portfolio_history (+benchmark), portfolio_xirr/twr, instrument_history
  returns.py     # czyste funkcje: xirr() (Newton+bisekcja), twr() (łańcuch podokresów)
  allocation.py  # compute (grupy vs cel + rebalans), get/set_targets
  backup.py      # backup_database (online copy + retencja), transactions_csv, list_backups
  scheduler.py   # start_scheduler() — APScheduler: refresh_job (~21:00) + backup_job (~03:00)
frontend/src/
  App.jsx        # cała aplikacja: zakładki, karty, wykresy, tabele, formularze, modal waloru
  api.js         # cienki klient REST (fetch)
  styles.css     # ciemny motyw, bez frameworka CSS
```

### Zależności między modułami (kierunek importów)

```
main.py → importer, instruments, prices, fx, cash, portfolio, history, allocation, scheduler
importer.py → cash, instruments
portfolio.py → cash, fx, prices
history.py → fx, prices, returns
allocation.py → cash, portfolio
backup.py → db
cash.py, fx.py, prices.py, instruments.py, returns.py, db.py → (liście, bez zależności wewn.)
scheduler.py → cash, instruments, prices, fx, db, backup
```

`returns.py` jest czysto funkcyjny (łatwy do testów). `db.py` nie zależy od niczego z app.

## 5. Model danych (SQLite, `db.py:SCHEMA`)

| Tabela | Klucz | Kolumny | Rola |
|---|---|---|---|
| `instruments` | `isin` | name, ticker, currency, source, category, active, needs_config | mapowanie waloru |
| `transactions` | `id` | ts, isin→, type(BUY/SELL), quantity, price_pln, value_pln, commission_pln, **import_hash UNIQUE** | handel |
| `prices` | (isin,date) | price (waluta natywna), source | cache wycen |
| `fx_rates` | (date,currency) | rate_to_pln | cache kursów NBP |
| `cash_flows` | `id` | ts, kind(deposit/withdrawal/buy/sell), amount_pln, note, **import_hash UNIQUE** | księga gotówki |
| `target_allocation` | `category` | weight_pct | model docelowy |

- `import_hash` transakcji = `sha1(ts_iso|isin|type|quantity|price_pln)` → idempotencja importu i ręcznego dodawania.
- `cash_flows.import_hash` dla wpływów z transakcji = `sha1("cash|" + import_hash)` (umożliwia spójne usunięcie).
- Pozycje **nie są materializowane** — liczone w locie z `transactions` (chronologicznie, średni koszt).
- Migracje: `db._migrate()` dodaje brakujące kolumny do istniejących baz (`CREATE IF NOT EXISTS` nie dodaje kolumn). Wzorzec: sprawdź `PRAGMA table_info`, `ALTER TABLE ... ADD COLUMN`.

## 6. Przepływ danych

```
import CSV / ręczna transakcja
   → transactions (+ instruments auto-create) (+ cash_flows buy/sell)
refresh / backfill
   → prices (yfinance/stooq, waluta auto) + fx_rates (NBP)
odczyt
   → portfolio.value_positions  → pozycje, P/L, gotówka, wartość konta
   → history.portfolio_history  → seria wartości + benchmark
   → history.portfolio_xirr/twr → stopy zwrotu
   → allocation.compute         → grupy vs cel
   → history.instrument_history → widok waloru + atrybucja FX
```

## 7. API (wszystkie endpointy w `main.py`)

| Metoda | Ścieżka | Opis |
|---|---|---|
| POST | `/api/import` | import CSV (multipart `file`) |
| GET/POST | `/api/transactions` | lista / ręczne dodanie transakcji |
| DELETE | `/api/transactions/{id}` | usunięcie transakcji (+ przepływ gotówki) |
| GET | `/api/portfolio?refresh=` | pozycje + sumy (P/L, cash, XIRR, TWR) |
| GET | `/api/history?benchmark_rate=` | seria wartości + benchmark |
| GET | `/api/instruments/{isin}/history` | widok waloru (cena natywna/PLN, atrybucja) |
| GET/PUT | `/api/instruments[/{isin}]` | mapowania ISIN→ticker (+ category) |
| GET | `/api/cash` / POST / DELETE `/{id}` | księga gotówki |
| GET/PUT | `/api/allocation` | alokacja docelowa vs rzeczywista |
| POST | `/api/refresh` | bieżące ceny + FX |
| POST | `/api/backfill` | pełna historia cen + FX od pierwszej transakcji |
| GET | `/api/export/transactions.csv` | eksport transakcji (CSV) |
| GET | `/api/export/db` | pobranie spójnej kopii bazy SQLite |
| GET/POST | `/api/backups` / `/api/backup-now` | lista kopii / backup na żądanie |
| GET | `/api/health` | health check |

Swagger: `/docs`.

## 8. Logika domenowa (kluczowe decyzje)

- **Koszt w PLN z importu** — broker rozlicza w PLN, więc cost basis jest wprost; FX dotyczy tylko bieżącej wyceny.
- **P/L łapie instrument + walutę** — `wartość = cena_natywna × ilość × kurs_NBP`, koszt w PLN → różnica zawiera oba efekty.
- **Średni koszt** (nie FIFO). Sprzedaż: `realized += przychód − śr_koszt × ilość`.
- **Auto-detekcja waluty** (`prices._yf_currency`) + normalizacja **GBx/GBp → GBP** (cena/100).
- **NBP lookback** — brak kursu w weekend/święto → ostatni dostępny ≤ data.
- **Gotówka „bramkowana"** — bez żadnej wpłaty saldo = 0 (nie pokazujemy ujemnego z samych zakupów); aktywuje się po pierwszej wpłacie (`cash.has_external`).
- **XIRR** — money-weighted; przepływy = wpłaty/wypłaty (lub fallback transakcje) + wartość końcowa.
- **TWR** — time-weighted; łańcuch dziennych zwrotów z neutralizacją przepływów (konwencja „początek dnia").
- **Benchmark** — money-weighted: każda wpłata oprocentowana stałą stopą od swojej daty (nie płaska linia!).
- **Atrybucja FX** (widok waloru) — `wartość_bez_zmian_kursu = ilość × cena_natywna × kurs_wejścia`; `efekt_waluty = wartość − wartość_bez_zmian_kursu`; `efekt_instrumentu = total − efekt_waluty`.

## 9. Build / uruchomienie / testy

```bash
# Docker (prod)
docker compose up -d                      # http://localhost:8000, dane w named volume portfolio_tracker_data

# Dev backend
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload

# Dev frontend (Vite proxuje /api na :8000)
cd frontend && npm install && npm run dev

# Testy (deterministyczne, bez sieci)
cd backend && .venv/bin/python -m pytest
```

Frontend w produkcji: `npm run build` → `frontend/dist`, serwowany przez FastAPI (mount w `main.py`,
aktywny tylko gdy katalog istnieje). Dockerfile robi to w etapie multi-stage.

## 10. Deployment

- Obraz: `kpa90/portfolio-tracker` na Docker Hub, multi-arch (arm64+amd64).
- **Tagowanie:** `:latest` + `:<git-short-sha>` (backup/rollback). Robi to skill `/ship`.
- **Rollback:** w `docker-compose.yml` podmień `:latest` na `:<sha>` i `docker compose up -d`.
- `docker-compose.yml` używa `image:` (nie `build:`) → **lokalne zmiany testuj budując obraz tym
  samym tagiem** (`docker build -t kpa90/portfolio-tracker:latest .` + `docker compose up -d --force-recreate`)
  albo re-pushuj. `docker compose up --build` nie przebuduje (brak `build:`).

## 11. Konwencje i pułapki (WAŻNE przy rozbudowie)

- **Bez ORM** — celowo `sqlite3` ze stdlib (Python 3.14 miał problemy z kołami niektórych ORM). Trzymaj się surowego SQL + `row_factory = Row`.
- **stooq blokuje IP datacenter** — domyślnym źródłem jest yfinance (pokrywa GPW przez `.WA`). Z IP domowego stooq działa.
- **yfinance jest nieoficjalne** — może się zepsuć; izoluj w `prices.py` za interfejsem provider.
- **GBx (pensy LSE)** — Yahoo zwraca pensy; ZAWSZE normalizuj `/100` + waluta `GBP`.
- **Named volume vs bind mount** — po zmianie na named volume w `/ship` dane z `./data` trzeba zmigrować (`docker cp ./data/portfolio.db <kontener>:/app/data/`).
- **Dedup** — każda nowa ścieżka tworzenia transakcji MUSI używać tego samego `import_hash` co `parse_csv`/`add_transaction`, inaczej powstaną duplikaty.
- **Dane osobiste** — prawdziwe CSV (`*.csv`) są gitignorowane; w repo jest tylko `backend/tests/sample_hisPW.csv` (fikcyjny, z wyjątkiem w `.gitignore`).
- **Cron tylko w produkcji** — scheduler startuje w `lifespan`; pod `TestClient` bez bloku `with` się nie uruchamia. `init_db()` wołane przy imporcie modułu (niezależnie od lifespan).
- **Atrybucja/positions czytają z cache** — bez `backfill`/`refresh` historia i wykresy będą puste.
- **Backupy są w named volume** (`data/backup/` obok bazy) — czyli wewnątrz wolumenu Dockera. Nocny backup (~03:00, `BACKUP_HOUR`) + retencja (`BACKUP_KEEP`, domyślnie 14). Do trzymania kopii poza wolumenem użyj `/api/export/db` albo zbinduj `data/` na host.

## 12. Jak rozbudować — gdzie co dopisać

| Cel | Gdzie |
|---|---|
| Nowy format importu (inny broker) | `importer.py` — nowy parser + auto-detekcja po nagłówku; mapuj do `transactions`+`instruments`+`cash_flows` |
| Nowe źródło cen | `prices.py` — funkcje `_xxx_last/_xxx_hist` + nowa wartość `source` |
| Realny benchmark (indeks zamiast %) | `history.py:portfolio_history` — zamiast `(1+stopa)^lata` użyj serii cen ETF-a z `prices` |
| FIFO / realizowany P/L per lot | `portfolio.compute_positions` — kolejka lotów zamiast średniego kosztu |
| Dywidendy / podatki | nowe `kind` w `cash_flows` + obsługa w imporcie i `cash.balance`; uwzględnij w XIRR |
| Nowe metryki/raporty | endpoint w `main.py` + funkcja w odpowiednim module + karta/zakładka w `App.jsx` |
| Zadanie cykliczne | `scheduler.py` — kolejny `add_job` |
| Eksport danych | endpoint w `main.py` (np. CSV/JSON z `transactions`/`portfolio`) |

Po każdej zmianie: `pytest` (backend) + `npm run build` (frontend) + rebuild obrazu do testu w Dockerze.
