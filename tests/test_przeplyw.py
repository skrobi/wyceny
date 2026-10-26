import unittest
from datetime import date

from wyceny import proces, przeplyw
from wyceny.config import Analiza
from wyceny.model import zbuduj
from tests import dane_testowe as d


class TestPrzeplyw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = zbuduj(d.migawka(), Analiza(pierwsze_zapytanie_id=0))
        cls.g = proces.zadania_glowne(cls.m)
        cls.trend = przeplyw.trend_tygodniowy(cls.m, cls.g)

    def test_trend_napływ_i_zamkniecia(self):
        t = self.trend.set_index("tydzien_od")
        self.assertEqual(int(t["nowe_zapytania"].sum()), 3)
        self.assertEqual(int(t["zamkniete_zapytania"].sum()), 2)
        # tydzień od 31.08: 2179 i 2180 rozpoczęte, 2180 zamknięte 6.09; w toku na koniec: 2178 i 2179
        w = t.loc[date(2026, 8, 31)]
        self.assertEqual((w["nowe_zapytania"], w["zamkniete_zapytania"], w["zapytania_w_toku_koniec_tygodnia"]),
                         (2, 1, 2))
        self.assertFalse(bool(self.trend["pelny_tydzien"].iloc[-1]))
        self.assertTrue(bool(self.trend["pelny_tydzien"].iloc[-2]))

    def test_zaleglosc_wg_fazy(self):
        z = przeplyw.zaleglosc_wg_fazy(self.m, self.g).set_index("tydzien_od").loc[date(2026, 8, 31)]
        # 2179 – otwarta kalkulacja; 2178 – brak otwartego zadania głównego (tylko konsultacja)
        self.assertEqual(z["Kalkulacja finansowa"], 1)
        self.assertEqual(z[przeplyw.BEZ_ZADANIA], 1)

    def test_prognoza(self):
        p, projekcja = przeplyw.prognoza(self.m, self.g, self.trend, okno_tygodni=8, horyzont_tygodni=4)
        self.assertEqual(p["okno_tygodni"], 8)
        self.assertAlmostEqual(p["srednio_nowych_tygodniowo"], 2 / 8)
        self.assertAlmostEqual(p["srednio_zamknietych_tygodniowo"], 2 / 8)
        self.assertEqual(p["kierunek"], "stabilna")
        self.assertEqual(p["zapytania_w_toku_teraz"], 1)
        self.assertEqual(len(projekcja), 4)
        self.assertAlmostEqual(p["tygodnie_na_obsluzenie_zaleglosci"], 4.0)

    def test_dominujaca_faza(self):
        pod, lista = przeplyw.dominujaca_faza(self.m, self.g)
        pod = pod.set_index("Dominująca faza")
        self.assertEqual(pod.loc[proces.FAZA_ZBIERANIA, "Zapytania"], 3)
        self.assertEqual(pod.loc[proces.FAZA_ZBIERANIA, "W toku"], 1)
        self.assertEqual(len(lista), 3)


if __name__ == "__main__":
    unittest.main()
