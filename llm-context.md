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
| Inflacja (benchmark) | **Eurostat HICP** (`prc_hicp_midx`, PL, miesięczny) | darmowe, bez klucza; GUS BDL ma CPI tylko rocznie/kwartalnie |
| Harmonogram | **APScheduler** (BackgroundScheduler) | dzienne odświeżanie ~21:00 |
| Klient HTTP | **httpx** | zapytania do NBP/Eurostat |
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
| `httpx` | HTTP do NBP i Eurostat |
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
- **Eurostat** — oficjalne, stabilne, bez klucza. `prc_hicp_midx?geo=PL&coicop=CP00&unit=I15` = miesięczny indeks HICP (baza 2015=100), 1996→teraz. Świadomie HICP, nie CPI GUS: GUS BDL API ma indeks cen tylko rocznie (`P2955`) i kwartalnie (`P2496`), miesięcznego nie ma wcale (tylko HTML). HICP vs CPI GUS różni się ~0,2 pp/rok — w skali benchmarku nieistotne.
- **stooq** — martwe jako źródło: JS proof-of-work blokuje klientów bez JS nawet z domowego IP (usunięte z UI **i z kodu** — ścieżka live-source `_stooq_*` skasowana). Format eksportu CSV ze stooq jest nadal wejściem dla importu cen.

## 4. Architektura i moduły

```
backend/app/
  main.py        # FastAPI: WSZYSTKIE endpointy, lifespan (start crona), serwowanie frontend/dist
  db.py          # połączenie SQLite, SCHEMA (CREATE IF NOT EXISTS), _migrate(), db_session()
  importer.py    # parse_csv (CP1250), import_transactions, add_transaction, delete_transaction
  instruments.py # ensure_instrument (+ SEED ISIN->ticker), list/update_instrument
  prices.py      # yfinance: fetch_latest/fetch_history, auto-detekcja waluty (GBx->GBP), cache; parse_price_csv/import_prices (import cen z CSV, format stooq)
  fx.py          # NBP: get_rate (lookback), backfill_range, cache w fx_rates
  cpi.py         # Eurostat HICP: refresh_cpi (cache cpi_index), load_points, index_at (interpolacja) — pod benchmark inflacyjny
  cash.py        # księga gotówki: balance/has_external, add/delete flow, record/remove_trade_cash
  portfolio.py   # compute_positions (średni koszt + zrealizowany), value_positions (sumy)
  history.py     # refresh_latest (bieżące+luki, TYLKO trzymane), backfill_all, portfolio_history (+2 benchmarki: stała stopa + inflacja, +_pct), portfolio_xirr/twr, portfolio_drawdown, instrument_history
  returns.py     # czyste funkcje: xirr() (Newton+bisekcja), twr_detail()/twr_index() (łańcuch podokresów, indeks growth-of-1)
  allocation.py  # compute (grupy vs cel + rebalans), get/set_targets
  summary.py     # build() — digest pod powiadomienia (kompozycja portfolio+history+allocation)
  backup.py      # backup_database (online copy + retencja), transactions_csv, list_backups
  scheduler.py   # start_scheduler() — APScheduler: refresh_job (~21:00, woła history.refresh_latest) + backup_job (~03:00)
frontend/src/
  App.jsx        # orkiestracja: stan (useState), loadAll (Promise.all), run(), handlery, layout zakładek
  components/    # jeden komponent = jeden plik: Cards, ReturnsStrip, HistoryChart, DrawdownChart,
                 #   InstrumentDetail, PositionsTable, TransactionForm, TransactionsTable, CashPanel,
                 #   InstrumentsPanel, AllocationPanel (+ AllocationDonut), DataPanel, BackupModal,
                 #   DailyChangesTable
  format.js      # wspólne helpery: fmtPln, fmtPct, cls, fmtDate
  api.js         # cienki klient REST (fetch)
  styles.css     # ciemny motyw, bez frameworka CSS, responsywny (@media <640px)
```

### Zależności między modułami (kierunek importów)

```
main.py → importer, instruments, prices, fx, cpi, cash, portfolio, history, allocation, scheduler
importer.py → cash, instruments
portfolio.py → cash, fx, prices
history.py → cpi, fx, prices, returns
allocation.py → cash, portfolio
summary.py → portfolio, history, allocation
backup.py → db
cash.py, fx.py, cpi.py, prices.py, instruments.py, returns.py, db.py → (liście, bez zależności wewn.)
scheduler.py → cash, instruments, prices, fx, db, backup
```

`returns.py` jest czysto funkcyjny (łatwy do testów). `db.py` nie zależy od niczego z app.

## 5. Model danych (SQLite, `db.py:SCHEMA`)

| Tabela | Klucz | Kolumny | Rola |
|---|---|---|---|
| `instruments` | `isin` | name (edytowalna własna nazwa w UI, przetrwa import), ticker, currency, source, category, active, needs_config | mapowanie waloru |
| `transactions` | `id` | ts, isin→, type(BUY/SELL), quantity, price_pln, value_pln, commission_pln, **import_hash UNIQUE** | handel |
| `prices` | (isin,date) | price (waluta natywna), source | cache wycen |
| `fx_rates` | (date,currency) | rate_to_pln | cache kursów NBP |
| `cpi_index` | `month` | idx (HICP, baza 2015=100) | cache inflacji (miesięczny, `month`='YYYY-MM-01') |
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
   → prices (yfinance, waluta auto) + fx_rates (NBP)
odczyt
   → portfolio.value_positions  → pozycje, P/L, gotówka, wartość konta
   → history.portfolio_history  → seria wartości + benchmark + stopy zwrotu %
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
| GET | `/api/history?benchmark_rate=&cpi_spread=` | seria `value_pln` + 2 benchmarki: `benchmark_pln` (stała stopa) i `benchmark_cpi_pln` (inflacja HICP + `cpi_spread`) + warianty `_pct` + `portfolio_pct` (przełącznik trybu PLN/% i widoczności benchmarków w `HistoryChart`) |
| GET | `/api/daily-changes` | dzienny P/L (zmiana wyceny ETF D/D, koszt transakcji odjęty) + rozbicie `instrument_pln`/`fx_pln` — `history.portfolio_daily_changes` |
| GET | `/api/drawdown` | obsunięcie portfela (drawdown) na indeksie TWR: krzywa „pod wodą" + max/bieżące DD z datami szczytu/dołka/odbicia — `history.portfolio_drawdown` |
| GET | `/api/instruments/{isin}/history` | widok waloru (cena natywna/PLN, atrybucja) |
| GET/PUT | `/api/instruments[/{isin}]` | mapowania ISIN→ticker (+ name własna, + category) |
| GET | `/api/cash` / POST / DELETE `/{id}` | księga gotówki |
| GET/PUT | `/api/allocation` | alokacja docelowa vs rzeczywista |
| POST | `/api/refresh` | bieżące ceny + FX + dociągnięcie luk od ostatniego dnia w cache, TYLKO trzymane walory (`history.refresh_latest`); odświeża też CPI |
| POST | `/api/backfill` | pełna historia cen + FX od pierwszej transakcji (wszystkie walory); odświeża też CPI |
| POST | `/api/cpi/refresh` | pobranie serii inflacji (Eurostat HICP) — **niezależne od cen**, nie dotyka `prices` (bezpieczne dla walorów z CSV) (`cpi.refresh_cpi`) |
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
- **Benchmarki** (`portfolio_history`) — DWA, oba money-weighted (każda wpłata oprocentowana od swojej daty, nie płaska linia): (1) **stała stopa** `amount × (1+benchmark_rate)^lata`; (2) **inflacja + X%** `amount × indeks_HICP(d)/indeks_HICP(wpłata) × (1+cpi_spread)^lata`. Indeks HICP z cache `cpi_index` (`cpi.load_points`), interpolacja liniowa między miesiącami + forward-fill końca (`cpi.index_at`). Bazowy indeks per wkład liczony raz przed pętlą. Gdy cache CPI pusty (`has_cpi=False`) → pola `benchmark_cpi_*` = `None` (front nie rysuje linii). Pola wyjściowe: `benchmark_pln`/`benchmark_pct` (stała), `benchmark_cpi_pln`/`benchmark_cpi_pct` (inflacja). Front: `HistoryChart` ma osobne przełączniki widoczności obu benchmarków, działa w trybie PLN i %.
- **Drawdown** (`history.portfolio_drawdown` + `returns.twr_index`) — obsunięcie liczone na **indeksie wzrostu TWR** (growth-of-1, ta sama neutralizacja przepływów co `twr_detail`), NIE na surowej wartości PLN: wpłaty IKE nie maskują spadków, wypłaty nie udają obsunięć. `drawdown[d] = indeks/dotychczasowy_szczyt − 1` (≤ 0). Zwraca dzienną krzywą „pod wodą" (`series`), `max_drawdown` z datami szczytu/dołka (`..._from`/`..._to`), `recovery_date` (pierwszy dzień powrotu do poziomu szczytu sprzed obsunięcia) oraz `current_drawdown`/`in_drawdown`. Front: `DrawdownChart` (czerwona krzywa pod osią 0 + pasek podsumowania) na Pulpicie pod wykresem wartości.
- **Stopa zwrotu % vs benchmark %** (`portfolio_history`) — `portfolio_pct = (wartość − cum_wkłady) / cum_wkłady × 100`, analogicznie `benchmark_pct`. Skumulowane wkłady liczone inkrementalnie (O(dni + wpłaty), nie O(dni × wpłaty)). Przed pierwszą wpłatą `cum_wkłady = 0` → `null` (przerwa w linii, `connectNulls` tylko w trybie PLN). Bez wpłat zewnętrznych fallback na transakcje (wkład = cost basis). Przełącznik trybu wykresu (PLN/%) jest czysto frontendowy w `HistoryChart`.
- **Atrybucja FX** (widok waloru) — `wartość_bez_zmian_kursu = ilość × cena_natywna × kurs_wejścia`; `efekt_waluty = wartość − wartość_bez_zmian_kursu`; `efekt_instrumentu = total − efekt_waluty`.
- **Rozbicie zmiany dziennej** (`history.portfolio_daily_changes`) — `fx_pln = Σ ilość × cena_dziś × (kurs_dziś − kurs_wczoraj)` (efekt fixingu NBP D/D), `instrument_pln = change_pln − fx_pln` (ruch ceny; dla PLN = całość). Niezmiennik: `instrument_pln + fx_pln == change_pln` (liczone z zaokrąglonych wartości, by kolumny sumowały się co do grosza). Sens: rozdziela, czy dzień zrobił ETF czy złoty — np. skok kursu NBP w poniedziałek vs ruch instrumentu.
- **Import cen z CSV** (`prices.parse_price_csv` + `prices.import_prices`) — ratunek, gdy provider nie oddaje poprawnej historii dla waloru (jedyny działający kanał dla niszowych papierów GPW). Parser czysty: rozpoznaje kolumny po nagłówku (PL/EN: `Data`/`Date`, `Zamkniecie`/`Close`), wykrywa separator (`,`/`;`/tab), akceptuje datę ISO/`YYYYMMDD`/`DD.MM.YYYY` i przecinek dziesiętny. Zapis przez `prices._cache_put` z `source='csv'`. **Waluta wymagana do wyceny** (CSV jej nie niesie; bez niej kurs FX → wartość 0): `import_prices(currency=...)` ustawia ją na instrumencie, jeśli podana; gdy brak i instrument też jej nie ma → `ValueError` (NIE zgadujemy PLN — stooq notuje też w USD/EUR/GBP). W UI: przy braku waluty frontend pyta (podpowiedź PLN). **Punkty CSV są chronione przed nadpisaniem** (patrz `_cache_put` niżej) — backfill/refresh yfinance ich NIE skasuje, więc stara pułapka „re-importuj CSV po backfillu" już nie istnieje (re-import nadal nadpisuje, gdy chcesz). Endpoint `POST /api/prices/import` (`isin`+`file`+opcjonalnie `currency`), w UI przycisk „Importuj ceny (CSV)" w oknie waloru.
- **Świeżość cen (UI)** — `value_positions` zwraca `price_date` per pozycja; front (`PositionsTable`/`PriceAge`, `format.daysSince`) pokazuje „dziś/wczoraj/N dni temu", a przy `> 4` dniach kalendarzowych (poza weekend+święto) ⚠️ — sygnał, że provider milczy i czas na import CSV. Czysto frontendowe, backend już miał `price_date`.
- **Refresh dociąga luki, tylko trzymane** (`history.refresh_latest`) — odświeżenie pobiera bieżący punkt (`fetch_latest`/`get_rate`) ORAZ uzupełnia brakujący zakres od ostatniego dnia w cache do dziś (`fetch_history`/`backfill_range`). Okno zawsze od ostatniego cache (instrument bez cache → od pierwszej transakcji), NIGDY całość co odświeżenie — świadomie, ze względu na limity API. **Odpytuje tylko AKTUALNIE TRZYMANE walory** (`held` = `SUM(BUY−SELL) > 0` liczone z `transactions`, NIE ręczna flaga `active`, której nikt nie zmienia po sprzedaży) — sprzedany do zera ETF nie jest pobierany ani nie zaśmieca `prices` punktami pod bieżącą datą; jego historia z okresu posiadania zostaje w cache. FX gated tym samym (waluty tylko trzymanych). Pełną rekonstrukcję wszystkich walorów robi ręczny `backfill_all`. Współdzielone przez `/api/refresh` i cron.
- **Ochrona danych z CSV** (`prices._cache_put`) — ręczny import (`source='csv'`) jest „święty": automatyczny provider (yfinance, `source != 'csv'`) używa UPSERT `ON CONFLICT(isin,date) DO UPDATE … WHERE prices.source IS NOT 'csv'` — wypełnia brakujące dni i aktualizuje WŁASNE punkty, ale NIE nadpisuje wierszy z CSV. Re-import CSV (ścieżka `source='csv'`) używa `INSERT OR REPLACE` → zawsze wygrywa. Dzięki temu backfill/refresh są bezpieczne dla papierów ratowanych z CSV.

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
- **stooq MARTWY jako źródło** — stooq postawił JS proof-of-work na endpointach CSV; blokuje `httpx`/`curl` (brak wykonania JS) **nawet z domowego IP** (sprawdzone empirycznie 2026-06). Usunięty z dropdownu źródeł w UI **oraz z kodu** — ścieżka live-source `_stooq_*` w `prices.py` skasowana (była nieużywalna; ponytail-audit 2026-06). Dla papierów, których yfinance nie obsługuje (niszowy GPW) — jedyna droga to **import CSV** (eksport ze stooq w przeglądarce + `POST /api/prices/import`). Darmowych API dla niszowego GPW brak (sprawdzone: Twelve Data free i Alpha Vantage free nie mają GPW; AV free obsługuje za to Xetrę/LSE — możliwy fallback dla yfinance na mainstreamie, ale nie wpięty).
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
| Kolejny benchmark (np. realny indeks ETF) | skopiuj wzorzec benchmarku inflacyjnego: klient+cache jak `cpi.py`, nowe pole w `portfolio_history` (mnożnik `seria(d)/seria(wpłata)`), param w `/api/history`, linia + przełącznik w `HistoryChart` |
| FIFO / realizowany P/L per lot | `portfolio.compute_positions` — kolejka lotów zamiast średniego kosztu |
| Dywidendy / podatki | nowe `kind` w `cash_flows` + obsługa w imporcie i `cash.balance`; uwzględnij w XIRR |
| Nowe metryki/raporty | endpoint w `main.py` + funkcja w module backendu + nowy komponent w `frontend/src/components/` podpięty jedną linią w `App.jsx` |
| Zadanie cykliczne | `scheduler.py` — kolejny `add_job` |
| Eksport danych | endpoint w `main.py` (np. CSV/JSON z `transactions`/`portfolio`) |

Po każdej zmianie: `pytest` (backend) + `npm run build` (frontend) + rebuild obrazu do testu w Dockerze.
