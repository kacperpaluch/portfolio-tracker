---
name: Portfolio
description: Prywatny tracker portfela — standard kategorii wykonany starannie, mówi liczbami i etykietami.
colors:
  accent: "#2563eb"
  accent-hover: "#1d4ed8"
  accent-ink: "#ffffff"
  accent-soft: "#eef3ff"
  pos: "#067647"
  neg: "#d92d20"
  warn: "#b54708"
  bg: "#f5f6f8"
  surface: "#ffffff"
  surface-2: "#f6f7f9"
  border: "#e4e7ec"
  border-strong: "#d0d5dd"
  text: "#101828"
  text-2: "#344054"
  muted: "#667085"
  series-portfolio: "#2563eb"
  series-benchmark: "#c27803"
  series-cpi: "#7c3aed"
  series-cost: "#98a2b3"
  series-loss: "#d92d20"
typography:
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 650
    letterSpacing: "-0.02em"
  kpi:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, sans-serif"
    fontSize: "1.625rem"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.02em"
    fontFeature: "tnum"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, sans-serif"
    fontSize: "1rem"
    fontWeight: 650
  stat:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 650
    fontFeature: "tnum"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 500
  table-head:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    letterSpacing: "0.02em"
rounded:
  focus: "4px"
  control: "8px"
  card: "12px"
  pill: "99px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  2xl: "24px"
  3xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-2}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "36px"
  button-secondary-hover:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.text}"
  button-small:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-2}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 10px"
    height: "30px"
  button-text:
    textColor: "{colors.accent}"
    height: "28px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "0 10px"
    height: "36px"
  nav-item:
    textColor: "{colors.muted}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "36px"
  nav-item-active:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent}"
  tab:
    textColor: "{colors.muted}"
    height: "40px"
  tab-active:
    textColor: "{colors.accent}"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.card}"
    padding: "20px 24px"
  kpi:
    backgroundColor: "{colors.surface}"
    typography: "{typography.kpi}"
    rounded: "{rounded.card}"
    padding: "18px 20px"
  stat-tile:
    backgroundColor: "{colors.surface-2}"
    typography: "{typography.stat}"
    rounded: "{rounded.control}"
    padding: "12px 14px"
  chip-preset:
    textColor: "{colors.text-2}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 12px"
    height: "32px"
  chip-preset-active:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent}"
  modal:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.card}"
    padding: "24px"
    width: "960px"
---

# Design System: Portfolio

## Overview

**Creative North Star: "Standard kategorii, wykonany starannie"**

Portfolio wygląda jak tracker, którego użytkownik się spodziewa: górny pasek z pięcioma sekcjami, nagłówek strony, rząd kart z liczbami, wykres i tabele. Nowość nie leży w formie, tylko w wykonaniu — równe odstępy, cyfry tabelaryczne, jedna niebieska barwa akcji, zieleń i czerwień tylko przy wyniku. Interfejs mówi liczbami i etykietami, nie zdaniami.

Gęstość jest umiarkowana: strona startowa odpowiada na „ile mam i jak idzie” czterema kartami KPI i siatką 2:1 (wykres + największe pozycje); gęstsze tabele i kafle pojawiają się dopiero w sekcjach analitycznych. Powierzchnie są płaskie: jasnoszare tło, białe karty z jednopikselową ramką i prawie niewidocznym cieniem. Tryb ciemny idzie za ustawieniem systemu; wydruk raportu jest zawsze jasny.

Odrzucone przez użytkownika (2026-10-24): styl redakcyjny ze zdaniami-wnioskami i wielką typografią, kolorowe bloki sekcji, boczne menu.

**Key Characteristics:**
- Jasnoszare tło, białe karty 12px z ramką 1px, cień tylko 1px.
- Jeden akcent (niebieski) dla akcji, aktywnej nawigacji i serii portfela.
- Zysk/strata kolorem, zero i przepływy neutralnie.
- Systemowy krój, treść 14px, liczby zawsze tabelaryczne.
- Liczby wyrównane do prawej, tekst do lewej.

## Colors

Chłodna szarość z jednym niebieskim akcentem i semantyczną triadą zysk / strata / ostrzeżenie.

### Primary
- **Niebieski akcji** (accent): przycisk główny „Dodaj”, aktywna pozycja menu (na tle accent-soft), podkreślenie aktywnej zakładki, linki tekstowe, logo, ramka focusu, seria portfela na wykresach. W trybie ciemnym rozdzielony na dwa tokeny: tekst w akcencie `#7ea3ff`, wypełnienie przycisku `--accent-fill` `#3b6fe0` — bo jasny tekst i ciemne wypełnienie nie mogą mieć tej samej wartości przy zachowaniu kontrastu.
- **Niebieski wciśnięty** (accent-hover): hover przycisku głównego i linków tekstowych.
- **Mgiełka akcentu** (accent-soft): tło aktywnej pigułki menu, aktywnego presetu okresu, edytowanego wiersza tabeli, numeru priorytetu w planerze.

### Secondary
- **Zieleń zysku** (pos) / **Czerwień straty** (neg): wartości dodatnie i ujemne (klasy `.pos` / `.neg` przez helper `cls()`), seria strat na wykresach, błędy formularzy (neg), stan „dane w porządku” w plakietkach jakości/kopii (pos, zawsze ze słowem).
- **Bursztyn ostrzeżenia** (warn): nieaktualne wyceny, plakietki ostrzeżeń, wskaźniki problemów z danymi.

### Tertiary
- **Serie wykresów**: benchmark (bursztyn `series-benchmark`), inflacja (fiolet `series-cpi`), koszt/wpłaty (szarość `series-cost`). Wykresy czytają je z CSS przez `useChartColors()`, więc motyw przełącza się bez przeładowania.
- **Paleta kategorii donuta** (tylko alokacja, w `chartTheme.js`): dziesięć stonowanych, średnich tonów czytelnych na obu tłach — jedyne miejsce, gdzie kolor koduje kategorię.

### Neutral
- **Tło strony** (bg) i **karta** (surface): tło za kartami / biel kart, paska i okien.
- **Kafel** (surface-2): tło kafli z liczbami wewnątrz kart, hover wierszy i przycisków, aktywny przełącznik wykresu.
- **Ramka** (border) dla kart, linii tabel i separatorów; **ramka mocna** (border-strong) dla pól, przycisków drugorzędnych, stopki tabeli.
- **Tekst** (text) dla liczb i tytułów; **tekst 2** (text-2) dla etykiet pól i treści drugorzędnej; **wyciszony** (muted) dla podpisów KPI, nagłówków kolumn, osi wykresów i wartości zero.

### Tryb ciemny
Te same role, inne wartości (blok `prefers-color-scheme: dark` w `styles.css`): grafitowe tło `#0c0e12`, karty `#15191f`, kafel `#1c2128`, ramki `#262c35` / `#363e4a`, tekst `#f2f4f7`, zysk `#47cd89`, strata `#f97066`, ostrzeżenie `#fdb022`; `--shadow-xs` wyłączony. Wydruk nadpisuje zmienne z powrotem na jasne.

### Named Rules
**The Zero Is Neutral Rule.** Zero, przepływy (wpłaty, zakupy, rebalans) i brak danych są szare (`muted`/`text`). Zielony i czerwony pojawiają się na liczbie tylko wtedy, gdy znak oznacza wynik.

**The One Blue Rule.** Niebieski znaczy „możesz w to kliknąć” albo „to twój portfel”. Nie służy do dekoracji, nagłówków sekcji ani teł kart.

**The Word Beside the Color Rule.** Kolor statusu (pos/warn/neg w plakietkach jakości, kopii, nieaktualnych wycen) zawsze stoi przy słowie lub liczbie, nigdy sam.

## Typography

**Body Font:** systemowy stos (-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, sans-serif)

**Character:** Jeden krój UI dla wszystkiego, hierarchia niesiona wagą (400 / 500–550 / 600 / 650) i rozmiarem, nie kontrastem krojów. Wybrany świadomie: standard kategorii, natywny wygląd na każdym urządzeniu.

### Hierarchy
- **Headline** (650, 1.5rem, -0.02em): tytuł strony („Przegląd”, „Portfel”); 1.25rem na telefonie.
- **KPI** (650, 1.625rem, lh 1.2, -0.02em, tnum): wartość w kartach KPI; 1.25rem na telefonie. Metryki raportu: 1.375rem.
- **Title** (650, 1rem): tytuł karty. Tytuł okna: 1.25rem.
- **Stat** (650, 1.125rem, tnum): wartości w kaflach wewnątrz kart.
- **Body** (400, 0.875rem, lh 1.5): treść, komórki tabel, pozycje list.
- **Label** (500–600, 0.8125rem, muted): podpisy KPI i kafli, etykiety pól (550, text-2), podpisy pod tytułem strony, małe przyciski.
- **Table head** (600, 0.75rem, +0.02em, muted): nagłówki kolumn; bez wersalików.
- **Logo** (750, 1.125rem, -0.02em, accent): słowo „Portfolio” w pasku.

### Named Rules
**The Tabular Figures Rule.** Każda liczba w tabeli, liście rankingowej, KPI i kaflu ma `font-variant-numeric: tabular-nums`. Kolumny cyfr muszą się zgadzać w pionie.

**The Labels Not Sentences Rule.** Etykieta nad liczbą to rzeczownik („Wartość portfela”, „Ostatnia sesja”), szczegół pod nią to druga liczba („TWR +21,76%”). Bez zdań-wniosków i bez nadtytułów nad nagłówkami.

## Layout

Jedna kolumna treści o maksymalnej szerokości 1280px (`--page`), wyśrodkowana, z marginesem bocznym `clamp(16px, 3vw, 32px)` (`--gutter`), 64px oddechu na dole. Sticky pasek górny 60px nad wszystkim.

Rytm pionowy: nagłówek strony 28px nad / 20px pod, odstęp między kartami i rzędami 20px, wewnątrz karty 16px między nagłówkiem a treścią. Siatki: KPI 4 kolumny (gap 16px), układ `split` 2:1 (gap 20px), kafle liczb w siatkach 2–5 kolumn (gap 12px).

Responsywność: ≤1100px — split w jedną kolumnę, KPI i metryki raportu 2×2, kafle zwrotów 3 kolumny. ≤760px — menu przechodzi do drugiego wiersza paska i przewija się poziomo, zakładki przewijają się poziomo, karty 16px paddingu, formularze na pełną szerokość, tabele przewijają się w poziomie z przyklejoną pierwszą kolumną, pola 16px (bez zoomu iOS), okna prawie pełnoekranowe. Przy `pointer: coarse` każdy cel dotykowy ma min. 44px.

Formatowanie liczb (`format.js`): PLN przez `Intl` `pl-PL`, przecinek dziesiętny, procenty ze znakiem plus, brak wartości jako „—”.

## Elevation & Depth

Płasko, warstwy tonalne. Karta odróżnia się od tła bielą i ramką 1px, nie cieniem; kafle wewnątrz kart schodzą o ton niżej (surface-2) zamiast podnosić się. Prawdziwe uniesienie mają tylko elementy nad stroną: okno modalne i powiadomienie.

### Shadow Vocabulary
- **Spoczynek** (`--shadow-xs`: `0 1px 2px rgba(16, 24, 40, 0.05)`): karty, KPI, przyciski, pola — ledwie widoczny dolny brzeg. W trybie ciemnym `none`.
- **Nad stroną** (`--shadow-lg`: `0 20px 48px rgba(16, 24, 40, 0.18)`; ciemny: alfa 0.55): okno modalne i toast.

### Named Rules
**The No Nested Cards Rule.** Liczby z podpisem wewnątrz karty to szare kafle (surface-2, promień 8px, bez ramki i cienia), nigdy karta w karcie.

## Shapes

Dwa promienie robią całą robotę: 12px dla kontenerów (karta, KPI, okno, toast, karta mapowania), 8px dla kontrolek i kafli (przyciski, pola, pigułki menu, przełączniki wykresu, kafle). Pełna pigułka (99px) dla presetów okresu, plakietek statusu i okrągłych wskaźników zdrowia danych. 4px tylko dla obrysu focusu i `code`. Ramki zawsze 1px; jedyna gruba linia to 2px podkreślenie aktywnej zakładki i pasek ładowania.

## Components

### Buttons
Spokojne, prostokątne, czytelne bez ikon.
- **Shape:** łagodnie zaokrąglone (8px), wysokość 36px, padding 0 14px, waga 600.
- **Primary:** niebieskie wypełnienie, biały tekst, cień spoczynku. Jeden na widok — „Dodaj” w pasku, „Zapisz” w formularzu.
- **Secondary:** białe tło, mocna ramka, tekst text-2; hover — kafel surface-2 i pełny tekst.
- **Small (w tabelach i nagłówkach okien):** jak secondary, 30px, label 0.8125rem, padding 0 10px. Wariant usuwania czerwienieje dopiero na hover.
- **Text button:** sam niebieski tekst 600, bez tła — akcje w nagłówkach kart („Pełna analiza”, „Cały portfel”).
- **Hover / Focus:** zmiana tła 120ms ease-out; focus to 2px obrys w akcencie z odstępem 2px. Disabled: 50% krycia.

### Chips
- **Presety okresu:** pigułka 32px z mocną ramką, label 0.8125rem; aktywna — ramka i tekst w akcencie na mgiełce akcentu.
- **Przełączniki wykresu:** bez ramki, wyciszony tekst; włączony — kafel surface-2 z wewnętrzną ramką 1px. Grupy dzieli pionowa kreska 1px.
- **Plakietki statusu:** pigułka z tłem 12–14% koloru statusu (`color-mix`) i tekstem w tym kolorze, 0.75rem/600.

### Cards / Containers
- **Corner Style:** 12px.
- **Background:** surface, ramka border 1px, cień spoczynku.
- **Internal Padding:** 20px 24px (16px na telefonie); KPI 18px 20px.
- **Nagłówek karty:** tytuł 1rem/650 po lewej, opcjonalna akcja (text button lub mały przycisk) po prawej.

### KPI
Etykieta (label, muted) → wartość (KPI, kolor wg znaku) → szczegół (label, muted). Cztery w rzędzie, nic więcej w karcie.

### Inputs / Fields
- **Style:** 36px, padding 0 10px, mocna ramka, białe tło, promień 8px, cień spoczynku; placeholder wyciszony.
- **Focus:** ramka w akcencie + 3px obrys z 20% akcentu.
- **Error:** czerwony tekst 0.8125rem/600 pod polem, na pełną szerokość wiersza formularza.
- **Etykiety:** nad polem, 0.8125rem/550, text-2, odstęp 6px.

### Navigation
- **Pasek górny:** biały, sticky, dolna ramka 1px; logo, pięć pozycji, po prawej wybór konta i „Dodaj”. Ładowanie: 2px niebieski pasek przesuwający się po dolnej krawędzi (statyczny przy ograniczonym ruchu).
- **Pozycje menu:** 36px, waga 550, wyciszone; hover — kafel i pełny tekst; aktywna — pigułka mgiełki akcentu z niebieskim tekstem.
- **Zakładki wewnątrz strony:** tekst 550 z 2px podkreśleniem w akcencie dla aktywnej, wspólna dolna linia rzędu; nawigacja strzałkami (WAI-ARIA tablist).

### Tables
Liczby do prawej, pierwsza i tekstowe kolumny do lewej; komórki 11px 12px, linie wierszy 1px, bez pionowych linii; hover wiersza na surface-2; stopka z mocną górną linią i wagą 650. Na telefonie poziomy scroll z przyklejoną pierwszą kolumną.

### Modal
Portal do body, tło przyciemnione (`--backdrop`), okno wyrównane do góry (48px), maks. 960px, promień 12px, padding 24px, cień „nad stroną”. Pułapka focusu, Esc zamyka wierzchnie okno, focus wraca do wyzwalacza; formularze nie zamykają się kliknięciem w tło.

### Toast
Prawy dolny róg, karta 12px z cieniem „nad stroną”, wjazd 240ms z 8px w górę (`cubic-bezier(0.16, 1, 0.3, 1)`); błąd — czerwona ramka i tekst.

## Do's and Don'ts

### Do:
- **Do** budować widok z tych samych klocków: nagłówek strony → rząd KPI → karty z tytułem i jedną akcją → tabele.
- **Do** kolorować liczbę przez `cls()` — zero i brak danych zostają wyciszone.
- **Do** dawać każdej liczbie `tabular-nums` i wyrównanie do prawej w kolumnach.
- **Do** brać kolory wykresów z `useChartColors()` / zmiennych `--series-*`, nie wpisywać hexów w komponentach.
- **Do** trzymać promienie 12px (kontenery) / 8px (kontrolki) / pigułka (presety, plakietki).
- **Do** zapewnić 44px celu dotykowego przy `pointer: coarse` dla każdego nowego przycisku.

### Don't:
- **Don't** dodawać zdań-wniosków, nadtytułów ani wielkiej typografii redakcyjnej — odrzucone przez użytkownika.
- **Don't** barwić sekcji ani kart kolorowymi tłami; jedyne tła tonalne to surface-2 i mgiełka akcentu dla stanu aktywnego.
- **Don't** wkładać karty w kartę — wewnątrz karty liczby idą do szarych kafli.
- **Don't** używać zieleni dla wpłat, zakupów ani zera.
- **Don't** dodawać cieni ponad `--shadow-xs` na elementach osadzonych w stronie; `--shadow-lg` tylko dla okien i powiadomień.
- **Don't** wprowadzać bocznego menu — nawigacja to pasek górny i zakładki.
