# Portfolio Tracker

Prosty, self-hostowany tracker portfela ETF-ów dla inwestora kupującego przez
polskie biuro maklerskie. Importuje historię transakcji z CSV, pobiera bieżące
wyceny i pokazuje wartość, zysk/stratę oraz roczną stopę zwrotu — **wszystko w PLN**.

## Funkcje

- **Import CSV** z biura maklerskiego (format GPW „historia PW", CP1250) — idempotentny.
- **Wycena w PLN** — ETF-y notowane w EUR/USD/GBP przeliczane bieżącym kursem NBP;
  waluta wykrywana automatycznie (z obsługą londyńskich pensów GBx).
- **Zysk całkowity** — niezrealizowany (otwarte pozycje) + zrealizowany (sprzedaże).
- **Konto gotówkowe** — ręczne wpłaty/wypłaty, śledzenie niezainwestowanej gotówki.
- **Wykres wartości w czasie** + porównanie z konfigurowalnym benchmarkiem (np. 5%/rok).
- **XIRR** — roczny zwrot money-weighted całego rachunku.
- **Historia transakcji** i ręczne mapowanie ISIN → ticker.
- **Codzienne odświeżanie** cen i kursów (cron ~21:00 Europe/Warsaw).

## Źródła danych

- Wyceny: Yahoo Finance (yfinance), opcjonalnie stooq dla GPW.
- Kursy walut: [NBP API](https://api.nbp.pl) (tabela A, darmowe).

## Uruchomienie

```bash
docker compose up -d
```

Aplikacja: `http://localhost:8000`. Dane (SQLite) trzymane w named volume `portfolio_tracker_data`.

## Konfiguracja (zmienne środowiskowe)

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `TZ` | `Europe/Warsaw` | strefa czasowa (cron) |
| `REFRESH_HOUR` | `21` | godzina dziennego odświeżania |
| `REFRESH_MINUTE` | `0` | minuta dziennego odświeżania |
| `DB_PATH` | `/app/data/portfolio.db` | ścieżka bazy SQLite |

Stack: FastAPI + SQLite + yfinance · frontend React/Recharts · obraz multi-arch (arm64 + amd64).
