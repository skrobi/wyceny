"""Uruchamianie: python -m wyceny [pobierz | raport | wszystko] [--migawka RRRR-MM-DD] [--config ŚCIEŻKA]"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from . import config, eksport, migawka, raport
from .model import zbuduj


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m wyceny", description="Analiza przebiegu wycen.")
    p.add_argument("polecenie", nargs="?", default="wszystko", choices=["pobierz", "raport", "wszystko"],
                   help="pobierz – migawka z bazy; raport – raport z migawki; wszystko – oba (domyślnie)")
    p.add_argument("--migawka", type=date.fromisoformat, help="dzień migawki do raportu (domyślnie najnowsza)")
    p.add_argument("--config", type=Path, help="ścieżka do config.toml")
    args = p.parse_args(argv)

    kfg = config.wczytaj(args.config)
    dzien = args.migawka
    if args.polecenie in ("pobierz", "wszystko"):
        print(f"Pobieranie danych z {kfg.baza.serwer}/{kfg.baza.baza}: zapytania od Id "
              f"{kfg.analiza.pierwsze_zapytanie_id}, workflow od {kfg.analiza.data_startu}…")
        katalog = migawka.pobierz(kfg)
        print(f"Zapisano migawkę: {katalog}")
        dzien = dzien or date.fromisoformat(katalog.name)
    if args.polecenie in ("raport", "wszystko"):
        m = migawka.wczytaj(kfg, dzien)
        model = zbuduj(m, kfg.analiza)
        plik = raport.zapisz(model, m.data, kfg.katalog_raportow / f"analiza_wycen_{m.data.isoformat()}.xlsx",
                             kfg.analiza.prog_porzucenia_dni, kfg.analiza.strefa_czasowa)
        print(f"Raport: {plik}")
        dane = eksport.zbuduj(model, m.data, kfg.analiza.prog_porzucenia_dni, kfg.analiza.json_anonimizacja)
        plik_json = eksport.zapisz(dane, plik.with_suffix(".json"))
        print(f"Plik dla asystenta AI: {plik_json}")


if __name__ == "__main__":
    main()
