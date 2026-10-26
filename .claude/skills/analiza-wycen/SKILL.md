---
name: analiza-wycen
description: Analiza przebiegu wycen (zapytań ofertowych) z pliku analiza_wycen_RRRR-MM-DD.json tworzonego przez `python -m wyceny`. Używaj, gdy użytkownik wkleja lub przesyła ten plik albo pyta o wąskie gardła, czasy faz, konsultacje (przekierowania), cofnięcia, porzucone zadania lub trend realizacji wycen.
---

# Analiza wycen z pliku JSON

> **ZAWSZE odpowiadaj po polsku** – także gdy plik, pytanie albo wcześniejsza rozmowa są po angielsku.
> Nazwy etapów, faz i grup podawaj dokładnie tak jak w pliku.

Plik `analiza_wycen_RRRR-MM-DD.json` powstaje obok raportu Excel (`raporty/`). Zawiera wyłącznie zestawienia
zagregowane i krótkie listy przypadków. Osoby są zastąpione pseudonimami („Osoba 07”) – pseudonimy są stałe
w obrębie jednego pliku, ale **nie** między plikami z różnych dni. Grupy (DS, DTTW, DZ…) i klienci są jawni.

Każdy wniosek opieraj na liczbach z pliku i podawaj je. Nie zgaduj przyczyn biznesowych –
nazwij je hipotezami do sprawdzenia z zespołem.

## Wiedza o procesie (potwierdzona przez zespół – nie przedstawiaj tego jako odkrycia ani problemu)

- **DJ czeka na DTTW.** Wyliczenia DJ bazują na danych DTTW, więc DJ nie zatwierdzi przed DTTW. „Wolny DJ” to zwykle
  wolny DTTW – patrz kolumna „Razy przyczyną” (uwzględnia zależność) i sekcja `zaleznosci_grup`
  („Czas własny po otrzymaniu danych” = realna praca DJ).
- **Cofnięcie z DF-W (kalkulacji finansowej) do tworzenia RFQ jest celowe.** Żeby dodać lub usunąć pozycję, trzeba
  wrócić na początek – po zatwierdzeniu BOM aplikacja wykonuje sprawdzenia i dopisuje wyliczenia historyczne, więc
  tylko pełny przebieg jest spójny. W `petle` to typ „Zmiana zakresu (powrót do RFQ)”. Analizuj **koszt** i
  **częstość** takich zmian (ile dni kosztuje jedna, czy da się ich uniknąć wcześniej), a nie sam fakt cofania.
- **Konsultacje DTTW są strukturalne.** DTTW nie ma kompetencji, by samodzielnie zatwierdzić wszystko, i rozsyła
  sprawy do działów (przyrządy, malowanie, procesy specjalne, inne działy techniczne). Konsultacje są więc częścią
  pracy, a nie objawem problemu. Szukaj, **które działy** (`konsultacje_wg_dzialu`) i **które osoby**
  (`obciazenie_konsultantow`) odpowiadają wolno lub są przeciążone.

## Struktura pliku (`schemat` = 2)

| Klucz | Zawartość |
|---|---|
| `meta` | data migawki, moment pobrania (UTC), zakres (`pierwsze_zapytanie_id`), próg porzucenia |
| `podsumowanie` | liczby kontrolne: zapytania, otwarte, workflow, zadania, konsultacje, zawieszone |
| `czas_realizacji_zamknietych` | mediana i P80 czasu realizacji zamkniętych zapytań |
| `terminowosc` | oferty przekazane klientowi: odsetek w terminie, spóźnione (mediana dni), braki danych, najbardziej spóźnione |
| `kontrola_danych` | kontrole jakości; `Rodzaj` = OK / Informacja / Do sprawdzenia |
| `fazy` | dla każdej fazy: czas w fazie (mediana/P80/maks.), % zapytań z powrotem do fazy, cofnięcia, konsultacje, **udział w czasie realizacji** |
| `zbieranie_danych_galaz_krytyczna` | faza równoległa: „Razy ostatnia” (dosłownie), „Razy przyczyną” i opóźnienie jako przyczyna (z uwzględnieniem zależności), ile otwartych rund blokuje |
| `zaleznosci_grup` | weryfikacja zależności (np. DJ → DTTW): czy grupa kończy zaraz po tamtej, czas własny po otrzymaniu danych, % zamykanych przez tę samą osobę |
| `etapy` | zadania główne wg etapu i grupy: mediana/P80/maks., otwarte, cofnięcia, liczba konsultacji i osobodni konsultacji |
| `konsultacje_a_czas` | czas zadań z konsultacjami vs bez – wg etapu |
| `konsultacje` | liczba, rozkład poziomów i rund, konsultacje wg etapu, najczęściej konsultowani (pseudonimy) |
| `konsultacje_wg_dzialu` | konsultacje wg działu konsultanta (słownik uzupełniany przez użytkownika; „(nieprzypisany)” = brak wpisu) |
| `obciazenie_konsultantow` | dla osoby: konsultacje, otwarte teraz, maks. otwartych jednocześnie, czas odpowiedzi (pseudonimy) |
| `petle` | koszt pętli cofnięć wg etapu cofającego i typu (zmiana zakresu / korekta – powrót do fazy X): mediana, P80, suma dni, zadania po drodze |
| `cofniecia` | etap, który cofnął, decyzja, faza, do której zapytanie wróciło, liczba |
| `dlugie_oferty` | zadania „Przygotowanie oferty” > 14 dni wg decyzji: ile, mediana, ile w zapytaniach anulowanych i z rewizją |
| `rozklad_czasow` | liczba zakończonych zadań w przedziałach < 1 / 1–3 / 3–7 / 7–14 / 14–30 / > 30 dni |
| `trend_tygodniowy` | tydzień po tygodniu: nowe, zamknięte, w toku, otwarte zadania, mediana realizacji zamkniętych |
| `porzucone_podsumowanie` | pełna liczba porzuconych i podział wg etapu |
| `porzucone` | do 30 najstarszych otwartych zadań/konsultacji starszych niż próg |
| `najdluzsze_zadania` | 20 najdłuższych zakończonych zadań |

## Jak czytać miary (częste pułapki)

- **Czas w fazie** liczy okresy, w których otwarte było choć jedno zadanie fazy – zadania równoległe liczą się raz,
  powroty po cofnięciu sumują się. **Rozpiętość** obejmuje też przerwy między rundami.
- **Udział w czasie realizacji** liczony jest tylko dla zamkniętych zapytań. Udziały faz nie muszą sumować się do 100%
  (przerwy między fazami, kroki automatyczne, fazy „Inne”).
- **Osobodni konsultacji** to suma czasów wszystkich konsultacji – mierzy obciążenie ludzi, **nie** wydłużenie wyceny
  (konsultacje biegną równolegle i nie blokują zadania głównego).
- **Zawieszona konsultacja**: otwarta, choć zadanie główne zakończone lub zapytanie zamknięte – to błąd procesu
  lub aplikacji, nie realna praca w toku.
- **Mediana vs P80**: duża różnica (np. 0,2 vs 14 dni) oznacza etap o „dwóch obliczach” – potwierdź w `rozklad_czasow`.
- Dni są **kalendarzowe** (weekendy i święta wliczone).
- Statystyki z małej liczby przypadków (< 10) oznaczaj jako niepewne.
- Etapy pomijane z założenia: „Ewentualne zmiany w RFQ/BOM” (zadania wyjścia z obiegu) – ich brak jest celowy.

## Kolejność analizy

1. **Wiarygodność danych** – `kontrola_danych`: wypisz pozycje „Do sprawdzenia” z liczbą > 0 i oceń, czy mogą
   zniekształcić wnioski. Jeśli tak – zacznij od nich.
2. **Gdzie płynie czas** – `fazy`: uszereguj fazy wg udziału w czasie realizacji i P80; wskaż 2–3 największe.
3. **Faza równoległa** – `zbieranie_danych_galaz_krytyczna`: która grupa jest najczęściej **przyczyną** wydłużenia
   (nie tylko ostatnia), jaka suma opóźnień, ile rund blokuje teraz; `zaleznosci_grup` – ile realnie pracuje grupa
   zależna po otrzymaniu danych.
4. **Konsultacje** – `konsultacje_a_czas`, `konsultacje`, `etapy`: czy zadania z konsultacjami trwają dłużej
   (różnica median, P80), jak głębokie są łańcuchy (poziomy, rundy), czy obciążenie skupia się na kilku osobach,
   ile jest zawieszonych.
5. **Pętle** – `petle`: ile kosztuje (dni) jedna pętla danego typu i ile ich jest; osobno zmiany zakresu
   (celowe – pytanie, czy dało się je wykryć wcześniej) i korekty danych.
6. **Terminowość** – `terminowosc`: odsetek w terminie, spóźnienia, braki danych.
7. **Zaległości** – `porzucone_podsumowanie`, `porzucone`: ile, w jakich etapach, czy dotyczą zapytań w toku.
8. **Trend** – `trend_tygodniowy`: czy przybywa zapytań w toku (napływ > zamknięcia), czy czas realizacji rośnie.

## Format odpowiedzi

1. **Najważniejsze wnioski** – 3–5 punktów, od największego wpływu na czas realizacji, każdy z liczbami.
2. **Wąskie gardła** – tabela: miejsce | miara | wartość | dlaczego to problem.
3. **Do sprawdzenia z zespołem** – hipotezy i konkretne przypadki (numery zapytań z `porzucone`/`najdluzsze_zadania`).
4. **Zastrzeżenia** – jakość danych, małe próby, czego plik nie mówi.

Przy dwóch plikach z różnych dni porównuj wartości zagregowane (fazy, etapy, trend), nie pseudonimy osób.

## Gdy brakuje informacji

Plik nie zawiera pojedynczych zadań ani historii komentarzy. Jeśli wniosek wymaga szczegółów,
wskaż, który arkusz raportu Excel to pokazuje (np. „Oś czasu”, „Konsultacje”, „Zadania”), albo zaproponuj
rozszerzenie eksportu w `wyceny/eksport.py` (podnieś `WERSJA_SCHEMATU` i zaktualizuj tę tabelę).
