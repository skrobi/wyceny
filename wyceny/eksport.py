"""Eksport JSON do analizy przez asystenta AI (skill .claude/skills/analiza-wycen).

Plik zawiera wyłącznie zagregowane zestawienia i krótkie listy przypadków – ma być mały i czytelny.
Osoby są domyślnie zastąpione pseudonimami („Osoba 07”); grupy AD i klienci pozostają bez zmian.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from . import kontrola, proces, przeplyw
from .config import Analiza
from .model import Model

WERSJA_SCHEMATU = 3


class Pseudonimy:
    """Stałe pseudonimy osób w obrębie jednego pliku. „Nazwisko Imię | e123” i „Nazwisko Imię” to ta sama osoba."""

    def __init__(self, wlaczone: bool):
        self.wlaczone = wlaczone
        self._mapa: dict[str, str] = {}

    @staticmethod
    def _klucz(osoba: str) -> str:
        return osoba.split("|")[0].strip().lower()

    def zarejestruj(self, *kolumny: pd.Series) -> None:
        klucze = sorted({self._klucz(v) for k in kolumny for v in k.dropna() if isinstance(v, str)})
        for i, kl in enumerate(klucze, start=1):
            self._mapa.setdefault(kl, f"Osoba {i:02d}")

    def __call__(self, wartosc):
        if not self.wlaczone or not isinstance(wartosc, str):
            return wartosc
        return self._mapa.get(self._klucz(wartosc), "Osoba ?")


def _czysc(v):
    if v is None or v is pd.NaT:
        return None
    if isinstance(v, float):
        if math.isnan(v):
            return None
        return int(v) if v.is_integer() else round(v, 2)
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, date):
        return v.isoformat()
    if hasattr(v, "item"):
        return _czysc(v.item())
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _rekordy(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    return [{str(k): _czysc(v) for k, v in w.items()} for w in df.to_dict(orient="records")]


def konsultacje_podsumowanie(m: Model, p: Pseudonimy) -> dict:
    z = m.zadania
    k = z[z["CzyKonsultacja"]]
    if k.empty:
        return {}
    zak = k[k["Stan"] == "Zakończone"]
    wg_etapu = (k.groupby(["EtapGlowny", "GrupaGlowna"], dropna=False)
                .agg(konsultacje=("Id", "size"), zadania_glowne=("ZadanieGlowne", "nunique"),
                     maks_poziom=("PoziomKonsultacji", "max"), mediana_dni=("CzasDni", "median"),
                     otwarte=("Stan", lambda s: int((s == "Otwarte").sum())),
                     zawieszone=("ZawieszonaKonsultacja", "sum"))
                .reset_index().sort_values("konsultacje", ascending=False))
    poziomy = k["PoziomKonsultacji"].value_counts().sort_index()
    rundy = k["Runda"].value_counts().sort_index()
    konsultanci = (k.assign(Osoba=k["Konsultant"].map(p))
                   .groupby("Osoba").agg(konsultacje=("Id", "size"), mediana_dni=("CzasDni", "median"),
                                         otwarte=("Stan", lambda s: int((s == "Otwarte").sum())),
                                         etapy=("EtapGlowny", lambda s: ", ".join(sorted(s.dropna().unique())[:3])))
                   .reset_index().sort_values("konsultacje", ascending=False).head(15))
    return {
        "liczba": len(k), "zakonczone": len(zak), "otwarte": int((k["Stan"] == "Otwarte").sum()),
        "zawieszone": int(k["ZawieszonaKonsultacja"].sum()),
        "mediana_dni_zakonczonych": _czysc(zak["CzasDni"].median()),
        "rozklad_poziomow": {str(int(i)): int(v) for i, v in poziomy.items()},
        "rozklad_rund": {str(int(i)): int(v) for i, v in rundy.items()},
        "wg_etapu": _rekordy(wg_etapu),
        "najczesciej_konsultowani": _rekordy(konsultanci),
    }


def cofniecia(g: pd.DataFrame) -> list[dict]:
    """Decyzje zwrotne wg etapu, który cofnął, i decyzji – oraz fazy, do której zapytanie wróciło."""
    c = g[g["Cofniecie"] & g["ZakonczonoUtc"].notna()].copy()
    if c.empty:
        return []
    po_zapytaniu = {zid: grp.sort_values("PrzypisanoUtc") for zid, grp in g.groupby("TenderEnquiryId")}

    def faza_powrotu(w) -> str | None:
        dalsze = po_zapytaniu[w["TenderEnquiryId"]]
        dalsze = dalsze[(dalsze["PrzypisanoUtc"] >= w["ZakonczonoUtc"]) & (dalsze["Id"] != w["Id"])]
        return dalsze["Faza"].iloc[0] if len(dalsze) else None

    c["Faza powrotu"] = c.apply(faza_powrotu, axis=1)
    wynik = (c.groupby(["Prompt", "Grupa", "Decyzja", "Faza powrotu"], dropna=False)
             .size().rename("liczba").reset_index().sort_values("liczba", ascending=False))
    return _rekordy(wynik.head(40).rename(columns={"Prompt": "etap_cofajacy", "Grupa": "grupa",
                                          "Decyzja": "decyzja", "Faza powrotu": "faza_powrotu"}))


def zbuduj(m: Model, dzien: date, analiza: Analiza | None = None, slownik: dict[str, str] | None = None) -> dict:
    analiza = analiza or Analiza()
    slownik = slownik or {}
    z = m.zadania
    g = proces.zadania_glowne(m)
    p = Pseudonimy(analiza.json_anonimizacja)
    p.zarejestruj(z["Konsultant"], z["Wykonal"], z["OwnerName"], m.zapytania["OwnerName"])

    def osoby(df: pd.DataFrame, kolumny: list[str]) -> pd.DataFrame:
        df = df.copy()
        for kol in kolumny:
            if kol in df.columns:
                df[kol] = df[kol].map(p)
        return df

    real = proces.czas_realizacji(m, g)
    zamk = real[real["Zamkniete"]]
    porz = proces.porzucone(m, analiza.prog_porzucenia_dni)
    porz = porz.assign(Komu=[p(k) if c else k for k, c in zip(porz["Komu"], porz["CzyKonsultacja"])])
    porz_wg_etapu = (porz.groupby(["Etap", "CzyKonsultacja"], dropna=False)
                     .agg(liczba=("CzasDni", "size"), mediana_dni=("CzasDni", "median"))
                     .reset_index().sort_values("liczba", ascending=False))
    term = proces.terminowosc(m, g, analiza.statusy_przekazane)
    spoznione = term[term["W terminie"] == False].head(15)  # noqa: E712
    petle = proces.petle(m, g)
    trend = przeplyw.trend_tygodniowy(m, g)
    prog, projekcja = przeplyw.prognoza(m, g, trend)
    dom_pod, _ = przeplyw.dominujaca_faza(m, g)
    return {
        "schemat": WERSJA_SCHEMATU,
        "meta": {
            "migawka": dzien, "pobrano_utc": m.teraz_utc,
            "pierwsze_zapytanie_id": m.pierwsze_zapytanie_id, "data_graniczna_workflow": m.data_startu,
            "anonimizacja_osob": analiza.json_anonimizacja, "prog_porzucenia_dni": analiza.prog_porzucenia_dni,
            "zaleznosci_grup": analiza.zaleznosci_grup, "tolerancja_zaleznosci_dni": analiza.tolerancja_zaleznosci_dni,
            "statusy_przekazane": analiza.statusy_przekazane, "jednostka_czasu": "dni kalendarzowe",
            "slownik_dzialow_wpisow": len(slownik),
        },
        "podsumowanie": {str(r["Pozycja"]).strip(): _czysc(r["Wartość"])
                         for r in kontrola.podsumowanie(m).to_dict(orient="records")},
        "czas_realizacji_zamknietych": {
            "zapytania": len(zamk), "mediana_dni": _czysc(zamk["CzasRealizacjiDni"].median()),
            "p80_dni": _czysc(zamk["CzasRealizacjiDni"].quantile(0.8)) if len(zamk) else None,
        },
        "terminowosc": {**{k: _czysc(v) for k, v in proces.terminowosc_podsumowanie(term).items()},
                        "najbardziej_spoznione": _rekordy(osoby(spoznione, ["OwnerName"]))},
        "kontrola_danych": _rekordy(kontrola.kontrole(m, tuple(analiza.statusy_przekazane))),
        "fazy": _rekordy(proces.fazy(m, g)),
        "zbieranie_danych_galaz_krytyczna": _rekordy(
            proces.galaz_krytyczna(g, analiza.zaleznosci_grup, analiza.tolerancja_zaleznosci_dni)),
        "zaleznosci_grup": _rekordy(
            proces.zaleznosci_grup(g, analiza.zaleznosci_grup, analiza.tolerancja_zaleznosci_dni)),
        "etapy": _rekordy(kontrola.etapy(m)),
        "konsultacje_a_czas": _rekordy(proces.wplyw_konsultacji(g)),
        "konsultacje": konsultacje_podsumowanie(m, p),
        "konsultacje_wg_dzialu": _rekordy(proces.konsultacje_wg_dzialu(m, slownik)),
        "obciazenie_konsultantow": _rekordy(
            osoby(proces.obciazenie_konsultantow(m, slownik), ["Konsultant"]).head(20)),
        "petle": _rekordy(proces.petle_podsumowanie(petle)),
        "cofniecia": cofniecia(g),
        "dlugie_oferty": _rekordy(proces.profil_dlugich(m, g)),
        "rozklad_czasow": _rekordy(proces.rozklad(g)),
        "trend_tygodniowy": _rekordy(trend),
        "przeplyw": {
            "prognoza": {k: _czysc(v) for k, v in prog.items()},
            "projekcja_w_toku": _rekordy(projekcja),
            "zaleglosc_wg_fazy_ostatnie_12_tyg": _rekordy(przeplyw.zaleglosc_wg_fazy(m, g).tail(12)),
            "dominujaca_faza": _rekordy(dom_pod),
        },
        "porzucone_podsumowanie": {"liczba": len(porz), "wg_etapu": _rekordy(porz_wg_etapu)},
        "porzucone": _rekordy(osoby(porz, ["OwnerName"]).head(30)),
        "najdluzsze_zadania": _rekordy(osoby(proces.najdluzsze(g, 20), ["OwnerName", "Wykonal"])),
    }


def zapisz(dane: dict, sciezka: Path) -> Path:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    sciezka.write_text(json.dumps(dane, ensure_ascii=False, indent=1, default=_czysc), encoding="utf-8")
    return sciezka
