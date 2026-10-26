"""Ładowanie konfiguracji z config.toml (z wartościami domyślnymi z config.example.toml)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

KATALOG_PROJEKTU = Path(__file__).resolve().parent.parent


@dataclass
class Baza:
    serwer: str = "splmcd08"
    baza: str = "WYCENY"
    sterownik: str = "ODBC Driver 18 for SQL Server"
    szyfrowanie: bool = True
    ufaj_certyfikatowi: bool = True

    def connection_string(self) -> str:
        return (
            f"DRIVER={{{self.sterownik}}};SERVER={self.serwer};DATABASE={self.baza};"
            f"Trusted_Connection=yes;Encrypt={'yes' if self.szyfrowanie else 'no'};"
            f"TrustServerCertificate={'yes' if self.ufaj_certyfikatowi else 'no'};"
        )


@dataclass
class Analiza:
    pierwsze_zapytanie_id: int = 758
    data_startu: date = date(2026, 4, 1)
    pomijane_zadania: list[str] = field(
        default_factory=lambda: ["Ewentualne zmiany w RFQ", "Ewentualne zmiany w BOM"])
    statusy_zamkniete: list[int] = field(default_factory=lambda: [9, 10, 11, 12, 13])
    strefa_czasowa: str = "Europe/Warsaw"
    prog_porzucenia_dni: float = 30


@dataclass
class Konfiguracja:
    baza: Baza = field(default_factory=Baza)
    analiza: Analiza = field(default_factory=Analiza)
    katalog_danych: Path = KATALOG_PROJEKTU / "data"
    katalog_raportow: Path = KATALOG_PROJEKTU / "raporty"


def wczytaj(sciezka: Path | None = None) -> Konfiguracja:
    """Wczytuje config.toml; brakujące klucze biorą wartości domyślne."""
    sciezka = sciezka or KATALOG_PROJEKTU / "config.toml"
    kfg = Konfiguracja()
    if not sciezka.exists():
        return kfg
    with open(sciezka, "rb") as fh:
        dane = tomllib.load(fh)
    for klucz, wartosc in dane.get("baza", {}).items():
        setattr(kfg.baza, klucz, wartosc)
    for klucz, wartosc in dane.get("analiza", {}).items():
        if klucz == "data_startu" and isinstance(wartosc, str):
            wartosc = date.fromisoformat(wartosc)
        setattr(kfg.analiza, klucz, wartosc)
    katalogi = dane.get("katalogi", {})
    if "dane" in katalogi:
        kfg.katalog_danych = (KATALOG_PROJEKTU / katalogi["dane"]).resolve()
    if "raporty" in katalogi:
        kfg.katalog_raportow = (KATALOG_PROJEKTU / katalogi["raporty"]).resolve()
    return kfg
