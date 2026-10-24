---
version: 1
slug: "frontend-src-app-jsx"
primary_target: "frontend/src/App.jsx"
related_targets: ["frontend/src/styles.css"]
---

# Aplikacja Portfolio (cała SPA)

Mode: Operate. Jeden obeznany inwestor; szybki rzut oka (często telefon), dodanie transakcji, okresowy przegląd. Alokacja i konfiguracja rzadko. Odrzucone: platforma tradingowa, aplikacja bankowa, „aplikacja dla dziecka” (kolorowe bloki), styl redakcyjny ze zdaniami-wnioskami i wielką typografią (zbudowany i odrzucony 2026-10-24: „te teksty są niepotrzebne”).

## Direction contract

THESIS: Standard kategorii wykonany starannie — przewidywalny tracker: górne menu, rząd kart z liczbami, wykres, tabele. Odrzuca boczne menu, zdania-wnioski i ozdobniki.

OWN-WORLD: Jasnoszare tło (#f5f6f8), białe karty z 1px ramką i promieniem 12px, jeden niebieski akcent (#2563eb) dla akcji i serii portfela, zieleń/czerwień tylko dla zysku/straty. Systemowy krój, 14px treść, KPI 26px z cyframi tabelarycznymi. Tryb ciemny: grafit #0c0e12 / karty #15191f, akcent tekstu #7ea3ff.

STORY: Wchodzisz i w rzędzie kart widzisz wartość, zysk od początku, ostatnią sesję i przewagę nad inflacją; niżej wykres i największe pozycje. Reszta pod pięcioma pozycjami menu.

FIRST VIEWPORT: Pasek: logo, Przegląd/Portfel/Historia/Raporty/Ustawienia (pigułka dla aktywnej), wybór konta, „Dodaj”. Tytuł strony + „Wyceny z …” i status danych, przycisk „Odśwież wyceny”. Cztery karty KPI. Siatka 2:1 — karta „Wartość w czasie” i karta „Największe pozycje”.

FORM: Standard kategorii (canon, wybrany przez użytkownika po odrzuceniu Raportu rocznego). seed:d1e99d0dad4e6e35.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
