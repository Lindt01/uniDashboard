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

from uni_dashboard import daten

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

# ---------------------------------------------------------------- Fristen

@pytest.mark.parametrize("eingabe, erwartet", [
    ("14.11", datetime(2026, 11, 14, 23, 59)),
    ("14.11.", datetime(2026, 11, 14, 23, 59)),
    ("14.11.2026", datetime(2026, 11, 14, 23, 59)),
    ("14.11, 12:00", datetime(2026, 11, 14, 12, 0)),
    (" 3.2, 9:30 ", datetime(2027, 2, 3, 9, 30)),   # Februar gehört ins Folgejahr
    (datetime(2026, 11, 14), datetime(2026, 11, 14, 23, 59)),  # Excel-Datum ohne Uhrzeit
    (datetime(2026, 11, 14, 10, 0), datetime(2026, 11, 14, 10, 0)),
    ("\\", None), ("", None), (None, None),
])
def test_frist_lesen(eingabe, erwartet):
    assert daten.frist_lesen(eingabe) == erwartet


@pytest.mark.parametrize("eingabe", ["bald", "32.13", "14/11"])
def test_frist_lesen_lehnt_unsinn_ab(eingabe):
    with pytest.raises(ValueError):
        daten.frist_lesen(eingabe)


JETZT = datetime(2026, 11, 6, 9, 0)


@pytest.mark.parametrize("frist, stufe", [
    (datetime(2026, 11, 6, 8, 59), "ueberfaellig"),
    (datetime(2026, 11, 6, 9, 1), "dringend"),
    (datetime(2026, 11, 7, 23, 59), "dringend"),
    (datetime(2026, 11, 8, 0, 0), "bald"),
    (datetime(2026, 11, 13, 23, 59), "bald"),
    (datetime(2026, 11, 14, 0, 0), "spaeter"),
    (None, None), (pd.NaT, None),
])
def test_frist_stufe_grenzen(frist, stufe):
    assert daten.frist_stufe(frist, JETZT) == stufe


@pytest.mark.parametrize("frist, text", [
    (datetime(2026, 11, 6, 8, 0), "seit 08:00"),
    (datetime(2026, 11, 5, 23, 59), "seit gestern"),
    (datetime(2026, 11, 6, 23, 59), "heute"),
    (datetime(2026, 11, 7, 12, 0), "morgen 12:00"),
    (datetime(2026, 11, 8, 23, 59), "übermorgen"),
    (datetime(2026, 11, 11, 23, 59), "in 5 Tagen"),
    (datetime(2026, 11, 20, 23, 59), "20.11."),
])
def test_frist_text(frist, text):
    assert daten.frist_text(frist, JETZT) == text


def test_aufgaben_lesen_frist_spalte(tmp_path):
    pfad = excel_anlegen(tmp_path / "a.xlsx", {"Aufgabenliste": [
        ["Modul", "Woche", "Status", "Frist", "Notiz"],
        ["Mathe", 1, "X", "14.11", "Abgabe"],
        ["Mathe", 1, "X", "\\", "ohne"],
        ["Mathe", 2, "X", datetime(2026, 11, 20), "Excel-Datum"],
    ]})
    frist = daten.lade_aufgaben(pfad)["Frist"]
    assert frist[0] == pd.Timestamp(2026, 11, 14, 23, 59)
    assert pd.isna(frist[1])
    assert frist[2] == pd.Timestamp(2026, 11, 20, 23, 59)


def test_aufgaben_ohne_frist_spalte(tmp_path):
    pfad = excel_anlegen(tmp_path / "a.xlsx", {"Aufgabenliste": [
        ["Modul", "Woche", "Status", "Notiz"], ["Mathe", 1, "X", "Test"],
    ]})
    assert daten.lade_aufgaben(pfad)["Frist"].isna().all()


def test_ungueltige_frist_nennt_zeile_und_wert(tmp_path):
    pfad = excel_anlegen(tmp_path / "a.xlsx", {"Aufgabenliste": [
        ["Modul", "Woche", "Status", "Notiz", "Frist"],
        ["Mathe", 1, "X", "ok", "14.11"],
        ["Statistik", 1, "X", "kaputt", "nächste Woche"],
    ]})
    with pytest.raises(daten.TabellenFehler, match="Zeile 3 \\(Statistik\\).*„nächste Woche“"):
        daten.lade_aufgaben(pfad)


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


# ---------------------------------------------------------------- Fehlermeldungen

AUFGABEN_KOPF = ["Modul", "Woche", "Status", "Notiz"]
PLAN_KOPF = ["Fach", "Art", "Tag", "Von", "Bis", "Raum"]


def test_fehlende_spalte_wird_mit_namen_gemeldet(tmp_path):
    pfad = excel_anlegen(tmp_path / "a.xlsx", {"Aufgabenliste": [
        ["Modul", "Woche", "Status", "Frist"],
        ["Mathe", 1, "X", "\\"],
    ]})
    with pytest.raises(daten.TabellenFehler, match="fehlt die Spalte „Notiz“") as info:
        daten.lade_aufgaben(pfad)
    assert "Aufgabenliste" in str(info.value)


def test_mehrere_fehlende_spalten_stehen_alle_in_der_meldung(tmp_path):
    pfad = excel_anlegen(tmp_path / "s.xlsx", {"Stundenplan": [["Fach", "Tag"], ["Mathe", "Mo"]]})
    with pytest.raises(daten.TabellenFehler, match="die Spalten „Art“, „Von“, „Bis“, „Raum“"):
        daten.lade_stundenplan(pfad)


def test_fehlendes_blatt_wird_gemeldet(tmp_path):
    pfad = excel_anlegen(tmp_path / "x.xlsx", {"Aufgaben": [AUFGABEN_KOPF]})
    with pytest.raises(daten.TabellenFehler, match="fehlt das Blatt „Aufgabenliste“"):
        daten.lade_aufgaben(pfad)


@pytest.mark.parametrize("woche, erwartet", [("zwei", "„zwei“"), (None, "leer"), (1.5, "„1.5“")])
def test_ungueltige_woche_nennt_zeile_und_wert(tmp_path, woche, erwartet):
    pfad = excel_anlegen(tmp_path / "a.xlsx", {"Aufgabenliste": [
        AUFGABEN_KOPF,
        ["Mathe", 1, "Done", "ok"],
        ["AI", woche, "X", "kaputt"],
    ]})
    with pytest.raises(daten.TabellenFehler, match=f"Zeile 3 \\(AI\\), ist die Woche keine ganze Zahl: {erwartet}"):
        daten.lade_aufgaben(pfad)


def test_ganze_zahl_als_kommazahl_ist_erlaubt(tmp_path):
    # Excel speichert Zahlen oft als 2.0
    pfad = excel_anlegen(tmp_path / "a.xlsx", {"Aufgabenliste": [AUFGABEN_KOPF, ["Mathe", 2.0, "X", ""]]})
    assert daten.lade_aufgaben(pfad)["Woche"].tolist() == [2]


def test_ungueltiger_tag_im_stundenplan(tmp_path):
    pfad = excel_anlegen(tmp_path / "s.xlsx", {"Stundenplan": [
        PLAN_KOPF, ["Mathe", "VL", "Montag", time(8, 0), time(10, 0), None],
    ]})
    with pytest.raises(daten.TabellenFehler, match="Zeile 2 \\(Mathe\\), steht beim Tag „Montag“"):
        daten.lade_stundenplan(pfad)


def test_tag_mit_leerzeichen_wird_akzeptiert(tmp_path):
    pfad = excel_anlegen(tmp_path / "s.xlsx", {"Stundenplan": [
        PLAN_KOPF, ["Mathe", "VL", "Mo ", time(8, 0), time(10, 0), None],
    ]})
    assert daten.lade_stundenplan(pfad)["Tag"].tolist() == ["Mo"]


def test_ungueltige_uhrzeit_im_stundenplan(tmp_path):
    pfad = excel_anlegen(tmp_path / "s.xlsx", {"Stundenplan": [
        PLAN_KOPF, ["Mathe", "VL", "Mo", "8 Uhr", time(10, 0), None],
    ]})
    with pytest.raises(daten.TabellenFehler, match="bei „Von“ keine Uhrzeit eingetragen: „8 Uhr“"):
        daten.lade_stundenplan(pfad)


def test_tabellenfehler_ist_auch_ein_valueerror():
    assert issubclass(daten.TabellenFehler, ValueError)
    assert issubclass(daten.TabellenFehler, daten.ExcelFehler)


# ---------------------------------------------------------------- Fehlerarten beim Laden

def test_lade_alles_liefert_alle_blaetter():
    tabellen = daten.lade_alles(BEISPIEL)
    assert len(tabellen.aufgaben) and len(tabellen.faecher) and len(tabellen.stundenplan)


def test_fehlende_datei(tmp_path):
    with pytest.raises(daten.DateiFehlt, match="weg.xlsx wurde nicht gefunden"):
        daten.lade_alles(tmp_path / "weg.xlsx")


def test_halb_geschriebene_datei_gilt_als_voruebergehend(tmp_path):
    # Während Excel speichert, ist die .xlsx kurz kein gültiges ZIP-Archiv
    pfad = tmp_path / "halb.xlsx"
    pfad.write_bytes(b"PK\x03\x04 abgebrochen")
    with pytest.raises(daten.DateiGesperrt, match="wird gerade geschrieben"):
        daten.lade_alles(pfad)


def test_gesperrte_datei_gilt_als_voruebergehend(monkeypatch):
    def gesperrt(*args, **kwargs):
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(daten.pd, "read_excel", gesperrt)
    with pytest.raises(daten.DateiGesperrt, match="Automatisches Speichern"):
        daten.lade_alles(BEISPIEL)


# ---------------------------------------------------------------- Excel finden

def test_excel_pfad_txt_hat_vorrang(tmp_path):
    eigene = excel_anlegen(tmp_path / "Meine.xlsx", {"x": [[1]]})
    (tmp_path / "uni.xlsx").write_bytes(b"")
    (tmp_path / "excel_pfad.txt").write_text(f'"{eigene}"\n', encoding="utf-8-sig")
    assert daten.excel_finden(tmp_path) == (eigene, None)


def test_umgebungsvariable_hat_vorrang(tmp_path, monkeypatch):
    eigene = tmp_path / "meine.xlsx"
    eigene.touch()
    monkeypatch.setenv("UNI_EXCEL", str(eigene))
    assert daten.excel_finden(tmp_path) == (eigene, None)


def test_falsche_umgebungsvariable_wird_gemeldet(tmp_path, monkeypatch):
    monkeypatch.setenv("UNI_EXCEL", str(tmp_path / "gibtsnicht.xlsx"))
    pfad, hinweis = daten.excel_finden(tmp_path)
    assert pfad == tmp_path / "beispiel.xlsx"
    assert hinweis.startswith("UNI_EXCEL zeigt auf")
    assert hinweis.endswith("Angezeigt wird stattdessen beispiel.xlsx.")


def test_falscher_pfad_wird_gemeldet_statt_still_ersetzt(tmp_path):
    (tmp_path / "excel_pfad.txt").write_text(str(tmp_path / "gibtsnicht.xlsx"), encoding="utf-8")
    pfad, hinweis = daten.excel_finden(tmp_path)
    assert pfad == tmp_path / "beispiel.xlsx"
    assert "gibtsnicht.xlsx" in hinweis and "diese Datei gibt es nicht" in hinweis
    assert hinweis.endswith("Angezeigt wird stattdessen beispiel.xlsx.")


def test_leere_excel_pfad_txt(tmp_path):
    (tmp_path / "excel_pfad.txt").write_text("\n", encoding="utf-8")
    (tmp_path / "uni.xlsx").write_bytes(b"")
    pfad, hinweis = daten.excel_finden(tmp_path)
    assert pfad == tmp_path / "uni.xlsx"
    assert hinweis.startswith("excel_pfad.txt ist leer.")


def test_ohne_excel_pfad_txt_gibt_es_keinen_hinweis(tmp_path):
    assert daten.excel_finden(tmp_path) == (tmp_path / "beispiel.xlsx", None)


# ---------------------------------------------------------------- Fristen-Kachel

def test_fristen_kachel_zeigt_nur_die_naechsten_drei_tage():
    from uni_dashboard import grafiken
    aufgaben = pd.DataFrame({
        "Modul": ["A", "B", "C", "D"], "Woche": [1, 1, 1, 1], "Erledigt": [False, False, False, True],
        "Notiz": ["vorbei", "heute", "in drei Tagen", "erledigt"],
        "Frist": pd.to_datetime(["2026-11-06 08:00", "2026-11-06 23:59", "2026-11-09 23:59",
                                 "2026-11-06 23:59"]),
    })
    kachel = grafiken.fristen_kachel(aufgaben, datetime(2026, 11, 6, 9, 0))
    assert "B: heute" in kachel
    assert "vorbei" not in kachel and "in drei Tagen" not in kachel and "erledigt" not in kachel
    assert "@keyframes" not in kachel   # eine Aufgabe: nichts zum Wechseln


def test_fristen_kachel_wechselt_bei_mehreren():
    from uni_dashboard import grafiken
    aufgaben = pd.DataFrame({
        "Modul": ["A", "B"], "Woche": [1, 1], "Erledigt": [False, False], "Notiz": ["x", "<b>y</b>"],
        "Frist": pd.to_datetime(["2026-11-07 23:59", "2026-11-08 12:00"]),
    })
    kachel = grafiken.fristen_kachel(aufgaben, datetime(2026, 11, 6, 9, 0))
    assert "@keyframes karussell-2" in kachel
    assert ">übermorgen<" in kachel and "bis 12:00 · B:" in kachel
    assert "&lt;b&gt;" in kachel   # Text aus der Excel wird maskiert
