"""Raport Excel."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import xlsxwriter

from . import kontrola, proces, przeplyw
from .config import Analiza
from .model import Model, _do_lokalnego

NAVY = "#1F3864"

SLOWNIK = [
    ("Zapytanie", "Zapytanie ofertowe (TenderEnquiry). Analizowane są te o TenderEnquiryId od pierwszego analizowanego (758); wcześniejsze to głównie testy."),
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
    ("Faza", "Grupa etapów o tym samym celu (np. Zbieranie danych = uzupełnienia kosztów i technologii)."),
    ("Czas w fazie", "Łączny czas, gdy w fazie było otwarte choć jedno zadanie (zadania równoległe liczone raz)."),
    ("Rozpiętość fazy", "Od pierwszego przypisania do ostatniej decyzji w fazie – razem z przerwami."),
    ("Runda", "Zadania fazy nakładające się w czasie. Powrót do fazy po cofnięciu = kolejna runda."),
    ("Gałąź krytyczna", "Grupa, która w zakończonej rundzie zbierania danych skończyła ostatnia."),
    ("Opóźnienie", "O ile dni grupa ostatnia skończyła później niż przedostatnia – tyle zyskałaby cała faza."),
    ("Przyczyna opóźnienia rundy", "Grupa, której przypisano wydłużenie rundy – z uwzględnieniem zależności "
     "(np. gdy DJ kończy zaraz po DTTW, przyczyną jest DTTW)."),
    ("Czas własny po otrzymaniu danych", "Ile grupa zależna pracowała po zakończeniu grupy, na którą czekała."),
    ("Koszt pętli", "Dni od cofnięcia do ponownego dojścia sprawy do etapu, który cofał."),
    ("Zmiana zakresu", "Cofnięcie do tworzenia RFQ – celowe, by dodać lub usunąć pozycje i zachować spójny przebieg."),
    ("Terminowość", "Oddano (TransferToCustomerDate lub ostatnia decyzja w Przygotowaniu oferty) ≤ termin klienta."),
    ("Zapytania w toku (WIP)", "Rozpoczęte i niezamknięte na koniec tygodnia – zaległość."),
    ("Przepustowość", "Liczba zapytań zamkniętych w tygodniu."),
    ("Prawo Little'a", "Czas realizacji ≈ średnio w toku / przepustowość. Gdy wyraźnie większy od faktycznej mediany – "
     "część zapytań w toku stoi (porzucone) albo zaległość rośnie."),
    ("Dominująca faza", "Faza, w której zapytanie spędziło najwięcej czasu – „gdzie utknęło”."),
    ("Udział w czasie realizacji", "Suma czasów fazy / suma czasów realizacji zamkniętych zapytań."),
    ("Zadania wyjścia z obiegu", "„Ewentualne zmiany w RFQ/BOM” – pomijane we wszystkich zestawieniach."),
]


# polskie nagłówki kolumn w arkuszach analitycznych (arkusze danych źródłowych zostają z nazwami technicznymi)
NAGLOWKI = {
    "TenderEnquiryNumber": "Nr zapytania", "Client": "Klient", "OwnerName": "Właściciel", "Prompt": "Etap (zadanie)",
    "Wykonal": "Wykonał", "Przypisano": "Przypisano", "Zakonczono": "Zakończono", "CzasDni": "Czas (dni)",
    "MaksPoziom": "Maks. poziom konsultacji", "CzasWFazieDni": "Czas w fazie (dni)",
    "RozpietoscDni": "Rozpiętość (dni)", "CzyKonsultacja": "Konsultacja?", "Komu": "Komu (grupa / osoba)",
    "ZawieszonaKonsultacja": "Zawieszona konsultacja",
}


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
        df = df.reset_index(drop=True).copy()
        for kol in df.columns:  # kolumny z obiektami date -> daty Excela
            if df[kol].dtype == object and df[kol].map(lambda v: isinstance(v, date) or v is None).all() \
                    and df[kol].notna().any():
                df[kol] = pd.to_datetime(df[kol])
        dane = []
        for wiersz in df.itertuples(index=False):
            dane.append([None if (not isinstance(v, str) and pd.isna(v)) else
                         (v.to_pydatetime() if isinstance(v, pd.Timestamp) else
                          (v.item() if hasattr(v, "item") else v)) for v in wiersz])
        kolumny = []
        for kol in df.columns:
            fmt = None
            if pd.api.types.is_datetime64_any_dtype(df[kol]):
                bez_godzin = (df[kol].dropna() == df[kol].dropna().dt.normalize()).all()
                fmt = self.f_dzien if bez_godzin else self.f_data
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

    def wykres(self, ws, nazwa: str, df: pd.DataFrame, serie: list[str], kategorie: str, komorka: str,
               tytul: str, typ: str = "line", podtyp: str | None = None, os_y: str = "") -> None:
        """Wykres z danych tabeli zapisanej przez tabela() (nagłówek w wierszu 4, dane od wiersza 5)."""
        if df.empty:
            return
        kolumny = list(df.columns)
        ostatni = 3 + len(df)
        wykres = self.wb.add_chart({"type": typ, **({"subtype": podtyp} if podtyp else {})})
        k = kolumny.index(kategorie)
        for nazwa_serii in serie:
            i = kolumny.index(nazwa_serii)
            wykres.add_series({"name": [nazwa, 3, i], "categories": [nazwa, 4, k, ostatni, k],
                               "values": [nazwa, 4, i, ostatni, i]})
        wykres.set_title({"name": tytul, "name_font": {"size": 12}})
        wykres.set_x_axis({"num_format": "yyyy-mm-dd", "date_axis": True})
        wykres.set_y_axis({"name": os_y})
        wykres.set_legend({"position": "bottom"})
        wykres.set_size({"width": 900, "height": 380})
        ws.insert_chart(komorka, wykres)


def zapisz(m: Model, dzien, sciezka: Path, analiza: Analiza | None = None,
           slownik_konsultantow: dict[str, str] | None = None) -> Path:
    analiza = analiza or Analiza()
    slownik_konsultantow = slownik_konsultantow or {}
    prog = analiza.prog_porzucenia_dni
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(sciezka))
    a = Arkusz(wb)

    pod = kontrola.podsumowanie(m)
    ws = a.tabela("Podsumowanie", pod, "Analiza wycen – podsumowanie danych",
                  f"Migawka z {dzien}, dane pobrane {m.teraz_utc:%Y-%m-%d %H:%M} UTC.",
                  szerokosci={"Pozycja": 55, "Wartość": 12})
    a.tabela("Kontrola danych", kontrola.kontrole(m, tuple(analiza.statusy_przekazane)), "Kontrola jakości danych",
             "Pozycje „Do sprawdzenia” z liczbą > 0 wymagają wyjaśnienia, zanim zaufamy dalszym analizom.",
             szerokosci={"Kontrola": 40, "Liczba": 9, "Opis": 90, "Przykłady": 50})
    g = proces.zadania_glowne(m)
    trend = przeplyw.trend_tygodniowy(m, g)
    trend_tab = trend.rename(columns={
        "tydzien_od": "Tydzień od", "pelny_tydzien": "Pełny tydzień", "nowe_zapytania": "Nowe",
        "zamkniete_zapytania": "Zamknięte", "przyrost_netto": "Przyrost netto",
        "zapytania_w_toku_koniec_tygodnia": "W toku (koniec tygodnia)",
        "otwarte_zadania_koniec_tygodnia": "Otwarte zadania (koniec tygodnia)",
        "mediana_realizacji_zamknietych_dni": "Realizacja zamkniętych – mediana (dni)"})
    ws_p = a.tabela("Przepływ", trend_tab, "Przepływ zapytań tydzień po tygodniu",
                    "Nowe = pierwsze zadanie w tygodniu; zamknięte = ostatnia decyzja zamkniętego zapytania. "
                    "Ostatni tydzień jest niepełny.")
    a.wykres(ws_p, "Przepływ", trend_tab, ["Nowe", "Zamknięte", "W toku (koniec tygodnia)"], "Tydzień od",
             "K4" if len(trend_tab.columns) < 10 else "J4", "Napływ, zamknięcia i zapytania w toku", os_y="zapytania")
    prognoza, projekcja = przeplyw.prognoza(m, g, trend)
    prog_tab = pd.DataFrame([(k.replace("_", " "), v.isoformat() if isinstance(v, date) else v)
                             for k, v in prognoza.items()], columns=["Miara", "Wartość"])
    ws_pr = a.tabela("Prognoza", prog_tab, "Prognoza zaległości",
                     "Średnie z ostatnich pełnych tygodni; prawo Little'a: czas realizacji ≈ średnio w toku / "
                     "zamykanych tygodniowo × 7. Projekcja zakłada, że napływ i przepustowość się nie zmienią.",
                     szerokosci={"Miara": 50, "Wartość": 14})
    if not projekcja.empty:
        r0 = len(prog_tab) + 6
        ws_pr.write(r0, 0, "Projekcja zapytań w toku", a.f_tytul)
        for i, w in enumerate(projekcja.itertuples(index=False), start=r0 + 1):
            ws_pr.write_datetime(i, 0, pd.Timestamp(w.tydzien_od).to_pydatetime(), a.f_dzien)
            ws_pr.write_number(i, 1, w.prognoza_w_toku, a.f_dec)
    zal = przeplyw.zaleglosc_wg_fazy(m, g).rename(columns={"tydzien_od": "Tydzień od"})
    ws_z = a.tabela("Zaległość wg fazy", zal, "Zapytania w toku wg fazy (koniec tygodnia)",
                    "Faza zapytania = najdalsza faza spośród jego otwartych zadań głównych.")
    a.wykres(ws_z, "Zaległość wg fazy", zal, [k for k in zal.columns if k != "Tydzień od"], "Tydzień od",
             "B" + str(len(zal) + 7), "Zapytania w toku wg fazy", typ="column", podtyp="stacked", os_y="zapytania")
    dom_pod, dom_lista = przeplyw.dominujaca_faza(m, g)
    a.tabela("Dominująca faza", dom_pod, "Gdzie utyka zapytanie – faza, w której spędziło najwięcej czasu",
             "Typy zapytań wg dominującej fazy. Lista zapytań – arkusz „Dominująca faza – lista”.",
             szerokosci={"Dominująca faza": 28}, procenty=("% zapytań", "Udział fazy – mediana"))
    a.tabela("Fazy", proces.fazy(m, g), "Fazy procesu",
             "Czas w fazie liczony dla faz zakończonych; udział w czasie realizacji – dla zamkniętych zapytań.",
             szerokosci={"Faza": 28},
             procenty=("% zapytań z powrotem do fazy", "Udział w czasie realizacji"))
    zal = ", ".join(f"{k} czeka na {'/'.join(v)}" for k, v in analiza.zaleznosci_grup.items()) or "brak"
    a.tabela("Zbieranie danych",
             proces.galaz_krytyczna(g, analiza.zaleznosci_grup, analiza.tolerancja_zaleznosci_dni),
             "Faza równoległa – kto wydłuża zbieranie danych",
             f"„Przyczyna” uwzględnia zależności ({zal}): gdy grupa zależna kończy do "
             f"{analiza.tolerancja_zaleznosci_dni:g} dnia po grupie, na którą czeka, opóźnienie idzie na tamtą.",
             szerokosci={"Grupa": 14}, procenty=("% rund, w których przyczyną",))
    a.tabela("Zależności grup", proces.zaleznosci_grup(g, analiza.zaleznosci_grup, analiza.tolerancja_zaleznosci_dni),
             "Weryfikacja zależności między grupami",
             "Czy grupa zależna rzeczywiście kończy zaraz po grupie, na którą czeka, i ile pracuje sama po otrzymaniu danych.",
             procenty=("% kończy po grupie, na którą czeka", "% kończy w tolerancji po niej",
                       "% zamykanych przez tę samą osobę"))
    t = proces.terminowosc(m, g, analiza.statusy_przekazane)
    a.tabela("Terminowość", t.rename(columns=NAGLOWKI), "Terminowość ofert przekazanych klientowi",
             "Data oddania: TransferToCustomerDate, a gdy brak – ostatnia decyzja w „Przygotowaniu oferty”.",
             szerokosci={"Źródło daty oddania": 30})
    p = proces.petle(m, g)
    a.tabela("Pętle", proces.petle_podsumowanie(p), "Pętle cofnięć – koszt",
             "Koszt pętli = dni od cofnięcia do ponownego dojścia sprawy do etapu, który cofał. "
             "„Zmiana zakresu” = powrót do tworzenia RFQ (np. dodanie lub usunięcie pozycji).",
             szerokosci={"Etap cofający": 40, "Typ pętli": 40})
    a.tabela("Długie oferty", proces.profil_dlugich(m, g), "Przygotowanie oferty trwające ponad 14 dni",
             "Czym kończą się długie zadania przygotowania oferty – pomaga odróżnić pracę od oczekiwania.",
             szerokosci={"Decyzja": 40})
    a.tabela("Konsultacje a czas", proces.wplyw_konsultacji(g), "Czas zadań z konsultacjami i bez",
             "Zakończone zadania główne; tylko etapy, w których były konsultacje.",
             szerokosci={"Etap (zadanie)": 45})
    a.tabela("Konsultacje wg działu", proces.konsultacje_wg_dzialu(m, slownik_konsultantow),
             "Konsultacje wg działu konsultanta",
             f"Działy ze słownika {analiza.slownik_konsultantow} – uzupełnij kolumnę Dzial, by zmniejszyć „(nieprzypisany)”.",
             szerokosci={"Dział": 28, "Etapy": 60})
    a.tabela("Obciążenie konsultantów", proces.obciazenie_konsultantow(m, slownik_konsultantow),
             "Obciążenie konsultantów", "Maks. otwartych jednocześnie – ile konsultacji osoba miała naraz w szczycie.",
             szerokosci={"Konsultant": 32, "Etapy": 60})
    a.tabela("Etapy", kontrola.etapy(m), "Etapy – pierwsze spojrzenie",
             "Zadania główne wg etapu i grupy oraz konsultacje uruchomione z tych zadań. Czasy w dniach kalendarzowych.",
             szerokosci={"Etap (zadanie)": 45}, procenty=("% zadań z konsultacją",))
    a.tabela("Rozkład czasów", proces.rozklad(g), "Rozkład czasów zadań",
             "Liczba zakończonych zadań głównych w przedziałach czasu. Dwa skupiska = etap o „dwóch obliczach”.",
             szerokosci={"Etap (zadanie)": 45})
    a.tabela("Porzucone", proces.porzucone(m, prog).rename(columns=NAGLOWKI), f"Otwarte dłużej niż {prog:g} dni",
             "Zadania i konsultacje do wyjaśnienia: czy sprawa jest jeszcze prowadzona?", szerokosci={"Etap": 40})
    a.tabela("Najdłuższe zadania", proces.najdluzsze(g).rename(columns=NAGLOWKI), "50 najdłuższych zakończonych zadań",
             "Przypadki do omówienia z zespołem.", szerokosci={"Etap (zadanie)": 40})
    o = proces.os_czasu(m, g)
    if not o.empty:
        o["Start"] = _do_lokalnego(o["StartUtc"], analiza.strefa_czasowa)
        o["Koniec"] = _do_lokalnego(o["KoniecUtc"], analiza.strefa_czasowa).where(o["FazaZakonczona"])
        o = o[["TenderEnquiryNumber", "Client", "OwnerName", "Faza", "Start", "Koniec", "CzasWFazieDni",
               "RozpietoscDni", "Zadania", "Rundy", "Otwarte", "Konsultacje", "Cofnięcia", "Grupy"]
              ].rename(columns=NAGLOWKI)
    a.tabela("Oś czasu", o, "Oś czasu zapytań – zapytanie × faza",
             "Koniec pusty = faza w toku. Filtruj po numerze zapytania, żeby zobaczyć jego przebieg.",
             szerokosci={"Grupy": 40})
    a.tabela("Dominująca faza – lista", dom_lista.rename(columns=NAGLOWKI), "Dominująca faza każdego zapytania", "",
             szerokosci={"Dominująca faza": 28}, procenty=("Udział fazy w czasie realizacji",))
    a.tabela("Pętle – lista", p.drop(columns=["TenderEnquiryId"], errors="ignore").rename(columns=NAGLOWKI),
             "Wszystkie cofnięcia", "", szerokosci={"Etap cofający": 40, "Typ pętli": 40})
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
