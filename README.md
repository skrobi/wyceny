# wyceny – analiza przebiegu wycen

Program pobiera dane zapytań ofertowych i workflow (WorkflowCore) z bazy **WYCENY**, buduje model procesu
(zadania, konsultacje, poziomy przekierowań) i tworzy raport Excel. Celem jest wskazanie wąskich gardeł
i najbardziej problematycznych miejsc procesu wyceny.

## Wymagania

- Windows, Python 3.11+
- pakiety: `pip install -r requirements.txt`
- sterownik **ODBC Driver 18 for SQL Server** i konto AD z prawem odczytu bazy WYCENY

## Konfiguracja

Skopiuj `config.example.toml` do `config.toml` i w razie potrzeby zmień serwer, datę startu albo listę
pomijanych zadań oraz pierwsze analizowane zapytanie (`pierwsze_zapytanie_id`, domyślnie 758). `config.toml` nie trafia do repozytorium.

## Uruchomienie

```
python -m wyceny              # pobierz dane i zrób raport
python -m wyceny pobierz      # tylko migawka z bazy -> data/RRRR-MM-DD/*.csv
python -m wyceny raport       # raport z najnowszej migawki -> raporty/analiza_wycen_RRRR-MM-DD.xlsx
python -m wyceny raport --migawka 2026-10-26
```

Obok raportu Excel powstaje `analiza_wycen_RRRR-MM-DD.json` – zwięzłe zestawienia do analizy przez asystenta AI
(Claude Code: skill `analiza-wycen` w `.claude/skills/`). Osoby są w nim zastąpione pseudonimami („Osoba 07”);
wyłącza to `json_anonimizacja = false` w `config.toml`.

Migawki (`data/`) i raporty (`raporty/`) zawierają dane osobowe – są w `.gitignore`.

## Raport

| Arkusz | Zawartość |
|---|---|
| Podsumowanie | Zakres analizy i liczby kontrolne: zapytania, workflow, zadania, konsultacje |
| Kontrola danych | Problemy z danymi do sprawdzenia przed dalszymi analizami (m.in. zawieszone konsultacje) |
| Fazy | Czas w każdej fazie, powroty do fazy, udział w czasie realizacji |
| Zbieranie danych | Faza równoległa: która grupa kończy ostatnia i o ile wydłuża fazę |
| Konsultacje a czas | Czas zadań z konsultacjami i bez – wg etapu |
| Etapy | Czasy etapów i grup, cofnięcia, obciążenie konsultacjami |
| Rozkład czasów | Ile zadań trwało < 1 dnia, 1–3, 3–7… dni – wg etapu |
| Porzucone | Zadania i konsultacje otwarte dłużej niż próg (domyślnie 30 dni) |
| Najdłuższe zadania | 50 najdłuższych zakończonych zadań do omówienia |
| Oś czasu | Zapytanie × faza: start, koniec, czas, rundy, konsultacje |
| Konsultacje | Każda konsultacja z zadaniem głównym, poziomem i rundą |
| Zadania / Zapytania | Dane źródłowe do własnych filtrów |
| Słownik | Definicje pojęć |

## Struktura

```
sql/            zapytania pobierające surowe dane (parametr: pierwsze Id zapytania lub data graniczna)
wyceny/         config, migawka (pobieranie/wczytywanie), model, kontrola, proces (fazy, oś czasu), raport, eksport (JSON)
.claude/skills/ analiza-wycen – jak asystent AI analizuje plik JSON
tests/          testy na fikcyjnych danych: python -m unittest
docs/           model-danych.md (jak wyglądają dane), plan.md (kolejne kroki)
```
