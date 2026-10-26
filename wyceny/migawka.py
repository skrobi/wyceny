"""Migawka danych: pobranie z bazy do plików CSV w data/<data>/ i ich wczytanie.

Migawki pozwalają analizować dane bez połączenia z bazą i porównywać stan w czasie
(baza przechowuje tylko stan bieżący, np. ostatni komentarz).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from .config import KATALOG_PROJEKTU, Konfiguracja

KATALOG_SQL = KATALOG_PROJEKTU / "sql"

# nazwa tabeli w migawce -> (plik SQL, kolumny z datami)
TABELE = {
    "zapytania": ("01_zapytania.sql", [
        "DateRequestReceived", "StartDateOfDataCollection", "DataCompletionDeadline",
        "StartDateOfValuation", "ValuationCompletionDate", "SubmissionDateRequired",
        "TransferToCustomerDate", "DateCompleted"]),
    "workflow": ("02_workflow.sql", ["CreateTime", "CompleteTime"]),
    "kroki": ("03_kroki.sql", ["StartTime", "EndTime"]),
    "atrybuty": ("04_atrybuty.sql", []),
    "zdarzenia": ("05_zdarzenia.sql", ["EventTime"]),
}


@dataclass
class Migawka:
    data: date
    pobrano_utc: pd.Timestamp
    zapytania: pd.DataFrame
    workflow: pd.DataFrame
    kroki: pd.DataFrame
    atrybuty: pd.DataFrame
    zdarzenia: pd.DataFrame


def pobierz(kfg: Konfiguracja, dzien: date | None = None) -> Path:
    """Uruchamia zapytania z katalogu sql/ i zapisuje wyniki jako CSV w data/<dzień>/."""
    import pyodbc  # import tutaj: wczytywanie migawek i testy nie wymagają sterownika

    dzien = dzien or date.today()
    katalog = kfg.katalog_danych / dzien.isoformat()
    katalog.mkdir(parents=True, exist_ok=True)
    start = datetime.combine(kfg.analiza.data_startu, datetime.min.time())
    pobrano = pd.Timestamp.now(tz="UTC").tz_localize(None)
    with pyodbc.connect(kfg.baza.connection_string(), timeout=30) as conn:
        for nazwa, (plik, _) in TABELE.items():
            sql = (KATALOG_SQL / plik).read_text(encoding="utf-8")
            kursor = conn.cursor()
            kursor.execute(sql, start)
            kolumny = [k[0] for k in kursor.description]
            df = pd.DataFrame.from_records(kursor.fetchall(), columns=kolumny)
            df.to_csv(katalog / f"{nazwa}.csv", index=False, encoding="utf-8")
            print(f"  {nazwa}: {len(df)} wierszy")
    meta = {"pobrano_utc": pobrano.isoformat(), "data_startu": kfg.analiza.data_startu.isoformat()}
    (katalog / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return katalog


def dostepne(kfg: Konfiguracja) -> list[date]:
    if not kfg.katalog_danych.exists():
        return []
    dni = []
    for p in kfg.katalog_danych.iterdir():
        try:
            if p.is_dir() and (p / "zapytania.csv").exists():
                dni.append(date.fromisoformat(p.name))
        except ValueError:
            continue
    return sorted(dni)


def wczytaj(kfg: Konfiguracja, dzien: date | None = None) -> Migawka:
    """Wczytuje migawkę z danego dnia (domyślnie najnowszą)."""
    dni = dostepne(kfg)
    if not dni:
        raise FileNotFoundError(f"Brak migawek w {kfg.katalog_danych} – najpierw uruchom: python -m wyceny pobierz")
    dzien = dzien or dni[-1]
    katalog = kfg.katalog_danych / dzien.isoformat()
    tabele = {}
    for nazwa, (_, daty) in TABELE.items():
        df = pd.read_csv(katalog / f"{nazwa}.csv", encoding="utf-8", low_memory=False)
        for kol in daty:
            df[kol] = pd.to_datetime(df[kol], errors="coerce")
        tabele[nazwa] = df
    meta_plik = katalog / "meta.json"
    if meta_plik.exists():
        pobrano = pd.Timestamp(json.loads(meta_plik.read_text(encoding="utf-8"))["pobrano_utc"])
    else:
        pobrano = pd.Timestamp(dzien) + pd.Timedelta(hours=23, minutes=59)
    return Migawka(data=dzien, pobrano_utc=pobrano, **tabele)
