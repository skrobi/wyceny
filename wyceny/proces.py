"""Krok 2: model procesu – fazy, oś czasu zapytania, faza równoległa i wpływ konsultacji.

Pojęcia:
- Faza: grupa etapów (zadań) o tym samym celu, np. „Zbieranie danych” = wszystkie uzupełnienia kosztów
  i technologii, wykonywane równolegle.
- Czas w fazie: łączny czas, w którym w fazie było otwarte co najmniej jedno zadanie
  (suma przedziałów bez nakładania się). Zadania równoległe nie sumują się, powroty po cofnięciu tak.
- Runda: zbiór zadań fazy nakładających się w czasie. Powrót do fazy po cofnięciu = kolejna runda.
- Gałąź krytyczna: w zakończonej rundzie zbierania danych grupa, która skończyła ostatnia –
  to ona wyznaczyła długość rundy. Opóźnienie = o ile skończyła później niż następna grupa.
"""
from __future__ import annotations

import pandas as pd

from .model import Model

FAZA_ZBIERANIA = "Zbieranie danych"
INNE = "Inne"

# (faza, początki opisów zadań) – kolejność listy = kolejność faz w procesie
FAZY: list[tuple[str, tuple[str, ...]]] = [
    ("Tworzenie RFQ", ("Utworzenie RFQ", "Uzupełnienie Zapytania")),
    ("Weryfikacja ITC", ("Weryfikacja ITC",)),
    ("Weryfikacja RFQ", ("Weryfikacja RFQ",)),
    ("Weryfikacja dokumentacji", ("Weryfikacja dokumentacji technicznej",)),
    ("Uzupełnienie BOM", ("Uzupełnienie BOM",)),
    ("Rozeznanie produkcyjne", ("Rozeznanie produkcyjne",)),
    (FAZA_ZBIERANIA, ("Uzupełnienie technologii", "Uzupełnienie kosztów", "Weryfikacja klasyfikacji i autoryzacji",
                      "Pozostałe koszty")),
    ("Kalkulacja finansowa", ("Kalkulacja finansowa",)),
    ("Przygotowanie oferty", ("Przygotowanie oferty",)),
]
KOLEJNOSC_FAZ = {nazwa: i + 1 for i, (nazwa, _) in enumerate(FAZY)} | {INNE: len(FAZY) + 1}

PRZEDZIALY_DNI = [(0, 1, "< 1 dnia"), (1, 3, "1–3 dni"), (3, 7, "3–7 dni"), (7, 14, "7–14 dni"),
                  (14, 30, "14–30 dni"), (30, float("inf"), "> 30 dni")]


def faza(opis: object) -> str:
    if isinstance(opis, str):
        for nazwa, prefiksy in FAZY:
            if opis.startswith(prefiksy):
                return nazwa
    return INNE


def _dni(td: pd.Series | pd.Timedelta):
    return td.dt.total_seconds() / 86400 if isinstance(td, pd.Series) else td.total_seconds() / 86400


def suma_przedzialow(poczatki: pd.Series, konce: pd.Series) -> float:
    """Długość sumy przedziałów (w dniach) – nakładające się fragmenty liczone raz."""
    razem, kon_biez, start_biez = 0.0, None, None
    for p, k in sorted(zip(poczatki, konce)):
        if kon_biez is None or p > kon_biez:
            if kon_biez is not None:
                razem += (kon_biez - start_biez).total_seconds()
            start_biez, kon_biez = p, k
        else:
            kon_biez = max(kon_biez, k)
    if kon_biez is not None:
        razem += (kon_biez - start_biez).total_seconds()
    return razem / 86400


def rundy(poczatki: pd.Series, konce: pd.Series) -> pd.Series:
    """Numer rundy dla każdego zadania: zadania nakładające się w czasie tworzą jedną rundę."""
    kolejnosc = poczatki.sort_values(kind="stable").index
    numer, kon_biez, wynik = 0, None, {}
    for i in kolejnosc:
        if kon_biez is None or poczatki[i] > kon_biez:
            numer += 1
            kon_biez = konce[i]
        else:
            kon_biez = max(kon_biez, konce[i])
        wynik[i] = numer
    return pd.Series(wynik).reindex(poczatki.index)


def zadania_glowne(m: Model) -> pd.DataFrame:
    """Zadania workflow głównego z fazą, efektywnym końcem, rundą i liczbą konsultacji."""
    z = m.zadania
    g = z[~z["CzyKonsultacja"]].copy()
    g["Faza"] = g["Prompt"].map(faza)
    g["KolejnoscFazy"] = g["Faza"].map(KOLEJNOSC_FAZ)
    otwarte = g["Stan"].isin(["Otwarte", "Wstrzymane"])
    # koniec do liczenia przedziałów: decyzja; otwarte – moment pobrania; anulowane bez decyzji – zero długości
    g["KoniecUtc"] = g["ZakonczonoUtc"].where(g["ZakonczonoUtc"].notna(),
                                             pd.Series(m.teraz_utc, index=g.index).where(otwarte, g["PrzypisanoUtc"]))
    g["CzyOtwarte"] = otwarte
    kons = z[z["CzyKonsultacja"] & z["ZadanieGlowneZnalezione"]]
    liczba = kons.groupby("ZadanieGlowne").size()
    poziom = kons.groupby("ZadanieGlowne")["PoziomKonsultacji"].max()
    g["Konsultacje"] = g["Id"].map(liczba).fillna(0).astype(int)
    g["MaksPoziom"] = g["Id"].map(poziom).fillna(0).astype(int)
    d = g["Decyzja"].fillna("")
    g["Cofniecie"] = d.str.startswith("Zwrócono") | d.str.startswith("Wymagana")
    g["Runda"] = 0
    for _, idx in g.groupby(["TenderEnquiryId", "Faza"]).groups.items():
        g.loc[idx, "Runda"] = rundy(g.loc[idx, "PrzypisanoUtc"], g.loc[idx, "KoniecUtc"]).to_numpy()
    return g


def czas_realizacji(m: Model, g: pd.DataFrame) -> pd.DataFrame:
    """Jeden wiersz na zapytanie: od pierwszego zadania do ostatniej decyzji (zamknięte) lub do teraz."""
    zap = m.zapytania.set_index("TenderEnquiryId")
    agg = g.groupby("TenderEnquiryId").agg(StartUtc=("PrzypisanoUtc", "min"), KoniecUtc=("KoniecUtc", "max"),
                                          Otwarte=("CzyOtwarte", "sum"))
    agg["Zamkniete"] = ~agg.index.map(zap["CzyOtwarte"]).astype(bool)
    agg.loc[~agg["Zamkniete"], "KoniecUtc"] = m.teraz_utc
    agg["CzasRealizacjiDni"] = _dni(agg["KoniecUtc"] - agg["StartUtc"])
    return agg


def os_czasu(m: Model, g: pd.DataFrame) -> pd.DataFrame:
    """Jeden wiersz na zapytanie i fazę."""
    wiersze = []
    for (zid, fz), grp in g.groupby(["TenderEnquiryId", "Faza"]):
        wiersze.append({
            "TenderEnquiryId": zid, "Faza": fz, "KolejnoscFazy": KOLEJNOSC_FAZ[fz],
            "StartUtc": grp["PrzypisanoUtc"].min(), "KoniecUtc": grp["KoniecUtc"].max(),
            "CzasWFazieDni": suma_przedzialow(grp["PrzypisanoUtc"], grp["KoniecUtc"]),
            "Zadania": len(grp), "Rundy": int(grp["Runda"].max()), "Otwarte": int(grp["CzyOtwarte"].sum()),
            "Konsultacje": int(grp["Konsultacje"].sum()), "Cofnięcia": int(grp["Cofniecie"].sum()),
            "Grupy": ", ".join(sorted(grp["Grupa"].dropna().unique())),
        })
    o = pd.DataFrame(wiersze)
    if o.empty:
        return o
    o["RozpietoscDni"] = _dni(o["KoniecUtc"] - o["StartUtc"])
    o["FazaZakonczona"] = o["Otwarte"] == 0
    zap = m.zapytania.set_index("TenderEnquiryId")
    o["TenderEnquiryNumber"] = o["TenderEnquiryId"].map(zap["TenderEnquiryNumber"])
    o["Client"] = o["TenderEnquiryId"].map(zap["Client"])
    o["OwnerName"] = o["TenderEnquiryId"].map(zap["OwnerName"])
    return o.sort_values(["TenderEnquiryNumber", "KolejnoscFazy"]).reset_index(drop=True)


def fazy(m: Model, g: pd.DataFrame) -> pd.DataFrame:
    """Podsumowanie faz: czasy, powtórzenia i udział w czasie realizacji zamkniętych zapytań."""
    o = os_czasu(m, g)
    real = czas_realizacji(m, g)
    zamkniete = set(real.index[real["Zamkniete"]])
    suma_realizacji = real.loc[real["Zamkniete"], "CzasRealizacjiDni"].sum()
    wiersze = []
    for fz, grp in o.groupby("Faza"):
        zak = grp[grp["FazaZakonczona"]]
        w_zamk = grp[grp["TenderEnquiryId"].isin(zamkniete)]
        wiersze.append({
            "Faza": fz, "Kolejność": KOLEJNOSC_FAZ[fz],
            "Zapytania": len(grp),
            "Teraz w fazie": int((~grp["FazaZakonczona"]).sum()),
            "Czas w fazie – mediana (dni)": zak["CzasWFazieDni"].median(),
            "Czas w fazie – P80 (dni)": zak["CzasWFazieDni"].quantile(0.8) if len(zak) else None,
            "Czas w fazie – maks. (dni)": zak["CzasWFazieDni"].max(),
            "% zapytań z powrotem do fazy": (grp["Rundy"] > 1).mean(),
            "Cofnięcia": int(grp["Cofnięcia"].sum()),
            "Konsultacje": int(grp["Konsultacje"].sum()),
            "Udział w czasie realizacji": (w_zamk["CzasWFazieDni"].sum() / suma_realizacji
                                           if suma_realizacji else None),
        })
    wynik = pd.DataFrame(wiersze).sort_values("Kolejność").drop(columns="Kolejność").reset_index(drop=True)
    return wynik


def galaz_krytyczna(g: pd.DataFrame) -> pd.DataFrame:
    """Faza zbierania danych: która grupa najczęściej kończy rundę ostatnia i o ile ją wydłuża."""
    zb = g[(g["Faza"] == FAZA_ZBIERANIA) & g["Grupa"].notna()]
    stat: dict[str, dict] = {}

    def s(grupa):
        return stat.setdefault(grupa, {"Rundy z udziałem": 0, "Razy ostatnia": 0, "Opóźnienia": [],
                                       "Czasy": [], "Teraz blokuje": 0})

    for _, runda in zb.groupby(["TenderEnquiryId", "Runda"]):
        po_grupie = runda.groupby("Grupa").agg(start=("PrzypisanoUtc", "min"), koniec=("KoniecUtc", "max"),
                                               otwarte=("CzyOtwarte", "sum"))
        for grupa, w in po_grupie.iterrows():
            s(grupa)["Rundy z udziałem"] += 1
            if w["otwarte"] == 0:
                s(grupa)["Czasy"].append(_dni(w["koniec"] - w["start"]))
            else:
                s(grupa)["Teraz blokuje"] += 1
        if po_grupie["otwarte"].sum() > 0 or len(po_grupie) < 2:
            continue
        kolejnosc = po_grupie["koniec"].sort_values(ascending=False)
        ostatnia = kolejnosc.index[0]
        s(ostatnia)["Razy ostatnia"] += 1
        s(ostatnia)["Opóźnienia"].append(_dni(kolejnosc.iloc[0] - kolejnosc.iloc[1]))

    wiersze = []
    for grupa, w in stat.items():
        op = pd.Series(w["Opóźnienia"], dtype=float)
        cz = pd.Series(w["Czasy"], dtype=float)
        wiersze.append({
            "Grupa": grupa, "Rundy z udziałem": w["Rundy z udziałem"], "Razy ostatnia": w["Razy ostatnia"],
            "% rund, w których ostatnia": w["Razy ostatnia"] / w["Rundy z udziałem"],
            "Czas gałęzi – mediana (dni)": cz.median(), "Czas gałęzi – P80 (dni)": cz.quantile(0.8) if len(cz) else None,
            "Opóźnienie gdy ostatnia – mediana (dni)": op.median(),
            "Opóźnienie – suma (dni)": op.sum(),
            "Rundy otwarte, w których czeka": w["Teraz blokuje"],
        })
    if not wiersze:
        return pd.DataFrame()
    return pd.DataFrame(wiersze).sort_values("Opóźnienie – suma (dni)", ascending=False).reset_index(drop=True)


def wplyw_konsultacji(g: pd.DataFrame) -> pd.DataFrame:
    """Czas zakończonych zadań głównych z konsultacjami i bez – wg etapu."""
    zak = g[g["Stan"] == "Zakończone"]
    wiersze = []
    for (etap, grupa), grp in zak.groupby(["Prompt", "Grupa"], dropna=False):
        z_k, bez = grp[grp["Konsultacje"] > 0], grp[grp["Konsultacje"] == 0]
        if z_k.empty:
            continue
        wiersze.append({
            "Etap (zadanie)": etap, "Grupa": grupa,
            "Bez konsultacji – zadania": len(bez), "Bez konsultacji – mediana (dni)": bez["CzasDni"].median(),
            "Bez konsultacji – P80 (dni)": bez["CzasDni"].quantile(0.8) if len(bez) else None,
            "Z konsultacjami – zadania": len(z_k), "Z konsultacjami – mediana (dni)": z_k["CzasDni"].median(),
            "Z konsultacjami – P80 (dni)": z_k["CzasDni"].quantile(0.8),
            "Różnica median (dni)": z_k["CzasDni"].median() - bez["CzasDni"].median() if len(bez) else None,
            "Konsultacji na zadanie – średnio": z_k["Konsultacje"].mean(),
            "Maks. poziom": int(z_k["MaksPoziom"].max()),
        })
    if not wiersze:
        return pd.DataFrame()
    return pd.DataFrame(wiersze).sort_values("Z konsultacjami – zadania", ascending=False).reset_index(drop=True)


def rozklad(g: pd.DataFrame) -> pd.DataFrame:
    """Liczba zakończonych zadań głównych w przedziałach czasu – pokazuje, czy etap ma „dwa oblicza”."""
    zak = g[g["Stan"] == "Zakończone"].copy()
    etykiety = [e for _, _, e in PRZEDZIALY_DNI]
    granice = [a for a, _, _ in PRZEDZIALY_DNI] + [float("inf")]
    zak["Przedział"] = pd.cut(zak["CzasDni"], bins=granice, labels=etykiety, right=False)
    tab = pd.crosstab([zak["Prompt"], zak["Grupa"]], zak["Przedział"]).reindex(columns=etykiety, fill_value=0)
    tab.insert(0, "Zadania", tab.sum(axis=1))
    tab = tab.reset_index().rename(columns={"Prompt": "Etap (zadanie)"})
    tab.columns.name = None
    return tab.sort_values("Zadania", ascending=False).reset_index(drop=True)


def porzucone(m: Model, prog_dni: float) -> pd.DataFrame:
    z = m.zadania
    p = z[(z["Stan"] == "Otwarte") & (z["CzasDni"] > prog_dni)].copy()
    zap = m.zapytania.set_index("TenderEnquiryId")
    p["Status zapytania"] = p["TenderEnquiryId"].map(zap["Status"])
    p["Etap"] = p["EtapGlowny"].where(p["CzyKonsultacja"], p["Prompt"])
    p["Komu"] = p["Konsultant"].where(p["CzyKonsultacja"], p["Grupa"])
    return p[["TenderEnquiryNumber", "Client", "OwnerName", "Status zapytania", "Etap", "CzyKonsultacja", "Komu",
              "Przypisano", "CzasDni", "ZawieszonaKonsultacja"]].sort_values("CzasDni", ascending=False)


def najdluzsze(g: pd.DataFrame, ile: int = 50) -> pd.DataFrame:
    zak = g[g["Stan"] == "Zakończone"].nlargest(ile, "CzasDni")
    return zak[["TenderEnquiryNumber", "Client", "OwnerName", "Faza", "Prompt", "Grupa", "Wykonal", "Decyzja",
                "Przypisano", "Zakonczono", "CzasDni", "Konsultacje", "MaksPoziom", "Runda"]].reset_index(drop=True)
