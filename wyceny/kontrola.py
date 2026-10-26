"""Kontrole jakości danych i pierwsze zestawienia (krok 1)."""
from __future__ import annotations

import pandas as pd

from .model import Model

ZAKONCZONE = "Zakończone"
OTWARTE = "Otwarte"


def czy_cofniecie(decyzja: pd.Series) -> pd.Series:
    d = decyzja.fillna("")
    return d.str.startswith("Zwrócono") | d.str.startswith("Wymagana")


def _przyklady(df: pd.DataFrame, kol: str = "TenderEnquiryNumber", n: int = 8) -> str:
    wartosci = df[kol].dropna().drop_duplicates().head(n)
    return ", ".join(str(int(v)) if isinstance(v, float) else str(v) for v in wartosci)


def kontrole(m: Model) -> pd.DataFrame:
    z, wf, zap = m.zadania, m.workflow, m.zapytania
    wiersze = []

    def dodaj(nazwa: str, df: pd.DataFrame, opis: str, kol: str = "TenderEnquiryNumber"):
        wiersze.append({"Kontrola": nazwa, "Liczba": len(df), "Opis": opis,
                        "Przykłady": _przyklady(df, kol) if len(df) else ""})

    znane_wf = set(wf["InstanceId"])
    dodaj("Zapytania bez workflow w danych",
          zap[~zap["WorkflowId"].isin(znane_wf)],
          "WorkflowId zapytania nie występuje wśród pobranych workflow (np. zapytanie bez uruchomionego obiegu).")
    glowne_bez = wf[(wf["glebokosc"] == 0) & wf["TenderEnquiryId"].isna()]
    dodaj("Workflow główne bez zapytania", glowne_bez,
          "Główne instancje workflow niepowiązane z zapytaniem z zakresu (np. zapytanie sprzed daty startu "
          "albo usunięte). Ich zadania nie trafiają do analiz zapytań.", kol="WorkflowDefinitionId")
    dodaj("Zadania zakończone bez czasu zakończenia",
          z[(z["Stan"] == ZAKONCZONE) & z["ZakonczonoUtc"].isna()],
          "Decyzja jest zapisana, ale nie udało się ustalić jej momentu (brak zdarzenia, EndTime i kroku następnego).")
    dodaj("Zadania z ujemnym czasem", z[z["CzasDni"] < 0],
          "Zakończenie przed przypisaniem – błąd danych lub stref czasowych.")
    dodaj("Zadania bez przypisania", z[z["AssignedPrincipal"].isna()],
          "Brak atrybutu AssignedPrincipal.")
    kons = z[z["CzyKonsultacja"]]
    dodaj("Konsultacje bez zadania nadrzędnego", kons[~kons["ZadanieGlowneZnalezione"]],
          "Nie znaleziono zadania, z którego przekazano konsultację (np. pominięte lub spoza zakresu).")
    dodaj("Zawieszone konsultacje", z[z["ZawieszonaKonsultacja"]],
          "Konsultacja nadal otwarta, choć zadanie główne zostało już zakończone albo zapytanie zamknięte. "
          "Zawyża liczbę otwartych zadań i obciążenie konsultantów.")
    dodaj("Otwarte zadania w zamkniętych zapytaniach",
          z[(z["Stan"] == OTWARTE) & z["ZapytanieOtwarte"].eq(False)],
          "Workflow czeka na decyzję, choć zapytanie ma status zamknięty (9–13).")
    return pd.DataFrame(wiersze)


def podsumowanie(m: Model) -> pd.DataFrame:
    z, wf, zap = m.zadania, m.workflow, m.zapytania
    kons = z[z["CzyKonsultacja"]]
    pozycje = [
        ("Zapytania (od daty startu)", len(zap)),
        ("  w tym otwarte", int(zap["CzyOtwarte"].sum())),
        ("Instancje workflow", len(wf)),
        ("  w tym konsultacje (ForwardWorkflow)", int((wf["WorkflowDefinitionId"] == "ForwardWorkflow").sum())),
        ("Zadania użytkowników (bez zadań wyjścia z obiegu)", len(z)),
        ("  w tym konsultacje", len(kons)),
        ("  otwarte", int((z["Stan"] == OTWARTE).sum())),
        ("  otwarte konsultacje", int((kons["Stan"] == OTWARTE).sum())),
        ("  zawieszone konsultacje", int(z["ZawieszonaKonsultacja"].sum())),
        ("Maks. poziom konsultacji", int(z["PoziomKonsultacji"].max()) if len(z) else 0),
        ("Zapytania z co najmniej jedną konsultacją", int(kons["TenderEnquiryId"].nunique())),
    ]
    return pd.DataFrame(pozycje, columns=["Pozycja", "Wartość"])


def etapy(m: Model) -> pd.DataFrame:
    """Pierwsze spojrzenie: zadania główne wg etapu i grupy, z obciążeniem konsultacjami."""
    z = m.zadania[m.zadania["TenderEnquiryId"].notna()]
    glowne = z[~z["CzyKonsultacja"]].copy()
    glowne["Cofniecie"] = czy_cofniecie(glowne["Decyzja"])
    kons = z[z["CzyKonsultacja"] & z["ZadanieGlowneZnalezione"]]

    klucze = ["Prompt", "Grupa"]
    wynik = glowne.groupby(klucze, dropna=False).agg(
        **{"Zadania": ("Id", "size"), "Cofnięcia": ("Cofniecie", "sum")})
    zak = glowne[glowne["Stan"] == ZAKONCZONE].groupby(klucze, dropna=False)["CzasDni"].agg(
        **{"Zakończone": "size", "Mediana (dni)": "median",
           "P80 (dni)": lambda s: s.quantile(0.8), "Maks. (dni)": "max"})
    otw = glowne[glowne["Stan"] == OTWARTE].groupby(klucze, dropna=False)["CzasDni"].agg(
        **{"Otwarte": "size", "Otwarte – mediana oczekiwania (dni)": "median"})
    wynik = wynik.join(zak, how="left").join(otw, how="left")
    for kol in ("Zakończone", "Otwarte"):
        wynik[kol] = wynik[kol].fillna(0).astype(int)
    wynik = wynik[["Zadania", "Zakończone", "Otwarte", "Mediana (dni)", "P80 (dni)", "Maks. (dni)",
                   "Otwarte – mediana oczekiwania (dni)", "Cofnięcia"]]
    k = kons.groupby(["EtapGlowny", "GrupaGlowna"], dropna=False).agg(
        **{"Konsultacje": ("Id", "size"),
           "Zadania z konsultacją": ("ZadanieGlowne", "nunique"),
           "Maks. poziom konsultacji": ("PoziomKonsultacji", "max"),
           "Konsultacje – mediana (dni)": ("CzasDni", "median"),
           "Konsultacje – suma (osobodni)": ("CzasDni", "sum"),
           "Zawieszone konsultacje": ("ZawieszonaKonsultacja", "sum")})
    k.index.names = ["Prompt", "Grupa"]
    wynik = wynik.join(k, how="left").reset_index()
    wynik = wynik.rename(columns={"Prompt": "Etap (zadanie)"})
    wynik["% zadań z konsultacją"] = wynik["Zadania z konsultacją"] / wynik["Zadania"]
    return wynik.sort_values("Zadania", ascending=False).reset_index(drop=True)


def konsultacje(m: Model) -> pd.DataFrame:
    z = m.zadania
    k = z[z["CzyKonsultacja"]]
    return k[["TenderEnquiryNumber", "Client", "OwnerName", "EtapGlowny", "GrupaGlowna", "StanGlownego",
              "PoziomKonsultacji", "Runda", "Konsultant", "Stan", "Decyzja", "Przypisano", "Zakonczono",
              "CzasDni", "ZawieszonaKonsultacja"]].reset_index(drop=True)
