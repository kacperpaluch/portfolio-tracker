# Portfolio Tracker

Prosty, self-hostowany tracker portfela ETF-ów dla inwestora kupującego przez
polskie biuro maklerskie. Importuje historię transakcji z CSV, pobiera bieżące
wyceny i pokazuje wartość, zysk/stratę oraz roczną stopę zwrotu — **wszystko w PLN**.

## Funkcje

- **Import CSV** z biura maklerskiego (format GPW „historia PW", CP1250) — idempotentny
  (CSV ze starymi + nowymi danymi importuje tylko nowe).
- **Ręczne dodawanie/usuwanie transakcji** w UI (z tym samym dedupem co import).
- **Wycena w PLN** — ETF-y notowane w EUR/USD/GBP przeliczane bieżącym kursem NBP;
  waluta wykrywana automatycznie (z obsługą londyńskich pensów GBx).
- **Import cen z CSV** — gdy Yahoo nie ma poprawnej historii waloru, wgraj dzienne ceny z pliku (format stooq) wprost na widoku waloru.
- **Zysk całkowity** — niezrealizowany (otwarte pozycje) + zrealizowany (sprzedaże).
- **Konto gotówkowe** — ręczne wpłaty/wypłaty, śledzenie niezainwestowanej gotówki.
- **Wykres wartości w czasie** + porównanie z konfigurowalnym benchmarkiem (np. 5%/rok) — przełącznik trybu: wartość konta (PLN) **lub** stopa zwrotu (%) vs benchmark w %.
- **XIRR i TWR** — roczny zwrot money-weighted (z timingiem wpłat) oraz time-weighted (wynik portfela).
- **Alokacja docelowa** — kategorie ETF-ów, wagi modelu (np. 60/40) i porównanie z rebalansem.
- **Widok waloru** — historia dzień po dniu + atrybucja zysku na instrument vs walutę (kurs PLN).
- **Zmiany dzienne** — dzienny P/L z rozbiciem na efekt instrumentu vs kurs NBP (co napędzało dzień) + eksport CSV.
- **Historia transakcji** i ręczne mapowanie ISIN → ticker.
- **Eksport i backup** — pobranie transakcji (CSV) i całej bazy z UI + nocny backup bazy (cron).
- **Codzienne odświeżanie** cen i kursów (cron ~21:00 Europe/Warsaw) + dociąganie luk w historii po awarii.

## Źródła danych

- Wyceny: Yahoo Finance (yfinance); ratunek dla papierów spoza pokrycia Yahoo — import cen z CSV.
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
