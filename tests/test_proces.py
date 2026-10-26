import unittest

import pandas as pd

from wyceny import proces
from wyceny.config import Analiza
from wyceny.model import zbuduj
from tests import dane_testowe as d

T = pd.Timestamp


class TestFunkcjePomocnicze(unittest.TestCase):
    def test_suma_przedzialow_bez_podwajania(self):
        p = pd.Series([T("2026-09-01"), T("2026-09-02"), T("2026-09-10")])
        k = pd.Series([T("2026-09-04"), T("2026-09-03"), T("2026-09-11")])
        self.assertAlmostEqual(proces.suma_przedzialow(p, k), 4.0)

    def test_rundy(self):
        p = pd.Series([T("2026-09-01"), T("2026-09-01"), T("2026-09-07")], index=[10, 11, 12])
        k = pd.Series([T("2026-09-03"), T("2026-09-06"), T("2026-09-08")], index=[10, 11, 12])
        self.assertEqual(proces.rundy(p, k).tolist(), [1, 1, 2])

    def test_faza_po_opisie(self):
        self.assertEqual(proces.faza("Uzupełnienie kosztów zakupowych (DZ)"), proces.FAZA_ZBIERANIA)
        self.assertEqual(proces.faza("Uzupełnienie technologii (DTT/W)"), proces.FAZA_ZBIERANIA)
        self.assertEqual(proces.faza("Kalkulacja finansowa (DF-W)"), "Kalkulacja finansowa")
        self.assertEqual(proces.faza("Wymagana akcja serwisowa"), proces.INNE)


class TestProces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = zbuduj(d.migawka(), Analiza(pierwsze_zapytanie_id=0))
        cls.g = proces.zadania_glowne(cls.m)

    def test_konsultacje_przypisane_do_zadania_glownego(self):
        g = self.g.set_index("Id")
        self.assertEqual(g.loc["p-dttw", "Konsultacje"], 3)
        self.assertEqual(g.loc["p-dttw", "MaksPoziom"], 2)
        self.assertEqual(g.loc["p-dj", "Konsultacje"], 0)

    def test_os_czasu_zbieranie_danych(self):
        o = proces.os_czasu(self.m, self.g).set_index(["TenderEnquiryNumber", "Faza"])
        zb = o.loc[(2179, proces.FAZA_ZBIERANIA)]
        self.assertEqual(zb["Rundy"], 2)
        self.assertAlmostEqual(zb["CzasWFazieDni"], 6.0)
        self.assertTrue(zb["FazaZakonczona"])
        kal = o.loc[(2179, "Kalkulacja finansowa")]
        self.assertEqual((kal["Rundy"], kal["Cofnięcia"]), (2, 1))

    def test_galaz_krytyczna(self):
        k = proces.galaz_krytyczna(self.g).set_index("Grupa")
        self.assertEqual(k.loc["DZ", "Razy ostatnia"], 1)
        self.assertAlmostEqual(k.loc["DZ", "Opóźnienie gdy ostatnia – mediana (dni)"], 2.0)
        self.assertEqual(k.loc["DJ", "Razy ostatnia"], 0)
        # zapytanie 2178: runda w toku – DTTW czeka
        self.assertEqual(k.loc["DTTW", "Rundy otwarte, w których czeka"], 1)

    def test_fazy_udzial_dla_zamknietych(self):
        f = proces.fazy(self.m, self.g).set_index("Faza")
        # zapytanie 2179: realizacja 9 dni 8 h, zbieranie danych 6 dni
        self.assertAlmostEqual(f.loc[proces.FAZA_ZBIERANIA, "Udział w czasie realizacji"], 6.0 / (9 + 8 / 24),
                               places=4)
        self.assertEqual(f.loc[proces.FAZA_ZBIERANIA, "Teraz w fazie"], 1)

    def test_wplyw_konsultacji_i_rozklad(self):
        w = proces.wplyw_konsultacji(self.g)
        self.assertIn("Weryfikacja dokumentacji technicznej", set(w["Etap (zadanie)"]))
        r = proces.rozklad(self.g).set_index("Etap (zadanie)")
        self.assertEqual(r.loc["Kalkulacja finansowa (DF-W)", "1–3 dni"], 2)

    def test_porzucone(self):
        p = proces.porzucone(self.m, 30)
        self.assertEqual(set(p["Etap"]), {"Uzupełnienie technologii (DTT/W)", "Weryfikacja dokumentacji technicznej"})


if __name__ == "__main__":
    unittest.main()
