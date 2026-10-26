"""Krok 4: przepływ zapytań – napływ, zamknięcia, zaległość (zapytania w toku), prognoza i dominująca faza.

Pojęcia:
- Zapytania w toku (WIP): rozpoczęte i niezamknięte na koniec tygodnia.
- Przepustowość: zapytania zamknięte w tygodniu.
- Prawo Little'a: średni czas realizacji ≈ średnia zaległość / średnia przepustowość. Duża rozbieżność z faktyczną
  medianą oznacza, że część zapytań w toku stoi (np. porzucone) albo proces nie jest stabilny.
- Prognoza: prosta ekstrapolacja średniego przyrostu netto (nowe − zamknięte) z ostatnich pełnych tygodni.
"""
from __future__ import annotations

import pandas as pd

from . import proces
from .model import Model

BEZ_ZADANIA = "Bez otwartego zadania"


def _tygodnie(m: Model, start: pd.Timestamp) -> pd.DatetimeIndex:
    start = start.normalize()
    return pd.date_range(start - pd.Timedelta(days=start.dayofweek), m.teraz_utc, freq="7D")


def trend_tygodniowy(m: Model, g: pd.DataFrame) -> pd.DataFrame:
    """Tydzień po tygodniu: napływ, zamknięcia, zapytania w toku i otwarte zadania na koniec tygodnia."""
    real = proces.czas_realizacji(m, g)
    if real.empty:
        return pd.DataFrame()
    wiersze = []
    for pocz in _tygodnie(m, real["StartUtc"].min()):
        kon = pocz + pd.Timedelta(days=7)
        zamk_w_tyg = real[real["Zamkniete"] & (real["KoniecUtc"] >= pocz) & (real["KoniecUtc"] < kon)]
        w_toku = real[(real["StartUtc"] < kon) & (~real["Zamkniete"] | (real["KoniecUtc"] >= kon))]
        otw_zad = g[(g["PrzypisanoUtc"] < kon) & (g["KoniecUtc"] >= kon)]
        nowe = int(((real["StartUtc"] >= pocz) & (real["StartUtc"] < kon)).sum())
        wiersze.append({
            "tydzien_od": pocz.date(),
            "pelny_tydzien": bool(kon <= m.teraz_utc),
            "nowe_zapytania": nowe,
            "zamkniete_zapytania": len(zamk_w_tyg),
            "przyrost_netto": nowe - len(zamk_w_tyg),
            "zapytania_w_toku_koniec_tygodnia": len(w_toku),
            "otwarte_zadania_koniec_tygodnia": len(otw_zad),
            "mediana_realizacji_zamknietych_dni": zamk_w_tyg["CzasRealizacjiDni"].median(),
        })
    return pd.DataFrame(wiersze)


def zaleglosc_wg_fazy(m: Model, g: pd.DataFrame) -> pd.DataFrame:
    """Na koniec każdego tygodnia: ile zapytań w toku było w której fazie.

    Faza zapytania = najdalsza faza spośród jego otwartych wtedy zadań głównych; zapytanie w toku bez otwartego
    zadania głównego (np. czeka na krok automatyczny lub tylko na konsultację) trafia do „Bez otwartego zadania”.
    """
    real = proces.czas_realizacji(m, g)
    if real.empty:
        return pd.DataFrame()
    fazy = [f for f, _ in proces.FAZY] + [proces.INNE, BEZ_ZADANIA]
    wiersze = []
    for pocz in _tygodnie(m, real["StartUtc"].min()):
        kon = min(pocz + pd.Timedelta(days=7), m.teraz_utc)
        w_toku = real.index[(real["StartUtc"] < kon) & (~real["Zamkniete"] | (real["KoniecUtc"] >= kon))]
        otwarte = g[(g["PrzypisanoUtc"] < kon) & (g["KoniecUtc"] >= kon) & g["TenderEnquiryId"].isin(w_toku)]
        faza_zap = otwarte.sort_values("KolejnoscFazy").groupby("TenderEnquiryId")["Faza"].last()
        liczby = faza_zap.value_counts()
        wiersz = {"tydzien_od": pocz.date()}
        wiersz.update({f: int(liczby.get(f, 0)) for f in fazy[:-1]})
        wiersz[BEZ_ZADANIA] = int(len(w_toku) - len(faza_zap))
        wiersze.append(wiersz)
    wynik = pd.DataFrame(wiersze)
    # bez kolumn faz, które nigdy nie wystąpiły
    puste = [f for f in fazy if f in wynik.columns and wynik[f].sum() == 0]
    return wynik.drop(columns=puste)


def prognoza(m: Model, g: pd.DataFrame, trend: pd.DataFrame, okno_tygodni: int = 8,
             horyzont_tygodni: int = 8) -> tuple[dict, pd.DataFrame]:
    """Średni napływ i przepustowość z ostatnich pełnych tygodni, prawo Little'a i projekcja zaległości."""
    real = proces.czas_realizacji(m, g)
    pelne = trend[trend["pelny_tydzien"]].tail(okno_tygodni) if not trend.empty else trend
    if real.empty or pelne.empty:
        return {}, pd.DataFrame()
    w_toku_teraz = int((~real["Zamkniete"]).sum())
    sr_nowe = float(pelne["nowe_zapytania"].mean())
    sr_zamk = float(pelne["zamkniete_zapytania"].mean())
    netto = sr_nowe - sr_zamk
    sr_wip = float(pelne["zapytania_w_toku_koniec_tygodnia"].mean())
    od = pd.Timestamp(pelne["tydzien_od"].iloc[0])
    zamk_w_oknie = real[real["Zamkniete"] & (real["KoniecUtc"] >= od)]
    wynik = {
        "okno_tygodni": len(pelne),
        "okno_od": pelne["tydzien_od"].iloc[0],
        "srednio_nowych_tygodniowo": sr_nowe,
        "srednio_zamknietych_tygodniowo": sr_zamk,
        "przyrost_netto_tygodniowo": netto,
        "kierunek": "rośnie" if netto > 0.5 else "maleje" if netto < -0.5 else "stabilna",
        "zapytania_w_toku_teraz": w_toku_teraz,
        "srednio_w_toku": sr_wip,
        "czas_realizacji_z_prawa_Littlea_dni": sr_wip / sr_zamk * 7 if sr_zamk else None,
        "czas_realizacji_faktyczny_mediana_dni": float(zamk_w_oknie["CzasRealizacjiDni"].median())
        if len(zamk_w_oknie) else None,
        "czas_realizacji_faktyczny_srednia_dni": float(zamk_w_oknie["CzasRealizacjiDni"].mean())
        if len(zamk_w_oknie) else None,
        "tygodnie_na_obsluzenie_zaleglosci": w_toku_teraz / sr_zamk if sr_zamk else None,
    }
    projekcja = pd.DataFrame([{
        "tydzien_od": (pd.Timestamp(trend["tydzien_od"].iloc[-1]) + pd.Timedelta(days=7 * k)).date(),
        "prognoza_w_toku": max(0.0, w_toku_teraz + netto * k),
    } for k in range(1, horyzont_tygodni + 1)])
    wynik[f"prognoza_w_toku_za_{horyzont_tygodni}_tyg"] = float(projekcja["prognoza_w_toku"].iloc[-1])
    return wynik, projekcja


def dominujaca_faza(m: Model, g: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Dla każdego zapytania faza, w której spędziło najwięcej czasu, i podsumowanie „typów” zapytań."""
    o = proces.os_czasu(m, g)
    real = proces.czas_realizacji(m, g)
    if o.empty:
        return pd.DataFrame(), pd.DataFrame()
    dom = o.loc[o.groupby("TenderEnquiryId")["CzasWFazieDni"].idxmax(),
                ["TenderEnquiryId", "TenderEnquiryNumber", "Client", "OwnerName", "Faza", "CzasWFazieDni"]]
    dom = dom.join(real[["Zamkniete", "CzasRealizacjiDni"]], on="TenderEnquiryId")
    dom["Udział fazy w czasie realizacji"] = dom["CzasWFazieDni"] / dom["CzasRealizacjiDni"]
    zamk = dom[dom["Zamkniete"]]
    pod = dom.groupby("Faza").agg(**{"Zapytania": ("TenderEnquiryId", "size"),
                                     "W toku": ("Zamkniete", lambda s: int((~s).sum())),
                                     "Czas w fazie – mediana (dni)": ("CzasWFazieDni", "median"),
                                     "Udział fazy – mediana": ("Udział fazy w czasie realizacji", "median")})
    pod = pod.join(zamk.groupby("Faza")["CzasRealizacjiDni"].median().rename("Realizacja zamkniętych – mediana (dni)"))
    pod.insert(1, "% zapytań", pod["Zapytania"] / pod["Zapytania"].sum())
    pod = pod.reset_index().rename(columns={"Faza": "Dominująca faza"})
    pod["Kolejność"] = pod["Dominująca faza"].map(proces.KOLEJNOSC_FAZ)
    pod = pod.sort_values("Zapytania", ascending=False).drop(columns="Kolejność").reset_index(drop=True)
    lista = dom.rename(columns={"Faza": "Dominująca faza"}).drop(columns="TenderEnquiryId")
    return pod, lista.sort_values("CzasWFazieDni", ascending=False).reset_index(drop=True)
