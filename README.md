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
pomijanych zadań. `config.toml` nie trafia do repozytorium.

## Uruchomienie

```
python -m wyceny              # pobierz dane i zrób raport
python -m wyceny pobierz      # tylko migawka z bazy -> data/RRRR-MM-DD/*.csv
python -m wyceny raport       # raport z najnowszej migawki -> raporty/analiza_wycen_RRRR-MM-DD.xlsx
python -m wyceny raport --migawka 2026-10-26
```

Migawki (`data/`) i raporty (`raporty/`) zawierają dane osobowe – są w `.gitignore`.

## Raport (krok 1)

| Arkusz | Zawartość |
|---|---|
| Podsumowanie | Liczby kontrolne: zapytania, workflow, zadania, konsultacje |
| Kontrola danych | Problemy z danymi do sprawdzenia przed dalszymi analizami (m.in. zawieszone konsultacje) |
| Etapy | Pierwsze spojrzenie: czasy etapów i grup, cofnięcia, obciążenie konsultacjami |
| Konsultacje | Każda konsultacja z zadaniem głównym, poziomem i rundą |
| Zadania / Zapytania | Dane źródłowe do własnych filtrów |
| Słownik | Definicje pojęć |

## Struktura

```
sql/            zapytania pobierające surowe dane (parametr: data startu)
wyceny/         config, migawka (pobieranie/wczytywanie), model, kontrola, raport
tests/          testy na fikcyjnych danych: python -m unittest
docs/           model-danych.md (jak wyglądają dane), plan.md (kolejne kroki)
```
