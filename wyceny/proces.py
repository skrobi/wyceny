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

import numpy as np
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


def _rundy_zbierania(g: pd.DataFrame):
    """Rundy fazy zbierania danych: (zapytanie, runda) -> zadania pogrupowane po grupie."""
    zb = g[(g["Faza"] == FAZA_ZBIERANIA) & g["Grupa"].notna()]
    for klucz, runda in zb.groupby(["TenderEnquiryId", "Runda"]):
        ostatnie = runda.sort_values("KoniecUtc").groupby("Grupa").tail(1).set_index("Grupa")["Wykonal"]
        po_grupie = runda.groupby("Grupa").agg(start=("PrzypisanoUtc", "min"), koniec=("KoniecUtc", "max"),
                                               otwarte=("CzyOtwarte", "sum"))
        po_grupie["wykonal"] = ostatnie
        yield klucz, po_grupie


def galaz_krytyczna(g: pd.DataFrame, zaleznosci: dict[str, list[str]] | None = None,
                    tolerancja_dni: float = 1.0) -> pd.DataFrame:
    """Faza zbierania danych: która grupa wydłuża rundę.

    „Ostatnia” = grupa, która skończyła rundę ostatnia. „Przyczyna” uwzględnia zależności: jeśli ostatnia grupa
    czeka na dane innej (np. DJ na DTTW) i skończyła w granicach tolerancji po niej, opóźnienie przypisujemy
    grupie, na którą czekała. Opóźnienie = koniec łańcucha (grupa + jej poprzednicy) minus koniec
    najpóźniejszej grupy spoza łańcucha.
    """
    zaleznosci = zaleznosci or {}
    stat: dict[str, dict] = {}

    def s(grupa):
        return stat.setdefault(grupa, {"Rundy z udziałem": 0, "Razy ostatnia": 0, "Razy przyczyną": 0,
                                       "Opóźnienia": [], "Czasy": [], "Teraz blokuje": 0})

    for _, po_grupie in _rundy_zbierania(g):
        for grupa, w in po_grupie.iterrows():
            s(grupa)["Rundy z udziałem"] += 1
            if w["otwarte"] == 0:
                s(grupa)["Czasy"].append(_dni(w["koniec"] - w["start"]))
            else:
                s(grupa)["Teraz blokuje"] += 1
        if po_grupie["otwarte"].sum() > 0 or len(po_grupie) < 2:
            continue
        ostatnia = po_grupie["koniec"].idxmax()
        koniec = po_grupie.loc[ostatnia, "koniec"]
        s(ostatnia)["Razy ostatnia"] += 1
        poprzednicy = [p for p in zaleznosci.get(ostatnia, []) if p in po_grupie.index]
        przyczyna = ostatnia
        if poprzednicy:
            p = po_grupie.loc[poprzednicy, "koniec"].idxmax()
            if _dni(koniec - po_grupie.loc[p, "koniec"]) <= tolerancja_dni:
                przyczyna = p
        pozostale = po_grupie.drop(index=[ostatnia] + poprzednicy)
        if pozostale.empty:
            continue
        s(przyczyna)["Razy przyczyną"] += 1
        s(przyczyna)["Opóźnienia"].append(_dni(koniec - pozostale["koniec"].max()))

    wiersze = []
    for grupa, w in stat.items():
        op = pd.Series(w["Opóźnienia"], dtype=float)
        cz = pd.Series(w["Czasy"], dtype=float)
        wiersze.append({
            "Grupa": grupa, "Rundy z udziałem": w["Rundy z udziałem"], "Razy ostatnia": w["Razy ostatnia"],
            "Razy przyczyną": w["Razy przyczyną"],
            "% rund, w których przyczyną": w["Razy przyczyną"] / w["Rundy z udziałem"],
            "Czas gałęzi – mediana (dni)": cz.median(), "Czas gałęzi – P80 (dni)": cz.quantile(0.8) if len(cz) else None,
            "Opóźnienie jako przyczyna – mediana (dni)": op.median(),
            "Opóźnienie jako przyczyna – suma (dni)": op.sum(),
            "Rundy otwarte, w których czeka": w["Teraz blokuje"],
        })
    if not wiersze:
        return pd.DataFrame()
    return (pd.DataFrame(wiersze).sort_values("Opóźnienie jako przyczyna – suma (dni)", ascending=False)
            .reset_index(drop=True))


def zaleznosci_grup(g: pd.DataFrame, zaleznosci: dict[str, list[str]], tolerancja_dni: float = 1.0) -> pd.DataFrame:
    """Weryfikacja zależności „grupa czeka na dane innej grupy” na zakończonych rundach zbierania danych."""
    pomiary: dict[tuple[str, str], list[dict]] = {}
    for _, po_grupie in _rundy_zbierania(g):
        if po_grupie["otwarte"].sum() > 0:
            continue
        for zal, poprzednicy in zaleznosci.items():
            for pop in poprzednicy:
                if zal not in po_grupie.index or pop not in po_grupie.index:
                    continue
                z, p = po_grupie.loc[zal], po_grupie.loc[pop]
                odstep = _dni(z["koniec"] - p["koniec"])
                wlasny = max(0.0, _dni(z["koniec"] - max(z["start"], p["koniec"])))
                pomiary.setdefault((zal, pop), []).append({
                    "po": odstep >= 0, "odstep": odstep, "w_tolerancji": 0 <= odstep <= tolerancja_dni,
                    "wlasny": wlasny, "ta_sama_osoba": isinstance(z["wykonal"], str) and z["wykonal"] == p["wykonal"]})
    wiersze = []
    for (zal, pop), lista in pomiary.items():
        df = pd.DataFrame(lista)
        wiersze.append({
            "Grupa": zal, "Czeka na": pop, "Rundy z obiema grupami": len(df),
            "% kończy po grupie, na którą czeka": df["po"].mean(),
            "% kończy w tolerancji po niej": df["w_tolerancji"].mean(),
            "Odstęp końców – mediana (dni)": df["odstep"].median(),
            "Czas własny po otrzymaniu danych – mediana (dni)": df["wlasny"].median(),
            "Czas własny – P80 (dni)": df["wlasny"].quantile(0.8),
            "% zamykanych przez tę samą osobę": df["ta_sama_osoba"].mean(),
        })
    return pd.DataFrame(wiersze)


def terminowosc(m: Model, g: pd.DataFrame, statusy_przekazane: list[int]) -> pd.DataFrame:
    """Zapytania przekazane klientowi: data oddania (TransferToCustomerDate albo ostatnia decyzja w
    „Przygotowaniu oferty”), termin klienta i czy zmieszczono się w terminie."""
    zap = m.zapytania[m.zapytania["StatusCode"].isin(statusy_przekazane)].copy()
    oferta = g[(g["Faza"] == "Przygotowanie oferty") & (g["Stan"] == "Zakończone")]
    ostatnia_decyzja = oferta.groupby("TenderEnquiryId")["Zakonczono"].max()
    z_decyzji = zap["TenderEnquiryId"].map(ostatnia_decyzja)
    zap["Oddano"] = zap["TransferToCustomerDate"].fillna(z_decyzji)
    zap["Źródło daty oddania"] = np.where(zap["TransferToCustomerDate"].notna(), "TransferToCustomerDate",
                                          np.where(z_decyzji.notna(), "Decyzja w Przygotowaniu oferty", "Brak"))
    zap["Termin"] = zap["SubmissionDateRequired"]
    dni = (zap["Oddano"].dt.normalize() - zap["Termin"].dt.normalize()).dt.days
    zap["Dni po terminie"] = dni
    zap["W terminie"] = (dni <= 0).where(dni.notna())
    return zap[["TenderEnquiryNumber", "Client", "OwnerName", "Status", "Termin", "Oddano", "Źródło daty oddania",
                "Dni po terminie", "W terminie"]].sort_values("Dni po terminie", ascending=False)


def terminowosc_podsumowanie(t: pd.DataFrame) -> dict:
    ocenione = t[t["W terminie"].notna()]
    spoznione = ocenione[ocenione["W terminie"] == False]  # noqa: E712 – kolumna obiektowa z None
    return {
        "przekazane_klientowi": len(t),
        "ocenione": len(ocenione),
        "w_terminie_odsetek": float(ocenione["W terminie"].astype(bool).mean()) if len(ocenione) else None,
        "spoznione": len(spoznione),
        "spoznienie_mediana_dni": float(spoznione["Dni po terminie"].median()) if len(spoznione) else None,
        "bez_terminu_klienta": int(t["Termin"].isna().sum()),
        "data_oddania_z_decyzji_oferty": int((t["Źródło daty oddania"] == "Decyzja w Przygotowaniu oferty").sum()),
        "bez_daty_oddania": int((t["Źródło daty oddania"] == "Brak").sum()),
    }


def petle(m: Model, g: pd.DataFrame) -> pd.DataFrame:
    """Koszt pętli: każde cofnięcie – dokąd wróciło i ile dni minęło, zanim sprawa znów dotarła do etapu,
    który cofał (zadań wykonanych po drodze)."""
    c = g[g["Cofniecie"] & g["ZakonczonoUtc"].notna()]
    if c.empty:
        return pd.DataFrame()
    otwarte_zap = set(m.zapytania.loc[m.zapytania["CzyOtwarte"], "TenderEnquiryId"])
    po_zapytaniu = {zid: grp.sort_values("PrzypisanoUtc") for zid, grp in g.groupby("TenderEnquiryId")}
    wiersze = []
    for _, w in c.iterrows():
        dalsze = po_zapytaniu[w["TenderEnquiryId"]]
        dalsze = dalsze[(dalsze["PrzypisanoUtc"] >= w["ZakonczonoUtc"]) & (dalsze["Id"] != w["Id"])]
        faza_powrotu = dalsze["Faza"].iloc[0] if len(dalsze) else None
        ponownie = dalsze[dalsze["Prompt"] == w["Prompt"]]
        if len(ponownie):
            koniec_petli, stan = ponownie["PrzypisanoUtc"].iloc[0], "Wróciło do etapu"
        elif w["TenderEnquiryId"] in otwarte_zap:
            koniec_petli, stan = m.teraz_utc, "W toku"
        else:
            koniec_petli, stan = pd.NaT, "Nie wróciło (zapytanie zamknięte)"
        if faza_powrotu is None:
            typ = "Brak dalszych zadań"
        elif faza_powrotu == "Tworzenie RFQ":
            typ = "Zmiana zakresu (powrót do RFQ)"
        else:
            typ = f"Korekta – powrót do: {faza_powrotu}"
        wiersze.append({
            "TenderEnquiryId": w["TenderEnquiryId"], "TenderEnquiryNumber": w["TenderEnquiryNumber"],
            "Etap cofający": w["Prompt"], "Grupa": w["Grupa"], "Decyzja": w["Decyzja"], "Typ pętli": typ,
            "Faza powrotu": faza_powrotu, "Stan pętli": stan,
            "Koszt pętli (dni)": _dni(koniec_petli - w["ZakonczonoUtc"]) if pd.notna(koniec_petli) else None,
            "Zadania po drodze": int((dalsze["PrzypisanoUtc"] < koniec_petli).sum()) if pd.notna(koniec_petli) else None,
        })
    return pd.DataFrame(wiersze)


def petle_podsumowanie(p: pd.DataFrame) -> pd.DataFrame:
    if p.empty:
        return p
    wynik = p.groupby(["Etap cofający", "Typ pętli"], dropna=False).agg(
        **{"Cofnięcia": ("TenderEnquiryId", "size"), "Zapytania": ("TenderEnquiryId", "nunique"),
           "Koszt – mediana (dni)": ("Koszt pętli (dni)", "median"),
           "Koszt – P80 (dni)": ("Koszt pętli (dni)", lambda s: s.quantile(0.8)),
           "Koszt – suma (dni)": ("Koszt pętli (dni)", "sum"),
           "Zadania po drodze – mediana": ("Zadania po drodze", "median"),
           "W toku": ("Stan pętli", lambda s: int((s == "W toku").sum()))})
    return wynik.reset_index().sort_values("Koszt – suma (dni)", ascending=False).reset_index(drop=True)


def profil_dlugich(m: Model, g: pd.DataFrame, faza_nazwa: str = "Przygotowanie oferty",
                   prog_dni: float = 14) -> pd.DataFrame:
    """Czym kończą się długie zadania fazy: decyzja, status zapytania, rewizje."""
    d = g[(g["Faza"] == faza_nazwa) & (g["Stan"] == "Zakończone") & (g["CzasDni"] > prog_dni)].copy()
    if d.empty:
        return pd.DataFrame()
    zap = m.zapytania.set_index("TenderEnquiryId")
    d["Status zapytania"] = d["TenderEnquiryId"].map(zap["Status"])
    rewizja = zap["EnquiryRevision"] if "EnquiryRevision" in zap.columns else pd.Series(dtype=float)
    d["Rewizja > 0"] = d["TenderEnquiryId"].map(rewizja).fillna(0) > 0
    return (d.groupby("Decyzja", dropna=False)
            .agg(**{"Zadania": ("Id", "size"), "Mediana (dni)": ("CzasDni", "median"),
                    "Maks. (dni)": ("CzasDni", "max"),
                    "Zapytania anulowane": ("Status zapytania", lambda s: int((s == "Anulowany").sum())),
                    "Zapytania z rewizją": ("Rewizja > 0", "sum")})
            .reset_index().sort_values("Zadania", ascending=False).reset_index(drop=True))


def _eid(osoba: object) -> str | None:
    if not isinstance(osoba, str):
        return None
    czesci = osoba.split("|")
    return (czesci[1] if len(czesci) > 1 else czesci[0]).strip().lower()


def konsultacje_wg_dzialu(m: Model, slownik: dict[str, str]) -> pd.DataFrame:
    """Konsultacje wg działu konsultanta (słownik osoba -> dział uzupełniany przez użytkownika)."""
    k = m.zadania[m.zadania["CzyKonsultacja"]].copy()
    if k.empty:
        return pd.DataFrame()
    k["Dział"] = k["Konsultant"].map(lambda o: slownik.get(_eid(o) or "", "(nieprzypisany)"))
    zak = k[k["Stan"] == "Zakończone"]
    wynik = k.groupby("Dział").agg(**{"Konsultacje": ("Id", "size"), "Osoby": ("Konsultant", "nunique"),
                                     "Otwarte": ("Stan", lambda s: int((s == "Otwarte").sum())),
                                     "Etapy": ("EtapGlowny", lambda s: ", ".join(sorted(s.dropna().unique())[:4]))})
    czasy = zak.groupby("Dział")["CzasDni"].agg(**{"Mediana (dni)": "median",
                                                   "P80 (dni)": lambda s: s.quantile(0.8)})
    return wynik.join(czasy).reset_index().sort_values("Konsultacje", ascending=False).reset_index(drop=True)


def obciazenie_konsultantow(m: Model, slownik: dict[str, str] | None = None) -> pd.DataFrame:
    """Dla każdego konsultanta: liczba konsultacji, czas odpowiedzi i maks. liczba otwartych jednocześnie."""
    slownik = slownik or {}
    k = m.zadania[m.zadania["CzyKonsultacja"]]
    wiersze = []
    for osoba, grp in k.groupby("Konsultant"):
        konce = grp["ZakonczonoUtc"].fillna(m.teraz_utc)
        zdarzenia = sorted([(t, 1) for t in grp["PrzypisanoUtc"]] + [(t, -1) for t in konce],
                           key=lambda x: (x[0], x[1]))
        biezace = maks = 0
        for _, zmiana in zdarzenia:
            biezace += zmiana
            maks = max(maks, biezace)
        zak = grp[grp["Stan"] == "Zakończone"]["CzasDni"]
        wiersze.append({
            "Konsultant": osoba, "Dział": slownik.get(_eid(osoba) or "", "(nieprzypisany)"),
            "Konsultacje": len(grp), "Otwarte teraz": int((grp["Stan"] == "Otwarte").sum()),
            "Maks. otwartych jednocześnie": maks,
            "Czas odpowiedzi – mediana (dni)": zak.median(), "Czas odpowiedzi – P80 (dni)": zak.quantile(0.8),
            "Etapy": ", ".join(sorted(grp["EtapGlowny"].dropna().unique())[:3]),
        })
    if not wiersze:
        return pd.DataFrame()
    return pd.DataFrame(wiersze).sort_values("Konsultacje", ascending=False).reset_index(drop=True)


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
