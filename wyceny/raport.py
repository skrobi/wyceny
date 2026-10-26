"""Raport Excel."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import xlsxwriter

from . import kontrola
from .model import Model

NAVY = "#1F3864"

SLOWNIK = [
    ("Zapytanie", "Zapytanie ofertowe (TenderEnquiry). Analizowane są te, które wpłynęły od daty startu."),
    ("Workflow główny", "Obieg zapytania (TenderEnquiryWorkflow) wskazany w TenderEnquiry.WorkflowId."),
    ("Zadanie", "Krok workflow czekający na decyzję użytkownika (UserTask, zdarzenie UserAction)."),
    ("Etap", "Opis zadania (Prompt), np. „Uzupełnienie technologii (DTT/W)”."),
    ("Grupa", "Grupa AD, której przypisano zadanie (RMS.APP_WYCENY_<grupa>)."),
    ("Konsultacja", "Zadanie powstałe przez „Przekaż do” (ForwardWorkflow), przypisane konkretnej osobie."),
    ("Poziom konsultacji", "1 = przekazane z zadania głównego, 2 = przekazane z konsultacji itd."),
    ("Runda", "Kolejne zadanie w tym samym obiegu konsultacji (ponowna konsultacja tej samej sprawy)."),
    ("Zadanie główne", "Zadanie w workflow głównym, od którego zaczął się łańcuch konsultacji."),
    ("Zawieszona konsultacja", "Konsultacja otwarta, choć zadanie główne jest już zakończone lub zapytanie zamknięte."),
    ("Cofnięcie", "Decyzja zaczynająca się od „Zwrócono…” lub „Wymagana…”."),
    ("Czas (dni)", "Od przypisania do decyzji; dla otwartych – do momentu pobrania danych. Dni kalendarzowe."),
    ("Mediana / P80", "Połowa / 80% zakończonych zadań trwała nie dłużej niż podana wartość."),
    ("Zadania wyjścia z obiegu", "„Ewentualne zmiany w RFQ/BOM” – pomijane we wszystkich zestawieniach."),
]


class Arkusz:
    def __init__(self, wb: xlsxwriter.Workbook):
        self.wb = wb
        self.f_tytul = wb.add_format({"bold": True, "font_size": 16, "font_color": NAVY})
        self.f_opis = wb.add_format({"italic": True, "font_color": "#7F7F7F"})
        self.f_data = wb.add_format({"num_format": "yyyy-mm-dd hh:mm"})
        self.f_dzien = wb.add_format({"num_format": "yyyy-mm-dd"})
        self.f_dec = wb.add_format({"num_format": "0.0"})
        self.f_pct = wb.add_format({"num_format": "0%"})
        self.f_wrap = wb.add_format({"text_wrap": True, "valign": "top"})

    def tabela(self, nazwa: str, df: pd.DataFrame, tytul: str, opis: str = "",
               szerokosci: dict[str, int] | None = None, procenty: tuple[str, ...] = ()) -> xlsxwriter.worksheet.Worksheet:
        ws = self.wb.add_worksheet(nazwa)
        ws.write(0, 0, tytul, self.f_tytul)
        if opis:
            ws.write(1, 0, opis, self.f_opis)
        start = 3
        df = df.reset_index(drop=True)
        dane = []
        for wiersz in df.itertuples(index=False):
            dane.append([None if (not isinstance(v, str) and pd.isna(v)) else
                         (v.to_pydatetime() if isinstance(v, pd.Timestamp) else
                          (v.item() if hasattr(v, "item") else v)) for v in wiersz])
        kolumny = []
        for kol in df.columns:
            fmt = None
            if pd.api.types.is_datetime64_any_dtype(df[kol]):
                fmt = self.f_data
            elif kol in procenty:
                fmt = self.f_pct
            elif pd.api.types.is_float_dtype(df[kol]):
                fmt = self.f_dec
            kolumny.append({"header": str(kol), **({"format": fmt} if fmt else {})})
        ws.add_table(start, 0, start + max(len(dane), 1), max(len(df.columns) - 1, 0), {
            "name": "t" + "".join(ch for ch in nazwa if ch.isascii() and ch.isalnum()),
            "style": "Table Style Light 9", "columns": kolumny,
            "data": dane or [[None] * len(df.columns)]})
        for i, kol in enumerate(df.columns):
            szer = (szerokosci or {}).get(kol)
            if szer is None:
                dl = max([len(str(kol))] + [len(str(v)) for v in df[kol].head(200).tolist()])
                szer = min(max(10, dl + 2), 50)
            ws.set_column(i, i, szer)
        ws.freeze_panes(start + 1, 0)
        return ws


def zapisz(m: Model, dzien, sciezka: Path) -> Path:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(sciezka))
    a = Arkusz(wb)

    pod = kontrola.podsumowanie(m)
    ws = a.tabela("Podsumowanie", pod, "Analiza wycen – podsumowanie danych",
                  f"Migawka z {dzien}, dane pobrane {m.teraz_utc:%Y-%m-%d %H:%M} UTC.",
                  szerokosci={"Pozycja": 55, "Wartość": 12})
    a.tabela("Kontrola danych", kontrola.kontrole(m), "Kontrola jakości danych",
             "Każda pozycja z liczbą > 0 wymaga sprawdzenia, zanim zaufamy dalszym analizom.",
             szerokosci={"Kontrola": 40, "Liczba": 9, "Opis": 90, "Przykłady": 50})
    a.tabela("Etapy", kontrola.etapy(m), "Etapy – pierwsze spojrzenie",
             "Zadania główne wg etapu i grupy oraz konsultacje uruchomione z tych zadań. Czasy w dniach kalendarzowych.",
             szerokosci={"Etap (zadanie)": 45}, procenty=("% zadań z konsultacją",))
    a.tabela("Konsultacje", kontrola.konsultacje(m), "Konsultacje (przekierowania)",
             "Każde zadanie „Konsultacja” z jego zadaniem głównym, poziomem i rundą.",
             szerokosci={"EtapGlowny": 40})
    z = m.zadania.drop(columns=["PrzypisanoUtc", "ZakonczonoUtc", "InstanceId", "Id", "ZadanieNadrzedne",
                                "ZadanieGlowne"])
    a.tabela("Zadania", z, "Wszystkie zadania użytkowników", "Dane źródłowe do własnych filtrów i tabel przestawnych.")
    a.tabela("Zapytania", m.zapytania, "Zapytania ofertowe", "")
    a.tabela("Słownik", pd.DataFrame(SLOWNIK, columns=["Pojęcie", "Znaczenie"]), "Słownik pojęć", "",
             szerokosci={"Pojęcie": 28, "Znaczenie": 110})
    ws.activate()
    wb.close()
    return sciezka
