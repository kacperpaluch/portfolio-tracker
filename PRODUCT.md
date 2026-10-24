# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Jeden inwestor — właściciel instancji. Zna pojęcia TWR, XIRR, drawdown, benchmark; nie potrzebuje
objaśniania podstaw, potrzebuje spokoju i szybkiej orientacji. Kupuje ETF-y i obligacje skarbowe
przez polskie biuro maklerskie (IKE i rachunek zwykły). Projekt jest publiczny na Docker Hub,
ale interfejs projektujemy dla jednego, obeznanego użytkownika.

## Product Purpose

Prywatny, self-hostowany tracker długoterminowego portfela: wartość, zysk/strata (zrealizowany
i niezrealizowany), stopa zwrotu i porównanie z benchmarkiem — wszystko w PLN, z walutami
przeliczonymi kursem NBP. Sukces: użytkownik w kilka sekund wie, jak stoi, a dodanie transakcji
czy comiesięczny przegląd nie wymagają przedzierania się przez konfigurację.

## Positioning

Polski kontekst wbudowany w mechanikę: import z polskich biur (GPW „historia PW”, eMAKLER,
potwierdzenia PDF mBanku), kursy NBP, obligacje detaliczne z tabel MF, szacunek podatku 19%
z rozróżnieniem IKE/IKZE i kont opodatkowanych, benchmark inflacji HICP dla Polski.
Dane zostają u użytkownika (SQLite, bez kont i chmury).

## Operating Context

Potwierdzone sposoby użycia, od najczęstszego:

1. **Szybki rzut oka** — ile mam i jak poszło ostatnio; kilka sekund, często z telefonu.
2. **Po zakupie lub wpłacie** — dodanie transakcji ręcznie albo import pliku z biura maklerskiego.
3. **Okresowy przegląd** — raz w miesiącu/kwartale: wyniki okresu, porównanie z benchmarkiem, raport.

Rzadko używane (mogą zejść na dalszy plan, ale muszą zostać dostępne):

- alokacja docelowa i planer wpłaty,
- dane i konfiguracja: jakość danych, tickery i providerzy, synchronizacja, konta, backupy.

Aplikacja działa w sieci domowej / za VPN, w przeglądarce na desktopie i telefonie.
Motyw jasny i ciemny za ustawieniem systemu; raport drukowany do PDF zawsze jasny.

## Capabilities and Constraints

- Backend FastAPI + SQLite i istniejące API (`frontend/src/api.js`) zostają; zmiana dotyczy warstwy UI.
- Frontend: React 18 + Vite 5 + Recharts 2.
- Wszystkie wartości w PLN; język interfejsu polski.
- Widok całego portfela albo jednego konta (`?account=`), stan sekcji w URL (`?tab=`).
- Funkcje do zachowania: wartość i wynik, TWR/XIRR, historia vs benchmark i inflacja, pozycje,
  widok waloru z atrybucją instrument/waluta, transakcje (dodawanie, import CSV/PDF, edycja, usuwanie),
  gotówka, obligacje, podatek szacunkowy, alokacja i planer, raport okresowy z wydrukiem,
  ryzyko (drawdown), zmiany dzienne, jakość danych, instrumenty/providerzy, konta, backup i przywracanie.
- Przy kwotach i procentach zielony/czerwony oznaczają wyłącznie zysk/stratę; przepływy (wpłaty, zakupy,
  rebalans) i zero są neutralne. W statusach systemu (jakość danych, kopie zapasowe, błędy formularzy) te same kolory oznaczają OK i błąd — zawsze z napisem obok, nigdy jako sam kolor.

## Brand Commitments

Nazwa robocza „Portfolio”. Brak logo.

Wygląd: standard kategorii trackerów — górne menu, karty z liczbami, wykres, tabele — wykonany starannie, bez ozdobników. Użytkownik odrzucił styl redakcyjny ze zdaniami-wnioskami i wielką typografią oraz kolorowe bloki sekcji (2026-10-24). Interfejs ma mówić liczbami i etykietami, nie zdaniami.

## Evidence on Hand

Prawdziwe dane użytkownika w lokalnej bazie (`data/`); brak zrzutów ekranu, referencji wizualnych
i materiałów marki.

## Product Principles

1. **Najpierw odpowiedź, potem szczegóły.** Ekran startowy odpowiada na „ile mam i jak idzie”; analiza jest o krok dalej.
2. **Częstotliwość wyznacza wagę.** To, co robione co tydzień, jest pod ręką; konfiguracja i rzadkie narzędzia nie konkurują o uwagę.
3. **Jedna liczba ma jedno znaczenie.** Kolor, znak i etykieta nie mogą sugerować zysku tam, gdzie go nie ma.
4. **Spokój zamiast kokpitu.** Mniej równoległych kart i liczb; gęstość tylko tam, gdzie użytkownik przyszedł analizować.

## Accessibility & Inclusion

Cel: WCAG 2.2 AA (kontrast, klawiatura w modalach, etykiety pól), pełna funkcjonalność na telefonie.
