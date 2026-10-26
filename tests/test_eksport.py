import json
import tempfile
import unittest
from pathlib import Path

from wyceny import eksport
from wyceny.config import Analiza
from wyceny.model import zbuduj
from tests import dane_testowe as d


class TestEksport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m = d.migawka()
        cls.model = zbuduj(m, Analiza(pierwsze_zapytanie_id=0))
        cls.dane = eksport.zbuduj(cls.model, m.data, 30)

    def test_json_serializowalny_i_kompletny(self):
        with tempfile.TemporaryDirectory() as tmp:
            plik = eksport.zapisz(self.dane, Path(tmp) / "a.json")
            wczytane = json.loads(plik.read_text(encoding="utf-8"))
        for klucz in ("meta", "podsumowanie", "kontrola_danych", "fazy", "zbieranie_danych_galaz_krytyczna",
                      "etapy", "konsultacje_a_czas", "konsultacje", "cofniecia", "rozklad_czasow",
                      "trend_tygodniowy", "porzucone", "najdluzsze_zadania", "czas_realizacji_zamknietych"):
            self.assertIn(klucz, wczytane)
        self.assertEqual(wczytane["schemat"], eksport.WERSJA_SCHEMATU)

    def test_brak_nazwisk_w_pliku(self):
        tekst = json.dumps(self.dane, ensure_ascii=False, default=eksport._czysc)
        for nazwisko in ("Konsultant A", "Konsultant B", "Konsultant C", "Właściciel Jan", "e459015"):
            self.assertNotIn(nazwisko, tekst)
        self.assertIn("Osoba ", tekst)

    def test_ta_sama_osoba_ten_sam_pseudonim(self):
        p = eksport.Pseudonimy(True)
        p.zarejestruj(__import__("pandas").Series(["Kowal Jan | e1", "Nowak Ewa"]))
        self.assertEqual(p("Kowal Jan | e1"), p("Kowal Jan"))
        self.assertNotEqual(p("Kowal Jan"), p("Nowak Ewa"))

    def test_bez_anonimizacji(self):
        dane = eksport.zbuduj(self.model, d.migawka().data, 30, anonimizacja=False)
        self.assertIn("Konsultant A", json.dumps(dane, ensure_ascii=False, default=eksport._czysc))

    def test_cofniecie_z_faza_powrotu(self):
        c = self.dane["cofniecia"]
        kal = [r for r in c if r["etap_cofajacy"] == "Kalkulacja finansowa (DF-W)"]
        self.assertEqual(kal[0]["faza_powrotu"], "Zbieranie danych")

    def test_trend_tygodniowy(self):
        t = self.dane["trend_tygodniowy"]
        self.assertTrue(t)
        self.assertEqual(sum(r["zamkniete_zapytania"] for r in t), 1)

    def test_czas_realizacji(self):
        r = self.dane["czas_realizacji_zamknietych"]
        self.assertEqual(r["zapytania"], 1)
        self.assertEqual(r["w_terminie_klienta"], 1.0)


if __name__ == "__main__":
    unittest.main()
