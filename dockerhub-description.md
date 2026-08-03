# Portfolio Tracker

Prywatny, self-hostowany tracker portfela ETF-ów dla jednego inwestora kupującego
przez polskie biuro maklerskie. Importuje historię transakcji z CSV lub PDF, pobiera bieżące
wyceny i pokazuje wartość, zysk/stratę oraz stopy zwrotu — **wszystko w PLN**.

> Aplikacja nie ma logowania. Uruchamiaj ją w zaufanej sieci lokalnej albo za
> VPN/Tailscale/reverse proxy z własną warstwą dostępu.

## Funkcje

- **Czytelny wealth cockpit** — jasna przestrzeń robocza z ciemnym sidebarem; osobne
  sekcje Pulpit, Portfel, Aktywność, Alokacja, Raporty i analiza oraz Dane i ustawienia.
- **Struktura portfela na Pulpicie** — przełączany widok kategorii i walorów, procentowe
  udziały pozycji oraz wskaźnik koncentracji w trzech największych inwestycjach.
- **Responsywny interfejs** — desktopowy sidebar i dolna nawigacja na telefonie.
- **Import CSV i PDF** z biura maklerskiego (GPW „historia PW”, eMAKLER
  „Transakcje bieżące” oraz potwierdzenia wykonania zleceń mBanku) — format rozpoznawany
  automatycznie, import idempotentny. PDF zapisuje dodatkowo cenę i walutę wykonania,
  kurs FX, prowizję, rynek, datę rozliczenia oraz numer zlecenia i może wzbogacić wpis z CSV.
- **Nowe symbole eMAKLER konfigurowane w UI** — użytkownik podaje ISIN, nazwę, ticker i
  walutę, mapowanie zapisuje się w SQLite, a import jest automatycznie ponawiany. Bez
  zaszytych aliasów i bez zgadywania instrumentów.
- **Ręczne dodawanie/usuwanie transakcji** w UI (z tym samym dedupem co import).
- **Wycena w PLN** — ETF-y notowane w EUR/USD/GBP przeliczane bieżącym kursem NBP;
  Yahoo wykrywa walutę automatycznie (z obsługą pensów GBx), dla providerów REST ustawia ją UI.
- **Yahoo, EODHD i Alpha Vantage** — osobny symbol i waluta zapisywane dla każdego providera;
  przełączanie źródła przywraca jego mapowanie bez nadpisywania pozostałych;
  Xetra używa odpowiednio `.DE`, `.XETRA` albo `.DEX`.
- **Import cen z CSV** — gdy provider nie ma poprawnej historii waloru, wgraj dzienne ceny z pliku (format stooq). Wgrane punkty są chronione przed automatycznym backfillem.
- **Zysk całkowity** — niezrealizowany (otwarte pozycje) + zrealizowany (sprzedaże).
- **Konto gotówkowe** — ręczne wpłaty/wypłaty, śledzenie niezainwestowanej gotówki.
- **Wykres wartości w czasie** + **dwa benchmarki** (przełączane): konfigurowalna stała stopa (np. 5%/rok) oraz **inflacja + X%** (realny indeks HICP dla Polski, Eurostat). Przełącznik trybu: wartość konta (PLN) **lub** stopa zwrotu (%) vs benchmarki w %.
- **XIRR i TWR** — roczny zwrot money-weighted (z timingiem wpłat) oraz time-weighted (wynik portfela).
- **Raporty okresowe** — bieżący i poprzedni miesiąc/rok, ostatnie 12 miesięcy lub własny
  zakres; wynik PLN, TWR/XIRR, benchmarki, poprzedni okres, walory, klasy, waluty, przepływy,
  prowizje, mapa miesięcznych zwrotów oraz eksport CSV i druk/zapis PDF.
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
- **Odświeżanie przez API** (`POST /api/refresh`) + dociąganie luk w historii po awarii. Odpytuje tylko aktualnie trzymane walory — sprzedany ETF nie zaśmieca bazy.

## Źródła danych

- Wyceny: Yahoo Finance, EODHD lub Alpha Vantage per instrument; ręczny CSV jako fallback.
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
| `SCHEDULER_ENABLED` | `true` (`false` w Compose) | wewnętrzny harmonogram; wyłączony przy sterowaniu przez API |
| `EODHD_API_KEY` | brak | klucz EODHD dla instrumentów ze źródłem `eodhd` |
| `ALPHA_VANTAGE_API_KEY` | brak | klucz Alpha Vantage dla źródła `alphavantage` |
| `EODHD_MIN_INTERVAL_SECONDS` | `1` | minimalny odstęp zapytań EODHD |
| `ALPHAVANTAGE_MIN_INTERVAL_SECONDS` | `12` | minimalny odstęp zapytań Alpha Vantage |
| `TZ` | `Europe/Warsaw` | strefa czasowa (cron) |
| `REFRESH_HOUR` | `21` | godzina dziennego odświeżania |
| `REFRESH_MINUTE` | `0` | minuta dziennego odświeżania |
| `BACKUP_HOUR` / `BACKUP_MINUTE` | `3` / `0` | pora nocnego backupu |
| `BACKUP_KEEP` | `14` | liczba przechowywanych kopii |
| `BACKUP_STALE_HOURS` | `36` | próg ostrzeżenia o wieku ostatniej poprawnej kopii |
| `DB_PATH` | `/app/data/portfolio.db` | ścieżka bazy SQLite |

Stack: FastAPI + SQLite + Yahoo/EODHD/Alpha Vantage · frontend React/Recharts · obraz multi-arch (arm64 + amd64).

W interfejsie można wyszukać symbol EODHD po ISIN-ie/nazwie albo symbol Alpha Vantage
po nazwie/tickerze. Zapytania REST mają limiter i trzy próby z backoffem; klucze pozostają
wyłącznie po stronie backendu.
