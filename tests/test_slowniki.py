import tempfile
import unittest
from pathlib import Path

import pandas as pd

from wyceny import slowniki
from wyceny.config import Analiza
from wyceny.model import zbuduj
from tests import dane_testowe as d


class TestSlownikKonsultantow(unittest.TestCase):
    def test_szablon_zachowuje_uzupelnione_dzialy(self):
        model = zbuduj(d.migawka(), Analiza(pierwsze_zapytanie_id=0))
        with tempfile.TemporaryDirectory() as tmp:
            plik = Path(tmp) / "slowniki" / "konsultanci.csv"
            slowniki.aktualizuj_szablon(model, plik)
            self.assertEqual(slowniki.wczytaj(plik), {})
            df = pd.read_csv(plik, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
            self.assertEqual(set(df["eID"]), {"e5", "e6", "e7"})
            df.loc[df["eID"] == "e7", "Dzial"] = "Malowanie"
            df.to_csv(plik, sep=";", index=False, encoding="utf-8-sig")
            slowniki.aktualizuj_szablon(model, plik)  # ponowne uruchomienie nie kasuje działu
            self.assertEqual(slowniki.wczytaj(plik), {"e7": "Malowanie"})


if __name__ == "__main__":
    unittest.main()
