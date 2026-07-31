# Portfolio Tracker

Prywatny, self-hostowany tracker portfela ETF-ów dla jednego inwestora kupującego
przez polskie biuro maklerskie. Importuje historię transakcji z CSV, pobiera bieżące
wyceny i pokazuje wartość, zysk/stratę oraz stopy zwrotu — **wszystko w PLN**.

> Aplikacja nie ma logowania. Uruchamiaj ją w zaufanej sieci lokalnej albo za
> VPN/Tailscale/reverse proxy z własną warstwą dostępu.

## Funkcje

- **Czytelny wealth cockpit** — jasna przestrzeń robocza z ciemnym sidebarem; osobne
  sekcje Pulpit, Portfel, Aktywność, Alokacja, Analiza oraz Dane i ustawienia.
- **Responsywny interfejs** — desktopowy sidebar i dolna nawigacja na telefonie.
- **Import CSV** z biura maklerskiego (GPW „historia PW” oraz eMAKLER
  „Transakcje bieżące”, CP1250) — format rozpoznawany automatycznie, import idempotentny
  (CSV ze starymi + nowymi danymi importuje tylko nowe).
- **Ręczne dodawanie/usuwanie transakcji** w UI (z tym samym dedupem co import).
- **Wycena w PLN** — ETF-y notowane w EUR/USD/GBP przeliczane bieżącym kursem NBP;
  waluta wykrywana automatycznie (z obsługą londyńskich pensów GBx).
- **Import cen z CSV** — gdy Yahoo nie ma poprawnej historii waloru, wgraj dzienne ceny z pliku (format stooq) wprost na widoku waloru. Wgrane punkty są chronione — automatyczny backfill ich nie nadpisuje.
- **Zysk całkowity** — niezrealizowany (otwarte pozycje) + zrealizowany (sprzedaże).
- **Konto gotówkowe** — ręczne wpłaty/wypłaty, śledzenie niezainwestowanej gotówki.
- **Wykres wartości w czasie** + **dwa benchmarki** (przełączane): konfigurowalna stała stopa (np. 5%/rok) oraz **inflacja + X%** (realny indeks HICP dla Polski, Eurostat). Przełącznik trybu: wartość konta (PLN) **lub** stopa zwrotu (%) vs benchmarki w %.
- **XIRR i TWR** — roczny zwrot money-weighted (z timingiem wpłat) oraz time-weighted (wynik portfela).
- **Obsunięcie (drawdown)** — wykres „pod wodą" (spadek od szczytu) na indeksie TWR — flow-neutral, więc wpłaty nie maskują spadków; max + bieżące DD z datami.
- **Alokacja docelowa** — kategorie ETF-ów, wagi modelu i plan podziału nowej wpłaty
  pomiędzy niedoważone klasy bez sugerowania sprzedaży.
- **Kontrola jakości danych** — ostrzeżenia o brakujących lub starych cenach i kursach,
  konfiguracji instrumentów, alokacji, sprzedaży ponad stan i niespójności gotówki.
- **Atrybucja wyniku** — zrealizowany i niezrealizowany wynik według ETF-ów i klas aktywów,
  historia wpłat, prowizje i aktywność inwestycyjna.
- **Widok waloru** — historia dzień po dniu + atrybucja zysku na instrument vs walutę (kurs PLN).
- **Zmiany dzienne** — dzienny wynik rynkowy ETF, skorygowany o przepływy handlowe, z eksportem CSV.
- **Historia transakcji** — wyszukiwanie, filtry, edycja, notatki i prowizje oraz ręczne
  mapowanie ISIN → ticker.
- **Eksport, backup i restore** — nocne kopie, kontrola integralności i SHA-256, ostrzeżenie
  o wieku kopii, pobieranie backupów oraz bezpieczne odtwarzanie z automatyczną kopią „przed".
- **Codzienne odświeżanie** cen i kursów (cron ~21:00 Europe/Warsaw) + dociąganie luk w historii po awarii. Odpytuje tylko aktualnie trzymane walory — sprzedany ETF nie zaśmieca bazy.

## Źródła danych

- Wyceny: Yahoo Finance (yfinance); ratunek dla papierów spoza pokrycia Yahoo — import cen z CSV.
- Kursy walut: [NBP API](https://api.nbp.pl) (tabela A, darmowe).
- Inflacja (benchmark): [Eurostat HICP](https://ec.europa.eu/eurostat) (miesięczny, PL, darmowe).

## Uruchomienie

```bash
docker compose up -d
```

Aplikacja: `http://localhost:8000`. Dane SQLite są trzymane poza obrazem, w named volume
`portfolio_tracker_data`, więc aktualizacja kontenera nie usuwa portfela.

## Konfiguracja (zmienne środowiskowe)

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `TZ` | `Europe/Warsaw` | strefa czasowa (cron) |
| `REFRESH_HOUR` | `21` | godzina dziennego odświeżania |
| `REFRESH_MINUTE` | `0` | minuta dziennego odświeżania |
| `BACKUP_HOUR` / `BACKUP_MINUTE` | `3` / `0` | pora nocnego backupu |
| `BACKUP_KEEP` | `14` | liczba przechowywanych kopii |
| `BACKUP_STALE_HOURS` | `36` | próg ostrzeżenia o wieku ostatniej poprawnej kopii |
| `DB_PATH` | `/app/data/portfolio.db` | ścieżka bazy SQLite |

Stack: FastAPI + SQLite + yfinance · frontend React/Recharts · obraz multi-arch (arm64 + amd64).
