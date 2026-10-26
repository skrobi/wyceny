import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from wyceny import kontrola, migawka, raport
from wyceny.config import Analiza, Konfiguracja
from wyceny.model import zbuduj
from tests import dane_testowe as d


class TestMigawkaIRaport(unittest.TestCase):
    def test_migawka_z_csv_i_raport(self):
        with tempfile.TemporaryDirectory() as tmp:
            kfg = Konfiguracja(analiza=Analiza(pierwsze_zapytanie_id=0), katalog_danych=Path(tmp) / "data",
                               katalog_raportow=Path(tmp) / "raporty")
            m = d.migawka()
            katalog = kfg.katalog_danych / m.data.isoformat()
            katalog.mkdir(parents=True)
            for nazwa in migawka.TABELE:
                df = getattr(m, nazwa).copy()
                if nazwa == "kroki":  # pyodbc zwraca bit jako bool
                    df["EventPublished"] = df["EventPublished"].astype(bool)
                df.to_csv(katalog / f"{nazwa}.csv", index=False, encoding="utf-8")
            (katalog / "meta.json").write_text(json.dumps({"pobrano_utc": m.pobrano_utc.isoformat()}))

            wczytana = migawka.wczytaj(kfg)
            self.assertEqual(wczytana.pobrano_utc, m.pobrano_utc)
            model = zbuduj(wczytana, kfg.analiza)
            wzor = zbuduj(m, kfg.analiza)
            self.assertEqual(len(model.zadania), len(wzor.zadania))
            self.assertEqual(model.zadania.set_index("Id").loc["p-ds", "Stan"], "Zakończone")

            plik = raport.zapisz(model, wczytana.data, kfg.katalog_raportow / "r.xlsx")
            with zipfile.ZipFile(plik) as z:
                self.assertIn("xl/workbook.xml", z.namelist())

    def test_kontrole(self):
        model = zbuduj(d.migawka(), Analiza(pierwsze_zapytanie_id=0))
        k = kontrola.kontrole(model).set_index("Kontrola")["Liczba"]
        self.assertEqual(k["Zawieszone konsultacje"], 1)
        self.assertEqual(k["Workflow zapytań spoza zakresu"], 1)
        self.assertEqual(k["Workflow bez zapytania"], 1)
        self.assertEqual(k["Konsultacje z obiegów sprzed daty granicznej"], 1)
        self.assertEqual(k["Przekazane bez daty przekazania klientowi"], 1)
        self.assertEqual(k["Przekazane bez terminu klienta"], 0)
        self.assertEqual(k["Zadania zakończone bez czasu zakończenia"], 0)

    def test_etapy(self):
        model = zbuduj(d.migawka(), Analiza(pierwsze_zapytanie_id=0))
        e = kontrola.etapy(model).set_index("Etap (zadanie)")
        dttw = e.loc["Uzupełnienie technologii (DTT/W)"]
        self.assertEqual(dttw["Otwarte"], 1)
        self.assertEqual(dttw["Konsultacje"], 3)
        self.assertEqual(dttw["Maks. poziom konsultacji"], 2)
        self.assertEqual(e.loc["Uzupełnienie kosztów (DJ)", "Cofnięcia"], 1)


if __name__ == "__main__":
    unittest.main()
