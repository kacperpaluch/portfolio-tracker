# Portfolio Tracker

[![Docker Hub](https://img.shields.io/docker/pulls/kpa90/portfolio-tracker?logo=docker)](https://hub.docker.com/r/kpa90/portfolio-tracker)

Prosty, self-hostowany tracker portfela ETF-ów dla inwestora kupującego przez
polskie biuro maklerskie. Importuje historię transakcji z CSV, pobiera bieżące
wyceny przez API i pokazuje wartość, zysk/stratę oraz roczną stopę zwrotu —
**wszystko w PLN**.

## Kluczowe założenia

- **Koszt nabycia jest w PLN** (broker rozlicza w złotówkach), więc cost basis bierzemy
  wprost z importu — bez przeliczeń.
- Większość ETF-ów jest notowana realnie w **EUR/USD/GBP** za granicą; bieżącą wycenę
  liczymy jako `cena × ilość × kurs_NBP`, więc P/L w PLN automatycznie łapie ruch
  instrumentu **i** waluty. Instrumenty z GPW (np. ETF PZU) są w PLN — bez FX.
- **Waluta wykrywana automatycznie** z notowania (z obsługą londyńskich pensów GBx→GBP).
- Wyceny odświeżane **raz dziennie cronem (~21:00 Europe/Warsaw)** — bez real-time.

## Źródła danych

| Dane | Źródło |
|---|---|
| Wyceny instrumentów | [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance), opcjonalnie stooq dla GPW |
| Kursy walut | [NBP API](https://api.nbp.pl) (tabela A, darmowe, bez klucza) |

Mapowanie **ISIN → ticker** robisz w UI (zakładka *Instrumenty*). Dla przykładowego
portfela tickery są wstępnie skonfigurowane (np. `FWIA.DE`, `ETFPZUWORLD.WA`).

## Uruchomienie (Docker)

Obraz dostępny na [Docker Hub](https://hub.docker.com/r/kpa90/portfolio-tracker) (multi-arch: arm64 + amd64).

```bash
docker compose up -d
```

Aplikacja: http://localhost:8000 — baza SQLite trwała w named volume `portfolio_tracker_data`.

## Uruchomienie lokalne (dev)

Backend:
```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Frontend (osobny terminal, proxuje `/api` na backend):
```bash
cd frontend
npm install && npm run dev
```

## Użycie

1. **Importuj CSV** — wgraj eksport historii rachunku (format GPW „historia PW";
   kodowanie CP1250, separator `;`, przecinek dziesiętny). Import jest idempotentny.
2. **Instrumenty** — uzupełnij/popraw ticker dla pozycji oznaczonych „do uzupełnienia".
3. **Odśwież ceny** — pobiera bieżące wyceny i kursy NBP.
4. **Backfill historii** — pobiera dzienne ceny i kursy od daty pierwszej transakcji
   (zasila wykres wartości w czasie).

## API

| Metoda | Ścieżka | Opis |
|---|---|---|
| POST | `/api/import` | import CSV |
| GET | `/api/portfolio` | pozycje, wartość, P/L, XIRR |
| GET | `/api/history` | dzienna seria wartości portfela |
| GET/PUT | `/api/instruments[/{isin}]` | mapowania ISIN→ticker |
| POST | `/api/refresh` | odświeżenie bieżących cen i FX |
| POST | `/api/backfill` | pełna historia cen i kursów |

## Testy

```bash
cd backend && .venv/bin/python -m pytest
```

## Architektura

```
backend/app/
  importer.py    # parsing CSV (CP1250, K/S, dedup)
  instruments.py # mapowanie ISIN→ticker + seed
  prices.py      # yfinance/stooq + auto-detekcja waluty (GBx→GBP)
  fx.py          # NBP + cache, lookback na weekendy
  portfolio.py   # pozycje (średni koszt), wycena, P/L
  history.py     # backfill + seria wartości w czasie
  returns.py     # XIRR (Newton + bisekcja)
  scheduler.py   # APScheduler — dzienne odświeżanie
  main.py        # FastAPI + serwowanie frontendu
frontend/        # Vite + React + Recharts
```
