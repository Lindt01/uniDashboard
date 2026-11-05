"""Einlesen und Aufbereiten der Daten aus der Excel-Datei.

Die Excel-Datei hat drei Blätter:

* ``Fächer``: Übersicht mit Vorlesung, Übung und Prüfungstermin je Fach.
* ``Stundenplan``: ein Termin pro Zeile (Fach, Art, Tag, Von, Bis, Raum).
* ``Aufgabenliste``: eine Aufgabe pro Zeile (Modul, Woche, Status, Notiz).

Alle Funktionen geben pandas-DataFrames mit bereinigten Werten zurück,
damit die Oberfläche in ``app.py`` nicht mit Rohdaten arbeiten muss.
"""

import re
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd

SEMESTERBEGINN = date(2026, 10, 19)
"""Montag der ersten Vorlesungswoche im Wintersemester 2026/27."""

WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr"]
"""Kürzel der Vorlesungstage in der Reihenfolge des Stundenplans."""


def lade_aufgaben(pfad: Path) -> pd.DataFrame:
    """Liest das Blatt ``Aufgabenliste``.

    Leere Zeilen werden übersprungen, Leerzeichen am Rand entfernt.
    Aus der Spalte ``Status`` wird ein Wahrheitswert: ``Done`` gilt
    als erledigt, alles andere (z. B. ``X``) als offen.

    Args:
        pfad: Pfad zur Excel-Datei.

    Returns:
        DataFrame mit den Spalten ``Modul`` (str), ``Woche`` (int),
        ``Erledigt`` (bool) und ``Notiz`` (str).

    Raises:
        ValueError: Wenn das Blatt fehlt oder eine Woche keine Zahl ist.
    """
    df = pd.read_excel(pfad, sheet_name="Aufgabenliste", usecols="A:D", engine="openpyxl")
    df = df.dropna(subset=["Modul"])
    df["Modul"] = df["Modul"].astype(str).str.strip()
    df["Notiz"] = _als_text(df["Notiz"])
    df["Woche"] = df["Woche"].astype(int)
    df["Erledigt"] = df["Status"].astype(str).str.strip().str.lower() == "done"
    return df[["Modul", "Woche", "Erledigt", "Notiz"]].reset_index(drop=True)


def lade_faecher(pfad: Path) -> pd.DataFrame:
    """Liest die Fächerübersicht oben links im Blatt ``Fächer``.

    Gelesen wird bis zur ersten leeren Zeile. Alles darunter
    (z. B. ein Stundenplan-Raster oder Notizen) wird ignoriert,
    damit das Blatt weiterhin frei gestaltet werden kann.

    Args:
        pfad: Pfad zur Excel-Datei.

    Returns:
        DataFrame mit den Spalten ``Fach``, ``Vorlesung``, ``Übung``,
        ``Prüfung`` (Originaltext) und ``Prüfungstermin`` (datetime
        oder None).

    Raises:
        ValueError: Wenn das Blatt fehlt.
    """
    df = pd.read_excel(pfad, sheet_name="Fächer", usecols="A:D", engine="openpyxl")
    df.columns = ["Fach", "Vorlesung", "Übung", "Prüfung"]
    ende = df["Fach"].isna().idxmax() if df["Fach"].isna().any() else len(df)
    df = df.iloc[:ende].copy()
    df["Fach"] = df["Fach"].astype(str).str.strip()
    df["Prüfungstermin"] = df["Prüfung"].apply(pruefungstermin)
    return df


def pruefungstermin(wert: str | datetime | None) -> datetime | None:
    """Wandelt einen Prüfungseintrag aus der Excel in ein Datum um.

    Akzeptiert werden Texte im Format ``TT.MM, HH:MM`` (Punkt nach dem
    Monat und Komma sind optional) sowie echte Excel-Datumswerte.

    Args:
        wert: Zelleninhalt, z. B. ``"11.02, 9:00"``, ``"TBA"`` oder
            ein Excel-Datum.

    Returns:
        Datum und Uhrzeit der Prüfung, oder None, wenn kein Termin
        feststeht (``TBA``, Backslash oder leere Zelle).

    Example:
        >>> pruefungstermin("11.02, 9:00")
        datetime.datetime(2027, 2, 11, 9, 0)
        >>> pruefungstermin("TBA") is None
        True
    """
    if isinstance(wert, datetime):
        return wert
    treffer = re.fullmatch(r"\s*(\d{1,2})\.(\d{1,2})\.?,?\s*(\d{1,2}):(\d{2})\s*", str(wert))
    if treffer is None:
        return None
    tag, monat, stunde, minute = map(int, treffer.groups())
    # Das Wintersemester geht über den Jahreswechsel: Monate vor dem
    # Semesterbeginn (Januar bis September) gehören ins Folgejahr.
    jahr = SEMESTERBEGINN.year
    if monat < SEMESTERBEGINN.month:
        jahr += 1
    return datetime(jahr, monat, tag, stunde, minute)


def lade_stundenplan(pfad: Path) -> pd.DataFrame:
    """Liest das Blatt ``Stundenplan``.

    Uhrzeiten werden in Dezimalstunden umgerechnet (08:30 wird 8.5),
    weil die Stundenplan-Grafik mit Zahlen auf der Zeitachse arbeitet.

    Args:
        pfad: Pfad zur Excel-Datei.

    Returns:
        DataFrame mit den Spalten ``Fach``, ``Art``, ``Tag``,
        ``Von`` und ``Bis`` (float) sowie ``Raum`` (str, ggf. leer).

    Raises:
        ValueError: Wenn das Blatt fehlt oder eine Uhrzeit nicht
            lesbar ist.
    """
    df = pd.read_excel(pfad, sheet_name="Stundenplan", usecols="A:F", engine="openpyxl")
    df = df.dropna(subset=["Fach"])
    df["Fach"] = df["Fach"].astype(str).str.strip()
    df["Raum"] = _als_text(df["Raum"])
    df["Von"] = df["Von"].apply(in_stunden)
    df["Bis"] = df["Bis"].apply(in_stunden)
    return df.reset_index(drop=True)


def _als_text(spalte: pd.Series) -> pd.Series:
    """Wandelt eine Spalte in bereinigten Text um, leere Zellen werden zu "".

    Ist eine Spalte in der Excel komplett leer (z. B. noch keine Räume
    eingetragen), liest pandas sie als Zahlenspalte ein. In eine solche
    Spalte darf ab pandas 3 kein Text mehr eingefüllt werden, deshalb
    wird zuerst in Text umgewandelt und erst danach aufgefüllt.

    Args:
        spalte: Spalte aus ``pd.read_excel``.

    Returns:
        Spalte vom Typ str ohne Leerzeichen am Rand.
    """
    text = spalte.astype("object")
    return text.where(spalte.notna(), "").astype(str).str.strip()


def in_stunden(wert: time | datetime | str) -> float:
    """Rechnet eine Uhrzeit in Dezimalstunden um.

    Args:
        wert: Uhrzeit als ``time``/``datetime`` (so liefert Excel
            formatierte Zellen) oder als Text ``"HH:MM"``.

    Returns:
        Stunden als Kommazahl.

    Example:
        >>> in_stunden("08:30")
        8.5
        >>> in_stunden(time(14, 15))
        14.25
    """
    if isinstance(wert, (time, datetime)):
        return wert.hour + wert.minute / 60
    stunde, minute = str(wert).split(":")[:2]
    return int(stunde) + int(minute) / 60


def aktuelle_woche(heute: date) -> int:
    """Bestimmt die Vorlesungswoche zu einem Datum.

    Args:
        heute: Das Datum, für das die Woche gesucht wird.

    Returns:
        Nummer der Vorlesungswoche, beginnend bei 1. Vor dem
        Semesterbeginn ergibt sich 0 oder weniger.

    Example:
        >>> aktuelle_woche(date(2026, 10, 19))
        1
        >>> aktuelle_woche(date(2026, 10, 31))
        2
    """
    return (heute - SEMESTERBEGINN).days // 7 + 1


def lanes_bestimmen(stundenplan: pd.DataFrame) -> pd.DataFrame:
    """Verteilt sich überschneidende Termine eines Tages auf Spuren.

    Termine, die zur selben Zeit stattfinden, sollen im Stundenplan
    nebeneinander statt übereinander stehen. Dafür bekommt jeder
    Termin die erste freie Spur seines Tages (Greedy-Verfahren wie
    bei Kalender-Apps).

    Args:
        stundenplan: Ergebnis von :func:`lade_stundenplan`.

    Returns:
        Kopie des Stundenplans mit zwei zusätzlichen Spalten:
        ``Spur`` (0, 1, ...: Position von links) und ``Spuren``
        (wie viele Termine sich den Zeitraum teilen, bestimmt die
        Breite).
    """
    df = stundenplan.sort_values(["Tag", "Von"]).copy()
    df["Spur"] = 0
    df["Spuren"] = 1
    for _, tag in df.groupby("Tag"):
        # enden[n] = Uhrzeit, ab der Spur n wieder frei ist
        enden = []
        for i, termin in tag.iterrows():
            frei = [n for n, ende in enumerate(enden) if ende <= termin["Von"]]
            if frei:
                spur = frei[0]
                enden[spur] = termin["Bis"]
            else:
                spur = len(enden)
                enden.append(termin["Bis"])
            df.loc[i, "Spur"] = spur
        for i, termin in tag.iterrows():
            parallel = tag[(tag["Von"] < termin["Bis"]) & (tag["Bis"] > termin["Von"])]
            df.loc[i, "Spuren"] = len(parallel)
    return df
