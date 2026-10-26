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

    def test_galaz_krytyczna_bez_zaleznosci(self):
        k = proces.galaz_krytyczna(self.g).set_index("Grupa")
        self.assertEqual(k.loc["DZ", "Razy przyczyną"], 1)
        self.assertAlmostEqual(k.loc["DZ", "Opóźnienie jako przyczyna – mediana (dni)"], 2.0)
        # 2180: DJ kończy ostatnia; bez zależności przyczyną jest DJ, o 2 h względem następnej grupy (DTTW)
        self.assertEqual(k.loc["DJ", "Razy ostatnia"], 1)
        self.assertEqual(k.loc["DJ", "Razy przyczyną"], 1)
        self.assertAlmostEqual(k.loc["DJ", "Opóźnienie jako przyczyna – mediana (dni)"], 2 / 24, places=4)
        # zapytanie 2178: runda w toku – DTTW czeka
        self.assertEqual(k.loc["DTTW", "Rundy otwarte, w których czeka"], 1)

    def test_galaz_krytyczna_z_zaleznoscia_dj_od_dttw(self):
        k = proces.galaz_krytyczna(self.g, {"DJ": ["DTTW"]}, 1.0).set_index("Grupa")
        self.assertEqual(k.loc["DJ", "Razy ostatnia"], 1)
        self.assertEqual(k.loc["DJ", "Razy przyczyną"], 0)
        self.assertEqual(k.loc["DTTW", "Razy przyczyną"], 1)
        # łańcuch DTTW->DJ kończy 2 dni 2 h po DZ
        self.assertAlmostEqual(k.loc["DTTW", "Opóźnienie jako przyczyna – mediana (dni)"], 2 + 2 / 24, places=4)

    def test_weryfikacja_zaleznosci(self):
        z = proces.zaleznosci_grup(self.g, {"DJ": ["DTTW"]}, 1.0).iloc[0]
        self.assertEqual(z["Rundy z obiema grupami"], 1)
        self.assertEqual(z["% kończy w tolerancji po niej"], 1.0)
        self.assertAlmostEqual(z["Czas własny po otrzymaniu danych – mediana (dni)"], 2 / 24, places=4)
        self.assertEqual(z["% zamykanych przez tę samą osobę"], 1.0)

    def test_terminowosc_z_decyzji_oferty(self):
        t = proces.terminowosc(self.m, self.g, [9]).set_index("TenderEnquiryNumber")
        self.assertEqual(t.loc[2180, "Źródło daty oddania"], "Decyzja w Przygotowaniu oferty")
        self.assertTrue(t.loc[2180, "W terminie"])
        self.assertTrue(t.loc[2179, "W terminie"])
        pod = proces.terminowosc_podsumowanie(proces.terminowosc(self.m, self.g, [9]))
        self.assertEqual((pod["ocenione"], pod["w_terminie_odsetek"], pod["data_oddania_z_decyzji_oferty"]),
                         (2, 1.0, 1))

    def test_petle(self):
        p = proces.petle(self.m, self.g).set_index("TenderEnquiryNumber")
        kal = p.loc[2179]
        self.assertEqual(kal["Typ pętli"], "Korekta – powrót do: Zbieranie danych")
        self.assertAlmostEqual(kal["Koszt pętli (dni)"], 1 + 2 / 24, places=4)
        self.assertEqual(kal["Zadania po drodze"], 1)
        self.assertEqual(p.loc[2178, "Stan pętli"], "W toku")
        pod = proces.petle_podsumowanie(proces.petle(self.m, self.g))
        self.assertEqual(int(pod["Cofnięcia"].sum()), 2)

    def test_konsultacje_wg_dzialu_i_obciazenie(self):
        d_ = proces.konsultacje_wg_dzialu(self.m, {"e6": "Przyrządy", "e7": "Malowanie"}).set_index("Dział")
        self.assertEqual(d_.loc["Malowanie", "Konsultacje"], 2)
        self.assertEqual(d_.loc["(nieprzypisany)", "Konsultacje"], 1)
        o = proces.obciazenie_konsultantow(self.m).set_index("Konsultant")
        self.assertEqual(o.loc["Konsultant C | e7", "Maks. otwartych jednocześnie"], 1)

    def test_fazy_udzial_dla_zamknietych(self):
        f = proces.fazy(self.m, self.g).set_index("Faza")
        # zamknięte: 2179 (realizacja 9 d 8 h, zbieranie 6 d) i 2180 (realizacja 4 d 22 h, zbieranie 4 d 2 h)
        oczekiwany = (6 + 4 + 2 / 24) / (9 + 8 / 24 + 4 + 22 / 24)
        self.assertAlmostEqual(f.loc[proces.FAZA_ZBIERANIA, "Udział w czasie realizacji"], oczekiwany, places=4)
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
