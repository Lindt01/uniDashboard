"""Tests für das Einlesen der Excel-Datei (daten.py).

Die Tests erzeugen kleine Excel-Dateien im temporären Ordner von pytest,
damit jeder Fall gezielt und unabhängig von der echten uni.xlsx geprüft
werden kann. Zusätzlich wird geprüft, dass beispiel.xlsx gültig bleibt.
"""

from datetime import date, datetime, time
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

import daten

BEISPIEL = Path(__file__).parent.parent / "beispiel.xlsx"


def excel_anlegen(pfad: Path, blaetter: dict[str, list[list]]) -> Path:
    """Schreibt eine Excel-Datei mit den angegebenen Blättern und Zeilen.

    Args:
        pfad: Zieldatei.
        blaetter: Blattname -> Zeilen (erste Zeile = Kopfzeile).

    Returns:
        Der Pfad der geschriebenen Datei.
    """
    mappe = openpyxl.Workbook()
    mappe.remove(mappe.active)
    for name, zeilen in blaetter.items():
        blatt = mappe.create_sheet(name)
        for zeile in zeilen:
            blatt.append(zeile)
    mappe.save(pfad)
    return pfad


# ---------------------------------------------------------------- Aufgaben

def test_aufgaben_status_wird_zu_wahrheitswert(tmp_path):
    pfad = excel_anlegen(tmp_path / "a.xlsx", {"Aufgabenliste": [
        ["Modul", "Woche", "Status", "Notiz"],
        ["Mathe", 1, "Done", "Übungsblatt"],
        ["Mathe", 1, "X", "Test"],
        ["Mathe", 2, " done ", "Klein und mit Leerzeichen"],
    ]})
    aufgaben = daten.lade_aufgaben(pfad)
    assert aufgaben["Erledigt"].tolist() == [True, False, True]


def test_aufgaben_entfernt_leerzeichen_und_leere_zeilen(tmp_path):
    # "Finanzierung " mit Leerzeichen kam in der echten Tabelle vor
    pfad = excel_anlegen(tmp_path / "a.xlsx", {"Aufgabenliste": [
        ["Modul", "Woche", "Status", "Notiz"],
        ["Finanzierung ", 1, "X", " Video "],
        [None, None, None, None],
        ["Finanzierung", 2, "X", None],
    ]})
    aufgaben = daten.lade_aufgaben(pfad)
    assert aufgaben["Modul"].tolist() == ["Finanzierung", "Finanzierung"]
    assert aufgaben["Notiz"].tolist() == ["Video", ""]
    assert aufgaben["Woche"].dtype.kind == "i"


# ---------------------------------------------------------------- Fächer

def test_faecher_liest_nur_bis_zur_ersten_leeren_zeile(tmp_path):
    pfad = excel_anlegen(tmp_path / "f.xlsx", {"Fächer": [
        ["Fächer", "Vorlesung", "Übung", "Prüfung"],
        ["Mathe", "Fr 8-10", "Do 8-10", "11.02, 9:00"],
        ["AI", "Mo 14-16", None, "TBA"],
        [None, None, None, None],
        ["Notiz unterhalb", None, None, None],
    ]})
    faecher = daten.lade_faecher(pfad)
    assert faecher["Fach"].tolist() == ["Mathe", "AI"]
    assert faecher.loc[0, "Prüfungstermin"] == datetime(2027, 2, 11, 9, 0)
    assert pd.isna(faecher.loc[1, "Prüfungstermin"])


@pytest.mark.parametrize("eingabe, erwartet", [
    ("11.02, 9:00", datetime(2027, 2, 11, 9, 0)),
    ("11.02., 09:00", datetime(2027, 2, 11, 9, 0)),
    ("1.3 10:30", datetime(2027, 3, 1, 10, 30)),
    ("05.12, 14:00", datetime(2026, 12, 5, 14, 0)),
    (datetime(2027, 2, 9, 10, 0), datetime(2027, 2, 9, 10, 0)),
    ("TBA", None),
    ("\\", None),
    (None, None),
])
def test_pruefungstermin(eingabe, erwartet):
    assert daten.pruefungstermin(eingabe) == erwartet


# ---------------------------------------------------------------- Stundenplan

def test_stundenplan_rechnet_uhrzeiten_in_stunden_um(tmp_path):
    pfad = excel_anlegen(tmp_path / "s.xlsx", {"Stundenplan": [
        ["Fach", "Art", "Tag", "Von", "Bis", "Raum"],
        ["Mathe", "VL", "Fr", time(8, 0), time(9, 30), None],
    ]})
    plan = daten.lade_stundenplan(pfad)
    assert plan.loc[0, "Von"] == 8.0
    assert plan.loc[0, "Bis"] == 9.5
    assert plan.loc[0, "Raum"] == ""


def test_in_stunden_mit_datetime():
    assert daten.in_stunden(datetime(2026, 1, 1, 16, 45)) == 16.75


def test_parallele_termine_bekommen_eigene_spuren():
    plan = pd.DataFrame({
        "Fach": ["Multimedia", "AI", "Seminar"],
        "Tag": ["Mo", "Mo", "Mo"],
        "Von": [16.0, 16.0, 18.0],
        "Bis": [18.0, 18.0, 20.0],
    })
    ergebnis = daten.lanes_bestimmen(plan).set_index("Fach")
    assert sorted([ergebnis.loc["Multimedia", "Spur"], ergebnis.loc["AI", "Spur"]]) == [0, 1]
    assert ergebnis.loc["Multimedia", "Spuren"] == 2
    # Beginnt genau, wenn die anderen enden: keine Überschneidung
    assert ergebnis.loc["Seminar", "Spuren"] == 1
    assert ergebnis.loc["Seminar", "Spur"] == 0


def test_termine_an_verschiedenen_tagen_stoeren_sich_nicht():
    plan = pd.DataFrame({
        "Fach": ["A", "B"], "Tag": ["Mo", "Di"], "Von": [10.0, 10.0], "Bis": [12.0, 12.0],
    })
    assert daten.lanes_bestimmen(plan)["Spuren"].tolist() == [1, 1]


# ---------------------------------------------------------------- Wochen

@pytest.mark.parametrize("tag, woche", [
    (date(2026, 10, 19), 1),
    (date(2026, 10, 25), 1),
    (date(2026, 10, 26), 2),
    (date(2027, 2, 10), 17),
    (date(2026, 10, 18), 0),
])
def test_aktuelle_woche(tag, woche):
    assert daten.aktuelle_woche(tag) == woche


# ---------------------------------------------------------------- Beispieldatei

def test_beispieldatei_ist_vollstaendig_lesbar():
    aufgaben = daten.lade_aufgaben(BEISPIEL)
    faecher = daten.lade_faecher(BEISPIEL)
    plan = daten.lade_stundenplan(BEISPIEL)
    assert len(aufgaben) > 0 and len(faecher) > 0 and len(plan) > 0
    assert set(plan["Tag"]) <= set(daten.WOCHENTAGE)
    assert (plan["Von"] < plan["Bis"]).all()
