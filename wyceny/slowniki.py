"""Słownik konsultant -> dział (plik CSV uzupełniany przez użytkownika).

Plik: kolumny eID;Osoba;Konsultacje;Dzial (separator „;”, kodowanie UTF-8 z BOM – otwiera się poprawnie w Excelu).
Program dopisuje nowych konsultantów i zachowuje uzupełnione działy.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .model import Model

KOLUMNY = ["eID", "Osoba", "Konsultacje", "Dzial"]


def _rozbij(osoba: str) -> tuple[str, str]:
    czesci = [c.strip() for c in osoba.split("|")]
    return (czesci[1] if len(czesci) > 1 else czesci[0]).lower(), czesci[0]


def wczytaj(sciezka: Path) -> dict[str, str]:
    if not sciezka.exists():
        return {}
    df = pd.read_csv(sciezka, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
    return {r["eID"].strip().lower(): r["Dzial"].strip() for _, r in df.iterrows() if r["Dzial"].strip()}


def aktualizuj_szablon(m: Model, sciezka: Path) -> Path:
    """Tworzy albo uzupełnia plik słownika o konsultantów z bieżącej migawki."""
    k = m.zadania.loc[m.zadania["CzyKonsultacja"], "Konsultant"].dropna()
    liczby: dict[str, list] = {}
    for osoba in k:
        eid, nazwa = _rozbij(osoba)
        liczby.setdefault(eid, [nazwa, 0])[1] += 1
    nowe = pd.DataFrame([{"eID": e, "Osoba": n, "Konsultacje": c, "Dzial": ""} for e, (n, c) in liczby.items()],
                        columns=KOLUMNY)
    if sciezka.exists():
        stare = pd.read_csv(sciezka, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
        dzialy = dict(zip(stare["eID"].str.lower(), stare["Dzial"]))
        nowe["Dzial"] = nowe["eID"].map(dzialy).fillna("")
        brakujace = stare[~stare["eID"].str.lower().isin(nowe["eID"])]
        nowe = pd.concat([nowe, brakujace[KOLUMNY]], ignore_index=True)
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    nowe.sort_values("Konsultacje", ascending=False, key=pd.to_numeric).to_csv(
        sciezka, sep=";", index=False, encoding="utf-8-sig")
    return sciezka
