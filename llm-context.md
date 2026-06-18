# LLM Context — Portfolio Tracker

Dokument referencyjny dla osoby (lub modelu) rozbudowującej projekt. Opisuje stack,
zależności, architekturę, model danych, logikę domenową, konwencje i pułapki oraz
„gdzie co dopisać". Opisuje stan z gałęzi `main` — przy rozbieżności źródłem prawdy
jest kod (`backend/app/`), nie ten dokument.

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
| Wyceny (ratunek) | **import CSV** | dla papierów bez pokrycia w yfinance (niszowy GPW); stooq jako live-source martwy (PoW) |
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

Brak routera, brak biblioteki stanu — cały stan trzyma `App.jsx` (`useState`) i schodzi propsami
do komponentów w `components/`. Świadomie proste. Helpery formatujące współdzielone przez `format.js`.

### Usługi zewnętrzne (bez kluczy API)

- **Yahoo Finance** — nieoficjalne, przez `yfinance`. Może się zmienić/zepsuć.
- **NBP** — oficjalne, stabilne, rate-limit łagodny.
- **stooq** — martwe jako źródło: JS proof-of-work blokuje klientów bez JS nawet z domowego IP (usunięte z UI; szkielet kodu zostaje). Format eksportu CSV ze stooq jest nadal wejściem dla importu cen.

## 4. Architektura i moduły

```
backend/app/
  main.py        # FastAPI: WSZYSTKIE endpointy, lifespan (start crona), serwowanie frontend/dist
  db.py          # połączenie SQLite, SCHEMA (CREATE IF NOT EXISTS), _migrate(), db_session()
  importer.py    # parse_csv (CP1250), import_transactions, add_transaction, delete_transaction
  instruments.py # ensure_instrument (+ SEED ISIN->ticker), list/update_instrument
  prices.py      # yfinance/stooq: fetch_latest/fetch_history, auto-detekcja waluty (GBx->GBP), cache; parse_price_csv/import_prices (import cen z CSV stooq)
  fx.py          # NBP: get_rate (lookback), backfill_range, cache w fx_rates
  cash.py        # księga gotówki: balance/has_external, add/delete flow, record/remove_trade_cash
  portfolio.py   # compute_positions (średni koszt + zrealizowany), value_positions (sumy)
  history.py     # refresh_latest (bieżące+luki), backfill_all, portfolio_history (+benchmark), portfolio_xirr/twr, instrument_history
  returns.py     # czyste funkcje: xirr() (Newton+bisekcja), twr() (łańcuch podokresów)
  allocation.py  # compute (grupy vs cel + rebalans), get/set_targets
  summary.py     # build() — digest pod powiadomienia (kompozycja portfolio+history+allocation)
  backup.py      # backup_database (online copy + retencja), transactions_csv, list_backups
  scheduler.py   # start_scheduler() — APScheduler: refresh_job (~21:00, woła history.refresh_latest) + backup_job (~03:00)
frontend/src/
  App.jsx        # orkiestracja: stan (useState), loadAll (Promise.all), run(), handlery, layout zakładek
  components/    # jeden komponent = jeden plik: Cards, ReturnsStrip, HistoryChart, InstrumentDetail,
                 #   PositionsTable, TransactionForm, TransactionsTable, CashPanel, InstrumentsPanel,
                 #   AllocationPanel, DataPanel, BackupModal, DailyChangesTable
  format.js      # wspólne helpery: fmtPln, fmtPct, cls, fmtDate
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
summary.py → portfolio, history, allocation
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
| POST | `/api/import` | import CSV transakcji (multipart `file`) |
| POST | `/api/prices/import` | import dziennych cen waloru z CSV (multipart `isin`+`file`+opcjonalnie `currency`, format stooq) → cache `prices` (`prices.import_prices`); waluta wymagana do wyceny |
| GET/POST | `/api/transactions` | lista / ręczne dodanie transakcji |
| DELETE | `/api/transactions/{id}` | usunięcie transakcji (+ przepływ gotówki) |
| GET | `/api/portfolio?refresh=` | pozycje + sumy (P/L, cash, XIRR, TWR, `returns` 1M/3M/YTD/1R/all) |
| GET | `/api/summary` | digest pod powiadomienia/n8n: konto, P/L, zmiana D/D, zwroty, alokacja vs cel (`summary.build`) |
| GET | `/api/history?benchmark_rate=` | seria wartości + benchmark |
| GET | `/api/daily-changes` | dzienny P/L (zmiana wyceny ETF D/D, koszt transakcji odjęty) + rozbicie `instrument_pln`/`fx_pln` — `history.portfolio_daily_changes` |
| GET | `/api/instruments/{isin}/history` | widok waloru (cena natywna/PLN, atrybucja) |
| GET/PUT | `/api/instruments[/{isin}]` | mapowania ISIN→ticker (+ category) |
| GET | `/api/cash` / POST / DELETE `/{id}` | księga gotówki |
| GET/PUT | `/api/allocation` | alokacja docelowa vs rzeczywista |
| POST | `/api/refresh` | bieżące ceny + FX + dociągnięcie luk od ostatniego dnia w cache (`history.refresh_latest`) |
| POST | `/api/backfill` | pełna historia cen + FX od pierwszej transakcji |
| GET | `/api/export/transactions.csv` | eksport transakcji (CSV) |
| GET | `/api/export/daily-changes.csv` | eksport dziennych zmian wartości (CSV) — `backup.daily_changes_csv` |
| GET | `/api/export/db` | pobranie spójnej kopii bazy SQLite |
| GET/POST | `/api/backups` / `/api/backup-now` | lista kopii / backup na żądanie |
| GET | `/api/health` | health check |

Dokumentacja generowana z kodu (zawsze zgodna, bez ręcznej aktualizacji):
Swagger UI `/docs` · ReDoc `/redoc` · OpenAPI JSON `/openapi.json` (do importu w n8n).

## 8. Logika domenowa (kluczowe decyzje)

- **Koszt w PLN z importu** — broker rozlicza w PLN, więc cost basis jest wprost; FX dotyczy tylko bieżącej wyceny.
- **P/L łapie instrument + walutę** — `wartość = cena_natywna × ilość × kurs_NBP`, koszt w PLN → różnica zawiera oba efekty.
- **Średni koszt** (nie FIFO). Sprzedaż: `realized += przychód − śr_koszt × ilość`.
- **Auto-detekcja waluty** (`prices._yf_currency`) + normalizacja **GBx/GBp → GBP** (cena/100).
- **NBP lookback** — brak kursu w weekend/święto → ostatni dostępny ≤ data.
- **Gotówka „bramkowana"** — bez żadnej wpłaty saldo = 0 (nie pokazujemy ujemnego z samych zakupów); aktywuje się po pierwszej wpłacie (`cash.has_external`).
- **XIRR** — money-weighted; przepływy = wpłaty/wypłaty (lub fallback transakcje) + wartość końcowa.
- **TWR** — time-weighted; łańcuch dziennych zwrotów z neutralizacją przepływów (konwencja „początek dnia").
- **Zwroty w okresach** (`history.portfolio_returns`) — okna 1M/3M/YTD/1R/od początku liczone z jednej dziennej serii. Per okno: TWR skumulowany (nie-zannualizowany, headline dla krótkich okien), TWR roczny, XIRR roczny. Wkłady kapitału (z `_contributions`) spójne z serią → neutralizacja TWR i baza XIRR nie liczą dopłat jako zwrotu. Zwracane w `totals.returns` z `/api/portfolio`.
- **Benchmark** — money-weighted: każda wpłata oprocentowana stałą stopą od swojej daty (nie płaska linia!).
- **Atrybucja FX** (widok waloru) — `wartość_bez_zmian_kursu = ilość × cena_natywna × kurs_wejścia`; `efekt_waluty = wartość − wartość_bez_zmian_kursu`; `efekt_instrumentu = total − efekt_waluty`.
- **Rozbicie zmiany dziennej** (`history.portfolio_daily_changes`) — `fx_pln = Σ ilość × cena_dziś × (kurs_dziś − kurs_wczoraj)` (efekt fixingu NBP D/D), `instrument_pln = change_pln − fx_pln` (ruch ceny; dla PLN = całość). Niezmiennik: `instrument_pln + fx_pln == change_pln` (liczone z zaokrąglonych wartości, by kolumny sumowały się co do grosza). Sens: rozdziela, czy dzień zrobił ETF czy złoty — np. skok kursu NBP w poniedziałek vs ruch instrumentu.
- **Import cen z CSV** (`prices.parse_price_csv` + `prices.import_prices`) — ratunek, gdy provider nie oddaje poprawnej historii dla waloru (jedyny działający kanał dla niszowych papierów GPW). Parser czysty: rozpoznaje kolumny po nagłówku (PL/EN: `Data`/`Date`, `Zamkniecie`/`Close`), wykrywa separator (`,`/`;`/tab), akceptuje datę ISO/`YYYYMMDD`/`DD.MM.YYYY` i przecinek dziesiętny. Zapis `INSERT OR REPLACE` z `source='csv'`. **Waluta wymagana do wyceny** (CSV jej nie niesie; bez niej kurs FX → wartość 0): `import_prices(currency=...)` ustawia ją na instrumencie, jeśli podana; gdy brak i instrument też jej nie ma → `ValueError` (NIE zgadujemy PLN — stooq notuje też w USD/EUR/GBP). W UI: przy braku waluty frontend pyta (podpowiedź PLN). **Pułapka:** pełny `backfill`/`refresh` (yfinance) może nadpisać te punkty z powrotem — po backfillu importuj CSV ponownie. Endpoint `POST /api/prices/import` (`isin`+`file`+opcjonalnie `currency`), w UI przycisk „Importuj ceny (CSV)" w oknie waloru.
- **Świeżość cen (UI)** — `value_positions` zwraca `price_date` per pozycja; front (`PositionsTable`/`PriceAge`, `format.daysSince`) pokazuje „dziś/wczoraj/N dni temu", a przy `> 4` dniach kalendarzowych (poza weekend+święto) ⚠️ — sygnał, że provider milczy i czas na import CSV. Czysto frontendowe, backend już miał `price_date`.
- **Refresh dociąga luki** (`history.refresh_latest`) — odświeżenie pobiera bieżący punkt (`fetch_latest`/`get_rate`) ORAZ uzupełnia brakujący zakres od ostatniego dnia w cache do dziś (`fetch_history`/`backfill_range`). Okno zawsze od ostatniego cache (instrument bez cache → od pierwszej transakcji), NIGDY całość co odświeżenie — świadomie, ze względu na limity API. Współdzielone przez `/api/refresh` i cron.

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
- **stooq MARTWY jako źródło** — stooq postawił JS proof-of-work na endpointach CSV; blokuje `httpx`/`curl` (brak wykonania JS) **nawet z domowego IP** (sprawdzone empirycznie 2026-06). Usunięty z dropdownu źródeł w UI; szkielet `_stooq_*` w `prices.py` zostaje jako slot pod przyszły provider, ale de facto nieużywalny. Dla papierów, których yfinance nie obsługuje (niszowy GPW) — jedyna droga to **import CSV** (eksport ze stooq w przeglądarce + `POST /api/prices/import`). Darmowych API dla niszowego GPW brak (sprawdzone: Twelve Data free i Alpha Vantage free nie mają GPW; AV free obsługuje za to Xetrę/LSE — możliwy fallback dla yfinance na mainstreamie, ale nie wpięty).
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
| Nowe metryki/raporty | endpoint w `main.py` + funkcja w module backendu + nowy komponent w `frontend/src/components/` podpięty jedną linią w `App.jsx` |
| Zadanie cykliczne | `scheduler.py` — kolejny `add_job` |
| Eksport danych | endpoint w `main.py` (np. CSV/JSON z `transactions`/`portfolio`) |

Po każdej zmianie: `pytest` (backend) + `npm run build` (frontend) + rebuild obrazu do testu w Dockerze.
