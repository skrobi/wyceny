import unittest

import pandas as pd

from wyceny.config import Analiza
from wyceny.model import zbuduj
from tests import dane_testowe as d


class TestModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = zbuduj(d.migawka(), Analiza())
        cls.z = cls.m.zadania.set_index("Id")

    def test_pomija_zadania_wyjscia_z_obiegu(self):
        self.assertNotIn("p-rfq", self.z.index)

    def test_drzewo_workflow_i_zapytanie(self):
        wf = self.m.workflow.set_index("InstanceId")
        self.assertEqual(wf.loc[d.F3, "glebokosc"], 2)
        self.assertEqual(wf.loc[d.F3, "korzen"], d.M)
        self.assertEqual(wf.loc[d.F3, "TenderEnquiryId"], 410)
        self.assertTrue(pd.isna(wf.loc[d.G, "TenderEnquiryId"]))

    def test_koniec_zadania_z_kroku_nastepnego(self):
        self.assertEqual(self.z.loc["p-ds", "ZakonczonoUtc"], pd.Timestamp("2026-08-13 10:54"))

    def test_koniec_zadania_ze_zdarzenia(self):
        self.assertEqual(self.z.loc["p-dtk", "ZakonczonoUtc"], pd.Timestamp("2026-08-20 08:57"))

    def test_koniec_zadania_z_endtime(self):
        self.assertEqual(self.z.loc["p-dj", "ZakonczonoUtc"], pd.Timestamp("2026-09-10 14:25"))

    def test_stan_i_czas_otwartego(self):
        self.assertEqual(self.z.loc["p-dttw", "Stan"], "Otwarte")
        oczekiwane = (pd.Timestamp("2026-10-26 08:00") - pd.Timestamp("2026-09-10 12:21")).total_seconds() / 86400
        self.assertAlmostEqual(self.z.loc["p-dttw", "CzasDni"], oczekiwane, places=2)

    def test_grupa_z_nazwy_ad(self):
        self.assertEqual(self.z.loc["p-dttw", "Grupa"], "DTTW")
        self.assertTrue(pd.isna(self.z.loc["f2", "Grupa"]))

    def test_konsultacje_wielopoziomowe(self):
        self.assertEqual(self.z.loc["f2", "PoziomKonsultacji"], 1)
        self.assertEqual(self.z.loc["f3a", "PoziomKonsultacji"], 2)
        self.assertEqual(self.z.loc["f3a", "ZadanieGlowne"], "p-dttw")
        self.assertEqual(self.z.loc["f3a", "GrupaGlowna"], "DTTW")
        self.assertEqual(self.z.loc["f3a", "EtapGlowny"], "Uzupełnienie technologii (DTT/W)")
        self.assertEqual(self.z.loc["f3a", "Runda"], 1)
        self.assertEqual(self.z.loc["f3b", "Runda"], 2)
        self.assertEqual(self.z.loc["f2", "Konsultant"], "Konsultant B | e6")

    def test_zawieszona_konsultacja(self):
        self.assertTrue(self.z.loc["f1", "ZawieszonaKonsultacja"])
        self.assertFalse(self.z.loc["f2", "ZawieszonaKonsultacja"])

    def test_czas_lokalny(self):
        # wrzesień = czas letni, UTC+2
        self.assertEqual(self.z.loc["p-dttw", "Przypisano"], pd.Timestamp("2026-09-10 14:21"))

    def test_zadanie_bez_zapytania_zostaje_w_modelu(self):
        self.assertTrue(pd.isna(self.z.loc["g1", "TenderEnquiryId"]))


if __name__ == "__main__":
    unittest.main()
