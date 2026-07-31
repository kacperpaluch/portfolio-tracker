# Portfolio Tracker

[![Docker Hub](https://img.shields.io/docker/pulls/kpa90/portfolio-tracker?logo=docker)](https://hub.docker.com/r/kpa90/portfolio-tracker)

Prywatny, self-hostowany tracker portfela ETF-ów dla jednego inwestora kupującego przez
polskie biuro maklerskie (np. konto IKE). Importuje historię transakcji z CSV, pobiera
bieżące wyceny, przelicza waluty kursem NBP i pokazuje wartość, zysk/stratę
(zrealizowany + niezrealizowany), stopę zwrotu oraz porównanie z benchmarkiem —
**wszystko w PLN**.

Projekt jest przeznaczony do uruchomienia we własnym środowisku. Nie ma kont użytkowników,
rejestracji ani autoryzacji, dlatego nie należy wystawiać go bezpośrednio do publicznego
Internetu bez dodatkowej warstwy dostępu (np. VPN, Tailscale lub reverse proxy z logowaniem).

## Zrzuty ekranu

> Nazwy i identyfikatory ETF-ów są publiczne i rzeczywiste, ale wszystkie transakcje,
> liczby, daty, ceny oraz wyniki są syntetycznymi danymi demonstracyjnymi. Zrzuty nie
> korzystają z prywatnej bazy właściciela aplikacji.

| Pulpit | Alokacja | Aktywność |
|---|---|---|
| ![Pulpit](docs/screenshots/dashboard.png) | ![Alokacja](docs/screenshots/allocation.png) | ![Aktywność](docs/screenshots/transactions.png) |

---

## Spis treści

- [Funkcje](#funkcje)
- [Interfejs aplikacji](#interfejs-aplikacji)
- [Kluczowe koncepcje](#kluczowe-koncepcje)
- [Stack technologiczny](#stack-technologiczny)
- [Uruchomienie](#uruchomienie)
- [Konfiguracja](#konfiguracja)
- [Sposób użycia](#sposób-użycia)
- [Architektura](#architektura)
- [Model danych](#model-danych)
- [Jak działa wycena (logika finansowa)](#jak-działa-wycena-logika-finansowa)
- [API](#api)
- [Format pliku CSV](#format-pliku-csv)
- [Prywatność i bezpieczeństwo danych](#prywatność-i-bezpieczeństwo-danych)
- [Testy](#testy)
- [Jak rozbudować](#jak-rozbudować)

---

## Funkcje

- **Prywatny interfejs typu wealth cockpit** — jasna, czytelna przestrzeń robocza z ciemnym
  sidebarem; osobne sekcje Pulpit, Portfel, Aktywność, Alokacja, Analiza oraz Dane i ustawienia.
  Widok mobilny korzysta z dolnej nawigacji i zachowuje pełną funkcjonalność.
- **Import CSV** z biura maklerskiego (GPW „historia PW” oraz eMAKLER
  „Transakcje bieżące”, kodowanie CP1250) — format jest rozpoznawany automatycznie, a import
  jest idempotentny: CSV ze starymi + nowymi danymi importuje tylko nowe, starych nie rusza.
- **Ręczne dodawanie/usuwanie transakcji** — formularz w UI (z dedupem jak w imporcie).
- **Widok waloru** — klik w nazwę pokazuje wykres wartości inwestycji w czasie (rzeczywista vs
  przy stałym kursie) z **atrybucją zysku na instrument vs walutę** (ile dał ETF, a ile ruch
  EUR/PLN w widoku tego waloru) oraz tabelę dzień po dniu (cena giełdowa, kurs NBP, cena PLN, szt., wartość).
- **Wycena w PLN** — instrumenty notowane w EUR/USD/GBP przeliczane bieżącym kursem NBP;
  **waluta wykrywana automatycznie** z notowania (z obsługą londyńskich pensów GBx → GBP).
- **Import cen z CSV (ratunek dla danych Yahoo)** — gdy Yahoo nie oddaje poprawnej historii
  dla mało płynnego waloru (np. ETN na GPW), wgraj dzienne ceny z pliku CSV (format stooq:
  `Data,…,Zamkniecie`) wprost na widoku waloru. Nadpisuje błędne punkty w cache i naprawia
  wykres wartości w czasie, zmiany dzienne oraz atrybucję. Waluta jest wymagana do wyceny
  (CSV jej nie niesie) — jeśli instrument jej nie ma, aplikacja o nią zapyta przy imporcie.
  **Punkty z CSV są chronione** — automatyczny backfill/refresh (yfinance) ich nie nadpisze,
  więc nie trzeba ich wgrywać ponownie po każdym odświeżeniu (re-import nadpisuje, gdy chcesz).
- **Świeżość cen** — przy każdej pozycji znacznik „kiedy ostatnia cena" (dziś / wczoraj /
  N dni temu); gdy notowanie się starzeje (np. yfinance milczy dla danego waloru) — ⚠️
  ostrzeżenie sygnalizujące, że czas na ręczny import CSV.
- **Zysk całkowity** = niezrealizowany (otwarte pozycje) **+** zrealizowany (ze sprzedaży).
- **Konto gotówkowe** — ręczne wpłaty/wypłaty; saldo nettowane przepływami z transakcji
  (kupno −, sprzedaż +). Wartość konta = wycena ETF + gotówka.
- **Wykres wartości konta w czasie** z porównaniem do **dwóch benchmarków** (oba
  money-weighted), każdy z osobnym przełącznikiem włącz/wyłącz:
  1. **stała stopa roczna** (konfigurowalna, np. 5%),
  2. **inflacja + X%** — realny indeks inflacji (Eurostat HICP dla Polski, miesięczny)
     powiększony o konfigurowalną premię (np. inflacja +2%); pokazuje, czy portfel bije
     wzrost cen, a nie tylko arbitralny próg.

  Plus **przełącznik trybu**: wartość konta (PLN) lub stopa zwrotu (%) vs benchmarki w %.
- **XIRR i TWR** — roczny zwrot money-weighted (z timingiem wpłat) **oraz** time-weighted
  (wynik samego portfela, niezależny od timingu). Różnica = wpływ timingu Twoich dopłat.
- **Zwroty w okresach** — pasek 1M / 3M / YTD / 1R / od początku: TWR skumulowany (faktyczny
  wynik portfela w danym okresie, timing-neutralny) + XIRR roczny dla każdego okresu. „Ile w tym
  roku" jednym rzutem oka.
- **Obsunięcie (drawdown)** — wykres „pod wodą" pokazujący spadek od ostatniego szczytu, liczony
  na **indeksie wzrostu TWR** (flow-neutral) — wpłaty IKE nie maskują spadków, a wypłaty nie udają
  obsunięć. Podsumowanie: max drawdown (z datami szczytu/dołka i datą odbicia) oraz bieżące
  obsunięcie. Czytelny obraz ryzyka portfela, spójny z TWR i zwrotami okresowymi.
- **Alokacja docelowa** — przypisz ETF-om kategorie (akcje/obligacje/…), ustaw wagi modelu
  (np. 60/40) i porównaj docelowy vs rzeczywisty udział grup z kwotą do rebalansu (gotówka
  liczona jako osobna grupa); wykres **donut** obok tabeli pokazuje rzeczywisty rozkład grup.
- **Struktura według walorów** — na Pulpicie przełączaj między kategoriami a poziomym
  wykresem największych pozycji, pozostałych aktywów i gotówki. Widok pokazuje udział
  procentowy oraz koncentrację w trzech największych walorach; kliknięcie otwiera szczegóły.
- **Planowanie nowej wpłaty** — symulator dzieli wskazaną kwotę pomiędzy niedoważone klasy,
  zachowuje docelową gotówkę i nie sugeruje sprzedaży istniejących pozycji.
- **Kontrola jakości danych** — automatycznie wykrywa brakujące i stare ceny, kursy FX,
  nieskonfigurowane instrumenty, brak kategorii, niepełny model alokacji, sprzedaż ponad stan
  oraz niespójność transakcji z księgą gotówki.
- **Atrybucja wyniku** — pokazuje zrealizowany i niezrealizowany wynik według instrumentów
  i klas aktywów, udział w łącznym wyniku, historię wpłat oraz aktywność inwestycyjną.
- **Zmiany dzienne** — tabela zysku/straty dzień-po-dniu (wynik rynkowy ETF, z odjętym kosztem
  kupna/sprzedaży, więc zakup nie liczy się jako zysk) z eksportem do CSV.
- **Historia transakcji** — wyszukiwanie i filtrowanie kupna/sprzedaży, edycja zapisanej
  operacji oraz opcjonalne notatki i prowizje.
- **Mapowanie ISIN → ticker** ręcznie w UI (z wstępnym seedem dla znanych instrumentów);
  edytowalna **nazwa własna** instrumentu (np. `PZU World` zamiast `ETFPZUWORLD` z importu) —
  nazwa z importu zapisana osobno (`imported_name`) i widoczna read-only obok; rename
  przetrwa każdy kolejny import (idempotentny).
- **Eksport, backup i restore** — nocna kopia SQLite oraz backup na żądanie, kontrola
  integralności i schematu, SHA-256, status wieku ostatniej kopii, pobieranie konkretnych
  backupów i odtwarzanie z pliku lub kopii serwerowej. Przed każdym restore aplikacja
  automatycznie zapisuje aktualną bazę jako `portfolio-pre-restore-…`.
- **Codzienne odświeżanie** cen i kursów (cron APScheduler, domyślnie ~21:00 Europe/Warsaw) —
  pobiera bieżące notowania i **dociąga ewentualne luki w historii** (np. po awarii sieci),
  zawsze od ostatniego dnia w cache, nigdy całości od początku. Odpytuje **tylko aktualnie
  trzymane** walory (saldo > 0) — sprzedany do zera ETF nie jest już pobierany ani nie zaśmieca
  bazy nowymi punktami (jego historia z okresu posiadania zostaje w cache).

## Interfejs aplikacji

Interfejs celowo rozdziela codzienne sprawdzanie portfela od operacji administracyjnych:

| Sekcja | Zawartość |
|---|---|
| **Pulpit** | łączna wartość konta, wynik całkowity, ostatnia zmiana, TWR, XIRR, gotówka, główny wykres, przełączana struktura kategorii/walorów i największe pozycje z udziałami |
| **Portfel** | pełna tabela otwartych pozycji, koszt, wartość, zysk niezrealizowany i zrealizowany oraz konto gotówkowe |
| **Aktywność** | ręczne dodawanie i edycja transakcji, notatki, filtry, historia kupna/sprzedaży i dzienne zmiany wartości |
| **Alokacja** | rzeczywisty i docelowy udział kategorii, odchylenie, kwota rebalansu oraz plan podziału nowej wpłaty bez sprzedaży |
| **Analiza** | atrybucja wyniku według ETF-ów i klas, wpłaty, zgodność z planem, stopy zwrotu, benchmarki i drawdown |
| **Dane i ustawienia** | kontrola jakości danych, odświeżanie wycen, backfill historii, HICP, mapowanie instrumentów, import, eksport i backup |

Najważniejsze operacje mają własne komunikaty postępu i błędów. Usunięcie transakcji albo
operacji gotówkowej wymaga potwierdzenia. Bieżąca sekcja jest zapisana w parametrze `tab`
adresu URL, więc działają przyciski Wstecz/Dalej i bezpośrednie odnośniki do widoków.

## Kluczowe koncepcje

Zrozumienie tych założeń wyjaśnia, dlaczego liczby wychodzą tak, a nie inaczej:

- **Koszt nabycia jest już w PLN.** Broker rozlicza zakupy w złotówkach, więc cost basis
  bierzemy wprost z importu — bez żadnych przeliczeń walutowych.
- **P/L w PLN łapie i instrument, i walutę.** Bieżąca wartość = `cena_natywna × ilość × kurs_NBP`.
  Ponieważ koszt jest w PLN, a wartość liczona w PLN, różnica automatycznie zawiera zarówno
  ruch ceny instrumentu, jak i ruch kursu waluty — czyli realny zwrot inwestora złotówkowego.
- **Zrealizowany vs niezrealizowany.** Przy każdej sprzedaży liczony jest zrealizowany zysk
  (`przychód − średni_koszt × sprzedana_ilość`). Pozycje sprzedane do zera znikają z listy,
  ale ich zysk wlicza się do zysku całkowitego.
- **Średni koszt (nie FIFO).** Sprzedaż redukuje koszt pozycji po średniej cenie nabycia.
- **Gotówka jest opcjonalna.** Dopóki nie dodasz żadnej wpłaty, konto gotówkowe jest
  „nieaktywne" (saldo 0, wartość konta = sama wycena ETF) — żeby nie pokazywać mylącego
  ujemnego salda z samych zakupów. Po pierwszej wpłacie ledger się aktywuje.
- **Benchmark jest money-weighted.** Nie jest płaską linią — każda wpłata jest oprocentowana
  stałą stopą od swojej daty, więc benchmark „skacze" przy wpłatach tak jak Twój portfel,
  a różnica między liniami to czysta różnica stóp zwrotu (a nie efekt dokładania kapitału).

## Stack technologiczny

| Warstwa | Technologia | Po co |
|---|---|---|
| Backend | **FastAPI** + Uvicorn | REST API + serwowanie frontendu |
| Baza | **SQLite** (wbudowany `sqlite3`, bez ORM) | trwałość, zero zależności (ważne na Python 3.14) |
| Wyceny | **yfinance** (Yahoo Finance) | ceny ETF-ów; pokrywa Xetra `.DE`, LSE `.L`, GPW `.WA` |
| Wyceny (ratunek) | **import CSV** | dla papierów bez pokrycia w yfinance (niszowy GPW) — stooq jako live-source jest martwy (antybot PoW) |
| Kursy walut | **NBP API** (tabela A) | darmowe, oficjalne, bez klucza |
| Harmonogram | **APScheduler** | dzienne odświeżanie w tle |
| HTTP klient | **httpx** | zapytania do NBP |
| Frontend | **React** + **Vite** + **Recharts** | jasny wealth cockpit, wykresy, responsywny desktop/mobile |
| Konteneryzacja | **Docker** (multi-stage, multi-arch arm64+amd64) | self-hosting |

Źródła danych:

| Dane | Źródło |
|---|---|
| Wyceny instrumentów | [yfinance](https://github.com/ranaroussi/yfinance); ratunek dla papierów spoza pokrycia Yahoo: import CSV (format stooq) |
| Kursy walut | [NBP API](https://api.nbp.pl) (tabela A, darmowe, bez klucza) |
| Inflacja (benchmark) | [Eurostat HICP](https://ec.europa.eu/eurostat) (`prc_hicp_midx`, miesięczny, PL, darmowe, bez klucza) — GUS BDL ma CPI tylko rocznie/kwartalnie, więc dla rozdzielczości miesięcznej używamy HICP |

## Uruchomienie

### Docker (zalecane)

Obraz na [Docker Hub](https://hub.docker.com/r/kpa90/portfolio-tracker) (multi-arch: arm64 + amd64).

```bash
docker compose up -d
```

Aplikacja: <http://localhost:8000>. Baza SQLite trwała w named volume `portfolio_tracker_data`.

### Lokalnie (dev)

Backend:
```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Frontend (osobny terminal — Vite proxuje `/api` na backend `:8000`):
```bash
cd frontend
npm install && npm run dev
```

Inny backend deweloperski można wskazać przez
`VITE_API_TARGET=http://127.0.0.1:8001 npm run dev`.

## Konfiguracja

Zmienne środowiskowe (ustawiane w `docker-compose.yml`):

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `TZ` | `Europe/Warsaw` | strefa czasowa (harmonogram crona) |
| `REFRESH_HOUR` | `21` | godzina dziennego odświeżania cen/kursów |
| `REFRESH_MINUTE` | `0` | minuta dziennego odświeżania |
| `BACKUP_HOUR` / `BACKUP_MINUTE` | `3` / `0` | pora nocnego backupu bazy |
| `BACKUP_DIR` | `<dir bazy>/backup` | katalog kopii zapasowych |
| `BACKUP_KEEP` | `14` | ile ostatnich kopii trzymać (retencja) |
| `BACKUP_STALE_HOURS` | `36` | po ilu godzinach bez poprawnej kopii UI pokazuje ostrzeżenie |
| `DB_PATH` | `/app/data/portfolio.db` | ścieżka pliku bazy SQLite |

## Sposób użycia

1. Otwórz **Dane i ustawienia → Import transakcji** i wgraj eksport historii rachunku.
   Powstaną transakcje oraz instrumenty; znane ISIN-y dostaną ticker automatycznie.
2. W **Dane i ustawienia → Instrumenty** uzupełnij ticker lub kategorię pozycji oznaczonych
   jako wymagające konfiguracji. Waluta zostanie wykryta przy pobieraniu ceny.
3. W **Dane i ustawienia → Źródła danych** wybierz **Odśwież**, aby pobrać bieżące wyceny
   z Yahoo Finance i kursy NBP.
4. Przy pierwszym uruchomieniu wybierz **Uzupełnij** przy pełnej historii. Backfill pobierze
   dzienne ceny i kursy od pierwszej transakcji, zasilając wykresy i miary ryzyka.
5. W sekcji **Portfel → Konto gotówkowe** dodaj wpłaty i wypłaty. Dzięki temu wartość konta,
   XIRR i benchmarki uwzględnią niezainwestowaną gotówkę oraz timing przepływów.
6. Opcjonalnie pobierz HICP w **Dane i ustawienia**, aby uruchomić benchmark
   „inflacja + X%". Ta operacja nie dotyka tabeli cen i nie nadpisuje ręcznych importów.
7. Na co dzień korzystaj z **Pulpitu**; szczegółowe TWR, XIRR, benchmarki i drawdown są
   zebrane w sekcji **Analiza**.

## Architektura

```
portfolio-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI: wszystkie endpointy + serwowanie frontendu, lifespan crona
│   │   ├── db.py          # SQLite: połączenie, schemat (CREATE TABLE IF NOT EXISTS), sesje
│   │   ├── importer.py    # parsing CSV (CP1250, ';', przecinek, K/S), dedup po import_hash
│   │   ├── instruments.py # tworzenie instrumentów z importu, seed ISIN→ticker, edycja mapowań
│   │   ├── prices.py      # provider yfinance + import cen z CSV (ratunek), auto-detekcja waluty (GBx→GBP), cache
│   │   ├── fx.py          # klient NBP + cache fx_rates, lookback na weekendy/święta
│   │   ├── cpi.py         # klient Eurostat HICP + cache cpi_index (inflacja pod benchmark)
│   │   ├── portfolio.py   # agregacja pozycji (średni koszt), wycena, P/L (zreal. + niezreal.)
│   │   ├── cash.py        # księga gotówki: saldo, wpłaty/wypłaty, przepływy z transakcji
│   │   ├── allocation.py  # alokacja docelowa vs rzeczywista (grupy, rebalans)
│   │   ├── summary.py     # digest pod powiadomienia/n8n (wartość, P/L, zwroty, alokacja vs cel)
│   │   ├── history.py     # backfill cen/kursów, seria wartości w czasie, benchmarki, XIRR
│   │   ├── returns.py     # czyste XIRR (Newton + bisekcja) i TWR (łańcuch podokresów)
│   │   ├── backup.py      # backup/restore SQLite, walidacja, retencja i eksport CSV
│   │   └── scheduler.py   # APScheduler — odświeżanie cen/FX (~21:00) + nocny backup (~03:00)
│   └── tests/             # pytest (+ sample_hisPW.csv — fikcyjne dane testowe)
├── frontend/              # Vite + React + Recharts (build serwowany przez FastAPI z /frontend/dist)
│   └── src/
│       ├── App.jsx        # shell, routing przez ?tab=, stan, ładowanie danych, akcje i sześć widoków aplikacji
│       ├── components/    # tabele, formularze, wykresy, alokacja, backup i modal instrumentu
│       ├── format.js      # wspólne helpery formatujące (fmtPln, fmtPct, cls, fmtDate)
│       ├── api.js         # cienki klient REST + czytelne błędy zwracane przez backend
│       └── styles.css     # tokeny UI, jasny motyw + ciemny sidebar, layout i breakpointy mobilne
├── Dockerfile            # multi-stage: build frontendu (node) → obraz Pythona z backendem
└── docker-compose.yml
```

**Przepływ danych:** `import CSV → transactions + instruments + cash_flows` →
`refresh/backfill → prices + fx_rates (cache)` → `portfolio/history → wycena w PLN, P/L, XIRR, benchmark`.

## Model danych

SQLite, 7 tabel (schemat w `backend/app/db.py`):

| Tabela | Klucz | Zawartość |
|---|---|---|
| `instruments` | `isin` | nazwa, `ticker`, `currency` (EUR/USD/GBP/PLN), `source` (yfinance/csv), `category`, `needs_config` |
| `target_allocation` | `category` | docelowy udział grupy (`weight_pct`) |
| `transactions` | `id` | `ts`, `isin`, `type` (BUY/SELL), `quantity`, `price_pln`, `value_pln`, `commission_pln`, `note`, `import_hash` (unikalny — dedup) |
| `prices` | (`isin`,`date`) | cena dzienna w walucie natywnej (cache) |
| `fx_rates` | (`date`,`currency`) | kurs do PLN z NBP (cache) |
| `cpi_index` | `month` | miesięczny indeks inflacji HICP (Eurostat, baza 2015=100) — cache pod benchmark „inflacja + X%" |
| `cash_flows` | `id` | `ts`, `kind` (deposit/withdrawal/buy/sell), `amount_pln` (znak = wpływ na saldo) |

Pozycje nie są materializowane — liczone w locie z `transactions` (chronologicznie, średni koszt).

## Jak działa wycena (logika finansowa)

- **Auto-detekcja waluty** (`prices.py`): przy pobraniu ceny z yfinance czytamy `fast_info.currency`
  i synchronizujemy `instruments.currency`. Londyńskie pensy (`GBp`/`GBx`) normalizujemy do GBP
  (cena / 100). Dzięki temu wystarczy zmapować ticker — waluta i kurs dobiorą się same.
- **Kurs NBP** (`fx.py`): tabela A, z lookbackiem (NBP nie publikuje kursów w weekendy/święta →
  bierzemy ostatni dostępny). Wyniki cache'owane w `fx_rates`. PLN → kurs 1.0.
- **Pozycje i P/L** (`portfolio.py`): średni koszt; `wartość = cena × ilość × kurs`;
  niezrealizowany = wartość − koszt; zrealizowany akumulowany przy sprzedażach.
- **Historia** (`history.py`): dla każdego dnia od pierwszej transakcji liczona suma
  `ilość_w_tym_dniu × cena_hist × kurs_hist` z forward-fill (dni bez notowań wypełnia ostatnia
  wartość). Gdy są wpłaty — doliczane jest saldo gotówki (pełna wartość konta).
- **Benchmarki** (`history.py`) — dwa, oba money-weighted (każda wpłata oprocentowana od swojej daty):
  - stała stopa: `Σ wpłat × (1 + stopa)^(lata_od_wpłaty)`;
  - inflacja + X%: `Σ wpłat × (indeks_HICP_dziś / indeks_HICP_wpłata) × (1 + X)^(lata)` — realny
    wzrost cen (Eurostat, interpolacja liniowa między miesiącami) powiększony o premię X. Bez
    danych CPI w cache pola benchmarku inflacyjnego = `null` (linia się nie pokazuje).
- **XIRR** (`returns.py`): money-weighted; przepływy zewnętrzne (wpłata −, wypłata +) +
  wartość końcowa konta. Bez wpłat — fallback na przepływy z transakcji. Newton z fallbackiem na bisekcję.

## API

| Metoda | Ścieżka | Opis |
|---|---|---|
| `POST` | `/api/import` | import CSV (multipart `file`) |
| `POST` | `/api/prices/import` | import dziennych cen waloru z CSV (multipart `isin` + `file` + opcjonalnie `currency`, format stooq) — ratunek, gdy Yahoo nie ma historii; waluta wymagana do wyceny |
| `GET` | `/api/portfolio?refresh=false` | pozycje + sumy (wartość, P/L zreal./niezreal., gotówka, XIRR, TWR, zwroty w okresach) |
| `GET` | `/api/summary` | zwięzły digest (wartość, P/L, zmiana D/D, zwroty, alokacja vs cel) — pod powiadomienia/n8n |
| `GET` | `/api/history?benchmark_rate=0.05&cpi_spread=0.02` | dzienna seria `value_pln` + dwa benchmarki: `benchmark_pln` (stała stopa) i `benchmark_cpi_pln` (inflacja HICP + `cpi_spread`); + warianty `_pct` |
| `GET` | `/api/daily-changes` | dzienny zysk/strata (zmiana wyceny ETF D/D, koszt transakcji odjęty; zakup nie liczy się jako zysk) |
| `GET` | `/api/drawdown` | obsunięcie portfela (drawdown) na indeksie TWR: krzywa „pod wodą" + max/bieżące DD z datami szczytu/dołka/odbicia |
| `GET` / `POST` | `/api/transactions` | historia transakcji / ręczne dodanie |
| `PUT` | `/api/transactions/{id}` | edycja transakcji i odtworzenie powiązanego ruchu gotówkowego |
| `DELETE` | `/api/transactions/{id}` | usunięcie transakcji (i jej przepływu gotówki) |
| `GET` | `/api/data-quality` | kontrola kompletności cen, FX, konfiguracji, alokacji i spójności księgi |
| `GET` | `/api/analytics` | atrybucja wyniku, klasy aktywów, instrumenty, wpłaty i aktywność |
| `POST` | `/api/allocation/plan` | symulacja podziału nowej wpłaty bez sprzedaży |
| `GET` | `/api/instruments/{isin}/history` | dzienna historia waloru (cena natywna, kurs, PLN, ilość) |
| `GET` / `PUT` | `/api/allocation` | alokacja docelowa vs rzeczywista (grupy + gotówka) |
| `GET` / `PUT` | `/api/instruments[/{isin}]` | podgląd / edycja mapowań ISIN→ticker + nazwa własna + kategoria |
| `GET` | `/api/cash` | saldo gotówki + lista wpłat/wypłat |
| `POST` / `DELETE` | `/api/cash[/{id}]` | dodaj / usuń wpłatę-wypłatę |
| `POST` | `/api/refresh` | odświeżenie bieżących cen i kursów + dociągnięcie luk w historii (od ostatniego dnia w cache) |
| `POST` | `/api/backfill` | pełna historia cen i kursów od pierwszej transakcji |
| `POST` | `/api/cpi/refresh` | pobranie serii inflacji (Eurostat HICP) pod benchmark „inflacja + X%" — **niezależne od cen** (nie dotyka tabeli `prices`, bezpieczne dla walorów z importu CSV) |
| `GET` | `/api/export/transactions.csv` | pobranie transakcji jako CSV |
| `GET` | `/api/export/daily-changes.csv` | pobranie dziennych zmian wartości jako CSV |
| `GET` | `/api/export/db` | pobranie całej bazy SQLite (spójna kopia) |
| `GET` / `POST` | `/api/backups` / `/api/backup-now` | status ochrony, lista kopii / zweryfikowany backup na żądanie |
| `GET` | `/api/backups/{file}/download` | pobranie konkretnej kopii z bezpieczną walidacją nazwy |
| `POST` | `/api/backups/{file}/restore` | odtworzenie kopii serwerowej po potwierdzeniu `PRZYWRÓĆ` |
| `POST` | `/api/backups/restore-upload` | walidacja i odtworzenie przesłanego pliku SQLite |

### Dokumentacja API (generowana z kodu)

FastAPI udostępnia żywą dokumentację wszystkich endpointów — zawsze zgodną z kodem,
bez ręcznej aktualizacji:

| Strona | URL | Do czego |
|---|---|---|
| **Swagger UI** | `http://localhost:8000/docs` | interaktywna (klikalne „Try it out"), generowana z kodu |
| **ReDoc** | `http://localhost:8000/redoc` | ładniejsza do czytania, też z kodu |
| **OpenAPI JSON** | `http://localhost:8000/openapi.json` | maszynowy schemat — idealny do importu w n8n (node „HTTP Request" / Import OpenAPI) |

## Format pliku CSV

Obsługiwane są dwa automatycznie rozpoznawane eksporty.

Eksport „historia PW” z biura maklerskiego:

- kodowanie **CP1250** (Windows-1250), separator `;`, liczby z **przecinkiem dziesiętnym**;
- kolumny (po pozycji): `data; papier; isin; ilość; [K/S]; cena; wartość; prowizja; po prowizji; waluta`;
- `K` = kupno (BUY), `S` = sprzedaż (SELL); data `DD.MM.YYYY HH:MM:SS`.

Eksport eMAKLER „Transakcje bieżące”:

- parser pomija preambułę zawierającą dane rachunku i odnajduje tabelę po nagłówku;
- kolumny tabeli: `Czas transakcji;Papier;Giełda;K/S;Liczba;Kurs;Waluta;Wartość;Waluta`;
- raport nie zawiera ISIN-u, dlatego para papier + giełda jest mapowana jawnie do zweryfikowanego
  instrumentu; nierozpoznany papier przerywa cały import z czytelnym błędem;
- `Wartość` w PLN jest pełnym kosztem transakcji, a jednostkowe `price_pln` jest wyliczane jako
  wartość / liczba. Prowizja jest zapisywana jako zero.

Przykład struktury: `backend/tests/sample_hisPW.csv` (fikcyjne dane). Prawdziwe eksporty są
celowo wykluczone z repo (`.gitignore`), bo zawierają dane osobiste.

## Prywatność i bezpieczeństwo danych

- Aplikacja jest **jednoużytkownikowa** i nie ma wbudowanego logowania. Uruchamiaj ją w
  zaufanej sieci lokalnej albo za prywatnym tunelem/VPN.
- Produkcyjna baza znajduje się w named volume Dockera `portfolio_tracker_data`, poza
  repozytorium Git. Lokalny wariant `data/portfolio.db` również jest ignorowany.
- `.gitignore` wyklucza katalog `data/`, bazy `*.db`, `*.sqlite`, `*.sqlite3`, pliki
  dziennika SQLite (`-wal`, `-shm`, `-journal`), prawdziwe eksporty `*.csv`, pliki `.env`,
  środowiska Pythona, zależności Node i katalogi buildów.
- `.dockerignore` stosuje te same zabezpieczenia dla kontekstu budowania obrazu, dlatego
  lokalna baza, eksporty brokera i pliki środowiskowe nie są wysyłane do buildera Dockera.
- Jedynym śledzonym CSV jest `backend/tests/sample_hisPW.csv`; zawiera wyłącznie fikcyjne
  dane testowe i jest jawnie dopuszczony wyjątkiem w `.gitignore`.
- Zrzuty ekranu w dokumentacji korzystają z odseparowanej bazy demonstracyjnej. Mogą
  prezentować publiczne nazwy i identyfikatory prawdziwych ETF-ów, ale transakcje, ceny,
  daty, kwoty i wyniki muszą pozostać syntetyczne. Nie należy commitować screenshotów
  wykonanych na prywatnej bazie.
- Backup w aplikacji tworzy spójną kopię SQLite wewnątrz wolumenu. Kopię poza serwer można
  pobrać przez **Dane i ustawienia → Backup i eksport → Pobierz całą bazę**.
- Każdy backup jest sprawdzany przez `PRAGMA integrity_check`, obecność wymaganych tabel
  i sumę SHA-256. Restore odrzuca pusty, uszkodzony lub obcy plik, a przed zastąpieniem
  aktywnej bazy zawsze tworzy automatyczną kopię bezpieczeństwa.

### Jak sprawdzić backup i odtwarzanie

1. Otwórz **Dane i ustawienia → Backup i eksport** i kliknij **Utwórz backup teraz**.
2. Sprawdź, czy panel pokazuje „Ostatnia poprawna kopia”, potwierdzoną integralność,
   liczbę transakcji i skrót SHA-256.
3. Pobierz utworzoną kopię przyciskiem **Pobierz** i przechowaj ją także poza named volume
   (np. na zaszyfrowanym dysku lub w prywatnym magazynie plików).
4. Test restore wykonuj dopiero po pobraniu bieżącej bazy. Wybierz kopię i kliknij
   **Przywróć** albo użyj **Przywróć z pliku .db**, a następnie wpisz dokładnie
   `PRZYWRÓĆ`. Aplikacja najpierw utworzy kopię `portfolio-pre-restore-…`.
5. Po odtworzeniu sprawdź Pulpit, liczbę transakcji i najnowsze wyceny. Kopię
   `portfolio-pre-restore-…` pozostaw do czasu potwierdzenia, że dane są poprawne.

Kopie w `portfolio_tracker_data` chronią przed błędem aplikacji lub przypadkową edycją,
ale nie przed utratą całego hosta/wolumenu. Co najmniej jedna aktualna kopia powinna być
regularnie pobierana poza serwer.

## Testy

```bash
cd backend && .venv/bin/python -m pytest
```

Testy są deterministyczne i nie wymagają sieci (ceny/kursy wstrzykiwane ręcznie, import na
`sample_hisPW.csv`). Pokrywają m.in.: parsing i idempotencję importu, edycję transakcji,
średni koszt, zrealizowany zysk, księgę gotówki, analitykę, kontrolę jakości danych,
planowanie nowej wpłaty, XIRR oraz tworzenie, walidację i odtwarzanie backupu.

## Jak rozbudować

Najczęstsze kierunki rozwoju i gdzie ich szukać:

- **Realny benchmark ETF** (np. MSCI ACWI) — wzorem benchmarku inflacyjnego (`cpi.py` +
  `history.portfolio_history`): pobierz serię cen przez `prices.py` i zamiast `(1+stopa)^lata`
  użyj `cena_ETF(dzień)/cena_ETF(data_wpłaty)`. Benchmark „inflacja + X%" (Eurostat HICP) jest
  już zrobiony w ten sposób — najłatwiej dorobić trzeci benchmark kopiując ten wzorzec.
- **FIFO / realizowany zysk per instrument** — rozszerz pętlę w `portfolio.compute_positions`
  (obecnie średni koszt) o kolejkę lotów; zwracaj rozbicie zrealizowanego zysku po ISIN.
- **Dywidendy / podatki** — dodaj typy w `cash_flows` (`dividend`, `tax`) i obsłuż je w imporcie
  oraz w `cash.balance`; uwzględnij w XIRR jako przepływy.
- **Nowy format importu** (inny broker) — dodaj parser w `importer.py` z auto-detekcją po nagłówku;
  mapuj do tego samego modelu (`transactions` + `instruments` + `cash_flows`).
- **Kolejne źródło cen** — dodaj funkcje `_xxx_last` / `_xxx_hist` w `prices.py` i obsłuż nową
  wartość `source`; reszta (cache, wycena) bez zmian.
- **Powiadomienia / eksport** — dorzuć endpoint w `main.py` i zadanie w `scheduler.py`.

---

Stack: FastAPI + SQLite + yfinance · frontend React/Recharts · Docker multi-arch (arm64 + amd64).
