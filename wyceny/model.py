"""Model procesu zbudowany z migawki: drzewo workflow, zadania użytkowników i konsultacje.

Najważniejsze fakty o danych (szczegóły: docs/model-danych.md):
- Każde zapytanie ma główny workflow (TenderEnquiry.WorkflowId).
- „Przekaż do” tworzy podworkflow ForwardWorkflow z Reference = <InstanceId rodzica>.<Id przekazanego kroku>.
  Konsultacje mogą być wielopoziomowe (ForwardWorkflow > ForwardWorkflow > …).
- Zadanie użytkownika to krok z EventName = 'UserAction'; decyzja jest w EventData (EventPublished = 1).
- Czasy w tabelach wfc.* są w UTC.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Analiza
from .migawka import Migawka

PREFIKS_GRUPY = "rms.app_wyceny_"
DEF_KONSULTACJI = "ForwardWorkflow"

STATUSY_ZAPYTANIA = {
    0: "Tworzenie RFQ", 1: "Weryfikacja ITC", 2: "Weryfikacja RFQ", 3: "Weryfikacja dokumentacji",
    4: "Uzupełnienie BOM", 5: "Rozeznanie produkcyjne", 6: "Zbieranie danych", 7: "Wycena",
    8: "Przygotowanie oferty", 9: "Przekazano do klienta", 10: "Anulowany", 11: "Zamknięta",
    12: "Brak technicznych możliwości realizacji", 13: "Zakończona wycena",
    14: "Generowanie podsumowania pliku", 15: "Kalkulacja finansowa", 16: "Przygotowanie oferty",
}

# WorkflowCore: status instancji workflow i kroku
WF_URUCHOMIONY, WF_WSTRZYMANY = 0, 1
KROK_ZAKONCZONY, KROK_CZEKA_NA_ZDARZENIE = 3, 5


ZAKRES_OK = "W zakresie"
ZAKRES_PRZED_STARTEM = "Zapytanie spoza zakresu"
ZAKRES_KONSULTACJA_PRZED_STARTEM = "Konsultacja z obiegu sprzed daty granicznej"
ZAKRES_BRAK = "Brak zapytania"


@dataclass
class Model:
    teraz_utc: pd.Timestamp
    zapytania: pd.DataFrame
    workflow: pd.DataFrame
    zadania: pd.DataFrame            # tylko zadania zapytań z zakresu (TenderEnquiryId >= pierwsze_zapytanie_id)
    zadania_poza_zakresem: pd.DataFrame
    data_startu: object = None
    pierwsze_zapytanie_id: int | None = None


def _rozpakuj(wartosc):
    """Wartości ExtensionAttribute są zapisane jako JSON („"tekst"”)."""
    if not isinstance(wartosc, str):
        return wartosc
    try:
        v = json.loads(wartosc)
        return v if isinstance(v, str) else wartosc
    except ValueError:
        return wartosc


def _grupa(przypisano: object) -> str | None:
    """Kod grupy z nazwy grupy AD (RMS.APP_WYCENY_DS -> DS); osoba -> None."""
    if not isinstance(przypisano, str):
        return None
    if przypisano.lower().startswith(PREFIKS_GRUPY):
        return przypisano[len(PREFIKS_GRUPY):]
    return None


def _drzewo_workflow(wf: pd.DataFrame) -> pd.DataFrame:
    """Rodzic, korzeń i głębokość każdej instancji workflow."""
    wf = wf.copy()
    ref = wf["Reference"].fillna("").astype(str)
    czesci = ref.str.split(".", n=1, expand=True).reindex(columns=[0, 1])
    znane = set(wf["InstanceId"])
    wf["rodzic"] = czesci[0].where(czesci[0].isin(znane))
    wf["krok_rodzica"] = czesci[1].where(wf["rodzic"].notna())

    rodzic = dict(zip(wf["InstanceId"], wf["rodzic"]))
    korzen, glebokosc = {}, {}
    for inst in wf["InstanceId"]:
        biezacy, poziom, odwiedzone = inst, 0, {inst}
        while isinstance(rodzic.get(biezacy), str) and poziom < 50:
            biezacy = rodzic[biezacy]
            if biezacy in odwiedzone:
                break
            odwiedzone.add(biezacy)
            poziom += 1
        korzen[inst], glebokosc[inst] = biezacy, poziom
    wf["korzen"] = wf["InstanceId"].map(korzen)
    wf["glebokosc"] = wf["InstanceId"].map(glebokosc)
    return wf


def _do_lokalnego(kol: pd.Series, strefa: str) -> pd.Series:
    return kol.dt.tz_localize("UTC").dt.tz_convert(strefa).dt.tz_localize(None)


def zbuduj(m: Migawka, analiza: Analiza, teraz_utc: pd.Timestamp | None = None) -> Model:
    # „teraz” = moment pobrania migawki, żeby raport z migawki był powtarzalny
    teraz_utc = teraz_utc or m.pobrano_utc

    # ---------- zapytania ----------
    zap = m.zapytania.copy()
    zap["WorkflowId"] = zap["WorkflowId"].astype("string").str.lower()
    # filtr także tutaj, żeby starsze migawki (pobrane z innym zakresem) dawały ten sam wynik
    przed_progiem = zap["TenderEnquiryId"] < (analiza.pierwsze_zapytanie_id or 0)
    wf_spoza_zakresu = set(zap.loc[przed_progiem, "WorkflowId"].dropna())
    zap = zap[~przed_progiem].copy()
    zap["Status"] = zap["StatusCode"].map(STATUSY_ZAPYTANIA)
    zap["CzyOtwarte"] = ~zap["StatusCode"].isin(analiza.statusy_zamkniete)

    # ---------- workflow ----------
    wf = _drzewo_workflow(m.workflow)
    zap_po_wf = dict(zip(zap["WorkflowId"], zap["TenderEnquiryId"]))
    wf["TenderEnquiryId"] = wf["korzen"].map(zap_po_wf).astype("Int64")
    wszystkie = set(m.powiazania["WorkflowId"].dropna().astype(str).str.lower()) | wf_spoza_zakresu
    korzen_ma_rodzica = wf["korzen"].map(dict(zip(wf["InstanceId"], wf["Reference"].fillna("")))).ne("")
    wf["Zakres"] = np.select(
        [wf["TenderEnquiryId"].notna(), wf["korzen"].isin(wszystkie), korzen_ma_rodzica],
        [ZAKRES_OK, ZAKRES_PRZED_STARTEM, ZAKRES_KONSULTACJA_PRZED_STARTEM], default=ZAKRES_BRAK)

    # ---------- zadania użytkowników ----------
    kroki = m.kroki.merge(
        wf[["PersistenceId", "InstanceId", "WorkflowDefinitionId", "Status", "glebokosc",
            "krok_rodzica", "TenderEnquiryId", "UserNameFrom", "Comment"]]
        .rename(columns={"PersistenceId": "WorkflowId", "Status": "StatusWorkflow"}),
        on="WorkflowId", how="inner")

    zad = kroki[kroki["EventName"] == "UserAction"].copy()

    atr = m.atrybuty.copy()
    atr["AttributeValue"] = atr["AttributeValue"].map(_rozpakuj)
    atr = (atr.drop_duplicates(["ExecutionPointerId", "AttributeKey"])
              .pivot_table(index="ExecutionPointerId", columns="AttributeKey", values="AttributeValue",
                           aggfunc="first")
              .reindex(columns=["AssignedPrincipal", "Prompt", "ActionUser"]))
    zad = zad.merge(atr, left_on="PersistenceId", right_index=True, how="left")

    # moment decyzji: zdarzenie UserAction -> EndTime kroku -> start kroku następnego
    czas_zdarzenia = m.zdarzenia.groupby("EventKey")["EventTime"].min()
    nastepny = (m.kroki.dropna(subset=["PredecessorId"])
                .groupby(["WorkflowId", "PredecessorId"])["StartTime"].min())
    po_nastepnym = pd.Series(
        nastepny.reindex(pd.MultiIndex.from_arrays([zad["WorkflowId"], zad["Id"]])).to_numpy(),
        index=zad.index)
    koniec = (zad["EventKey"].map(czas_zdarzenia)
              .fillna(zad["EndTime"].where(zad["Status"] == KROK_ZAKONCZONY))
              .fillna(po_nastepnym))
    opublikowane = zad["EventPublished"].fillna(0).astype(int) == 1
    zad["ZakonczonoUtc"] = koniec.where(opublikowane)

    zad["Stan"] = np.select(
        [opublikowane,
         (zad["Status"] == KROK_CZEKA_NA_ZDARZENIE) & (zad["StatusWorkflow"] == WF_URUCHOMIONY),
         (zad["Status"] == KROK_CZEKA_NA_ZDARZENIE) & (zad["StatusWorkflow"] == WF_WSTRZYMANY)],
        ["Zakończone", "Otwarte", "Wstrzymane"], default="Anulowane")

    zad["Decyzja"] = zad["EventOutcome"]
    zad["Wykonal"] = zad["ActionUser"].fillna(zad["EventUser"])
    zad["Grupa"] = zad["AssignedPrincipal"].map(_grupa)
    zad["CzyKonsultacja"] = zad["WorkflowDefinitionId"] == DEF_KONSULTACJI
    zad["Konsultant"] = zad["AssignedPrincipal"].where(zad["CzyKonsultacja"])

    # ---------- konsultacje: zadanie nadrzędne, zadanie główne, poziom ----------
    # ForwardWorkflow wskazuje w Reference krok, z którego go przekazano
    zad["ZadanieNadrzedne"] = zad["krok_rodzica"].where(zad["CzyKonsultacja"])
    nadrzedne = dict(zip(zad["Id"], zad["ZadanieNadrzedne"]))
    glowne, poziom = {}, {}
    for zid in zad["Id"]:
        biezace, p, odwiedzone = zid, 0, {zid}
        while isinstance(nadrzedne.get(biezace), str) and p < 50:
            biezace = nadrzedne[biezace]
            if biezace in odwiedzone:
                break
            odwiedzone.add(biezace)
            p += 1
        glowne[zid], poziom[zid] = biezace, p
    zad["ZadanieGlowne"] = zad["Id"].map(glowne)
    zad["PoziomKonsultacji"] = zad["Id"].map(poziom)
    po_id = zad.set_index("Id")
    zad["ZadanieGlowneZnalezione"] = zad["ZadanieGlowne"].isin(po_id.index) & (
        ~zad["CzyKonsultacja"] | zad["ZadanieGlowne"].ne(zad["Id"]))
    for kol_src, kol_dst in (("Prompt", "EtapGlowny"), ("Grupa", "GrupaGlowna"), ("Stan", "StanGlownego")):
        zad[kol_dst] = zad["ZadanieGlowne"].map(po_id[kol_src])
    # runda: kolejne zadanie w tym samym ForwardWorkflow (ponowna konsultacja w tym samym obiegu)
    zad["Runda"] = (zad.groupby("InstanceId")["StartTime"].rank(method="first")
                    .where(zad["CzyKonsultacja"]).astype("Int64"))

    # ---------- wykluczenia (zadania wyjścia z obiegu) ----------
    def pomijane(opis: pd.Series) -> pd.Series:
        wynik = pd.Series(False, index=opis.index)
        for prefiks in analiza.pomijane_zadania:
            wynik |= opis.fillna("").str.startswith(prefiks)
        return wynik

    zad = zad[~pomijane(zad["Prompt"]) & ~pomijane(zad["EtapGlowny"])].copy()

    # ---------- czasy ----------
    zad["PrzypisanoUtc"] = zad["StartTime"]
    zad["CzasDni"] = ((zad["ZakonczonoUtc"].fillna(teraz_utc) - zad["PrzypisanoUtc"])
                      .dt.total_seconds() / 86400).round(2)
    zad["Przypisano"] = _do_lokalnego(zad["PrzypisanoUtc"], analiza.strefa_czasowa)
    zad["Zakonczono"] = _do_lokalnego(zad["ZakonczonoUtc"], analiza.strefa_czasowa)

    zad = zad.merge(zap[["TenderEnquiryId", "TenderEnquiryNumber", "Client", "OwnerName", "CzyOtwarte"]]
                    .rename(columns={"CzyOtwarte": "ZapytanieOtwarte"}),
                    on="TenderEnquiryId", how="left")
    zad["ZawieszonaKonsultacja"] = (zad["CzyKonsultacja"] & (zad["Stan"] == "Otwarte")
                                    & (zad["StanGlownego"].isin(["Zakończone", "Anulowane"])
                                       | zad["ZapytanieOtwarte"].eq(False)))

    w_zakresie = zad["TenderEnquiryId"].notna()
    poza = zad[~w_zakresie].merge(wf[["InstanceId", "Zakres"]], on="InstanceId", how="left")
    zad = zad[w_zakresie]

    kolumny = ["TenderEnquiryId", "TenderEnquiryNumber", "Client", "OwnerName", "ZapytanieOtwarte",
               "WorkflowDefinitionId", "InstanceId", "Id", "StepId", "Prompt", "AssignedPrincipal", "Grupa",
               "CzyKonsultacja", "PoziomKonsultacji", "Runda", "Konsultant", "ZadanieNadrzedne", "ZadanieGlowne",
               "ZadanieGlowneZnalezione", "EtapGlowny", "GrupaGlowna", "StanGlownego", "Stan", "Decyzja", "Wykonal",
               "Przypisano", "Zakonczono", "PrzypisanoUtc", "ZakonczonoUtc", "CzasDni", "ZawieszonaKonsultacja",
               "UserNameFrom", "Comment"]
    zad = zad[kolumny].sort_values(["TenderEnquiryNumber", "PrzypisanoUtc"]).reset_index(drop=True)

    return Model(teraz_utc=teraz_utc, zapytania=zap, workflow=wf, zadania=zad,
                 data_startu=analiza.data_startu, pierwsze_zapytanie_id=analiza.pierwsze_zapytanie_id,
                 zadania_poza_zakresem=poza[["InstanceId", "Id", "Prompt", "Stan", "Zakres"]])
