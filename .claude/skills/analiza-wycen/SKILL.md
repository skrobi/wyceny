---
name: analiza-wycen
description: Analiza przebiegu wycen (zapytań ofertowych) z pliku analiza_wycen_RRRR-MM-DD.json tworzonego przez `python -m wyceny`. Używaj, gdy użytkownik wkleja lub przesyła ten plik albo pyta o wąskie gardła, czasy faz, konsultacje (przekierowania), cofnięcia, porzucone zadania lub trend realizacji wycen.
---

# Analiza wycen z pliku JSON

Plik `analiza_wycen_RRRR-MM-DD.json` powstaje obok raportu Excel (`raporty/`). Zawiera wyłącznie zestawienia
zagregowane i krótkie listy przypadków. Osoby są zastąpione pseudonimami („Osoba 07”) – pseudonimy są stałe
w obrębie jednego pliku, ale **nie** między plikami z różnych dni. Grupy (DS, DTTW, DZ…) i klienci są jawni.

Odpowiadaj po polsku. Każdy wniosek opieraj na liczbach z pliku i podawaj je. Nie zgaduj przyczyn biznesowych –
nazwij je hipotezami do sprawdzenia z zespołem.

## Struktura pliku (`schemat` = 1)

| Klucz | Zawartość |
|---|---|
| `meta` | data migawki, moment pobrania (UTC), zakres (`pierwsze_zapytanie_id`), próg porzucenia |
| `podsumowanie` | liczby kontrolne: zapytania, otwarte, workflow, zadania, konsultacje, zawieszone |
| `czas_realizacji_zamknietych` | mediana i P80 czasu realizacji zamkniętych zapytań, odsetek oddanych w terminie klienta |
| `kontrola_danych` | kontrole jakości; `Rodzaj` = OK / Informacja / Do sprawdzenia |
| `fazy` | dla każdej fazy: czas w fazie (mediana/P80/maks.), % zapytań z powrotem do fazy, cofnięcia, konsultacje, **udział w czasie realizacji** |
| `zbieranie_danych_galaz_krytyczna` | faza równoległa: ile razy grupa kończyła rundę ostatnia i o ile dni ją wydłużyła; ile otwartych rund teraz blokuje |
| `etapy` | zadania główne wg etapu i grupy: mediana/P80/maks., otwarte, cofnięcia, liczba konsultacji i osobodni konsultacji |
| `konsultacje_a_czas` | czas zadań z konsultacjami vs bez – wg etapu |
| `konsultacje` | liczba, rozkład poziomów i rund, konsultacje wg etapu, najczęściej konsultowani (pseudonimy) |
| `cofniecia` | etap, który cofnął, decyzja, faza, do której zapytanie wróciło, liczba |
| `rozklad_czasow` | liczba zakończonych zadań w przedziałach < 1 / 1–3 / 3–7 / 7–14 / 14–30 / > 30 dni |
| `trend_tygodniowy` | tydzień po tygodniu: nowe, zamknięte, w toku, otwarte zadania, mediana realizacji zamkniętych |
| `porzucone` | do 30 otwartych zadań/konsultacji starszych niż próg |
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
3. **Faza równoległa** – `zbieranie_danych_galaz_krytyczna`: która grupa najczęściej kończy ostatnia, jaka suma
   opóźnień, ile rund blokuje teraz.
4. **Konsultacje** – `konsultacje_a_czas`, `konsultacje`, `etapy`: czy zadania z konsultacjami trwają dłużej
   (różnica median, P80), jak głębokie są łańcuchy (poziomy, rundy), czy obciążenie skupia się na kilku osobach,
   ile jest zawieszonych.
5. **Pętle** – `cofniecia`, kolumna „% zapytań z powrotem do fazy” w `fazy`: które etapy najczęściej cofają
   i dokąd zapytania wracają.
6. **Zaległości** – `porzucone`: ile, w jakich etapach, czy dotyczą zapytań w toku czy zamkniętych.
7. **Trend** – `trend_tygodniowy`: czy przybywa zapytań w toku (napływ > zamknięcia), czy czas realizacji rośnie.

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
