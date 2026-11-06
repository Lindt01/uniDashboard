"""Einlesen und Aufbereiten der Daten aus der Excel-Datei.

Die Excel-Datei hat drei Blätter:

* ``Fächer``: Übersicht mit Vorlesung, Übung und Prüfungstermin je Fach.
* ``Stundenplan``: ein Termin pro Zeile (Fach, Art, Tag, Von, Bis, Raum).
* ``Aufgabenliste``: eine Aufgabe pro Zeile (Modul, Woche, Status, Notiz).

Alle Funktionen geben pandas-DataFrames mit bereinigten Werten zurück,
damit die Oberfläche in ``app.py`` nicht mit Rohdaten arbeiten muss.

Passt etwas nicht, lösen die Funktionen eine :class:`ExcelFehler`-Unterart
mit einer Meldung aus, die direkt im Dashboard angezeigt werden kann:

* :class:`DateiGesperrt`: vorübergehend, ein neuer Versuch lohnt sich.
* :class:`DateiFehlt`: Die Datei gibt es nicht.
* :class:`TabellenFehler`: Blatt, Spalte oder Wert muss in der Excel
  korrigiert werden.
"""

import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd

SEMESTERBEGINN = date(2026, 10, 19)
"""Montag der ersten Vorlesungswoche im Wintersemester 2026/27."""

WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr"]
"""Kürzel der Vorlesungstage in der Reihenfolge des Stundenplans."""

SPALTEN_AUFGABEN = ["Modul", "Woche", "Status", "Notiz"]
"""Pflichtspalten im Blatt ``Aufgabenliste``; weitere (z. B. Frist) sind erlaubt."""

SPALTEN_STUNDENPLAN = ["Fach", "Art", "Tag", "Von", "Bis", "Raum"]
"""Pflichtspalten im Blatt ``Stundenplan``."""


# ---------------------------------------------------------------- Fehler

class ExcelFehler(Exception):
    """Die Excel-Datei konnte nicht (vollständig) gelesen werden.

    Die Meldung ist für Menschen geschrieben und wird so im Dashboard
    angezeigt. Die Unterklassen sagen, was zu tun ist.
    """


class DateiGesperrt(ExcelFehler):
    """Die Datei ist gerade gesperrt oder halb geschrieben.

    Passiert z. B., während Excel speichert. Das geht von selbst vorbei,
    ein neuer Versuch nach ein paar Sekunden lohnt sich.
    """


class DateiFehlt(ExcelFehler):
    """Die Datei gibt es nicht (mehr), z. B. weil sie umbenannt wurde."""


class TabellenFehler(ExcelFehler, ValueError):
    """Die Datei ist lesbar, aber ein Blatt, eine Spalte oder ein Wert passt nicht.

    Muss in der Excel korrigiert werden. Erbt auch von ``ValueError``,
    weil es fachlich ein ungültiger Wert ist.
    """


@dataclass(frozen=True)
class Tabellen:
    """Alle drei Blätter, fertig aufbereitet.

    Attributes:
        aufgaben: Ergebnis von :func:`lade_aufgaben`.
        faecher: Ergebnis von :func:`lade_faecher`.
        stundenplan: Ergebnis von :func:`lade_stundenplan`.
    """

    aufgaben: pd.DataFrame
    faecher: pd.DataFrame
    stundenplan: pd.DataFrame


# ---------------------------------------------------------------- Datei finden und laden

def excel_finden(projekt: Path) -> tuple[Path, str | None]:
    """Sucht die Excel-Datei, die angezeigt werden soll.

    Reihenfolge: der Pfad in ``excel_pfad.txt``, dann ``uni.xlsx``, dann
    ``beispiel.xlsx`` (alle im Projektordner). Zeigt ``excel_pfad.txt``
    auf eine Datei, die es nicht gibt, wird das nicht still übergangen,
    sondern als Hinweis zurückgegeben.

    Args:
        projekt: Projektordner.

    Returns:
        Pfad der Excel-Datei und ein Hinweis für das Dashboard, oder None,
        wenn alles wie eingestellt gefunden wurde.
    """
    hinweis = None
    pfad_datei = projekt / "excel_pfad.txt"
    if pfad_datei.exists():
        # utf-8-sig: Der Windows-Editor setzt manchmal unsichtbare Zeichen an den Anfang
        eintrag = pfad_datei.read_text(encoding="utf-8-sig").strip().strip('"')
        if eintrag and Path(eintrag).is_file():
            return Path(eintrag), None
        hinweis = (f"In excel_pfad.txt steht „{eintrag}“, diese Datei gibt es nicht."
                   if eintrag else "excel_pfad.txt ist leer.")
    ersatz = projekt / "uni.xlsx" if (projekt / "uni.xlsx").is_file() else projekt / "beispiel.xlsx"
    if hinweis:
        hinweis += f" Angezeigt wird stattdessen {ersatz.name}."
    return ersatz, hinweis


def lade_alles(pfad: Path) -> Tabellen:
    """Liest alle drei Blätter und ordnet Fehler einer der drei Arten zu.

    Args:
        pfad: Pfad zur Excel-Datei.

    Returns:
        Die aufbereiteten Blätter.

    Raises:
        DateiFehlt: Wenn es die Datei nicht gibt.
        DateiGesperrt: Wenn die Datei gesperrt oder halb geschrieben ist.
        TabellenFehler: Wenn ein Blatt, eine Spalte oder ein Wert nicht passt.
    """
    try:
        return Tabellen(lade_aufgaben(pfad), lade_faecher(pfad), lade_stundenplan(pfad))
    except ExcelFehler:
        raise
    except FileNotFoundError as fehler:
        raise DateiFehlt(f"{pfad.name} wurde nicht gefunden ({pfad}).") from fehler
    except PermissionError as fehler:
        raise DateiGesperrt(f"{pfad.name} ist gerade gesperrt, vermutlich speichert Excel gerade. "
                            "Tipp: In Excel „Automatisches Speichern“ ausschalten.") from fehler
    except (zipfile.BadZipFile, EOFError, OSError) as fehler:
        # Eine halb geschriebene .xlsx ist kein gültiges ZIP-Archiv
        raise DateiGesperrt(f"{pfad.name} wird gerade geschrieben und ist kurz nicht lesbar.") from fehler
    except (KeyError, ValueError) as fehler:
        raise TabellenFehler(f"{pfad.name} enthält einen unerwarteten Wert ({fehler}).") from fehler


def _blatt_lesen(pfad: Path, blatt: str, **optionen) -> pd.DataFrame:
    """Liest ein Blatt und meldet ein fehlendes Blatt verständlich.

    Args:
        pfad: Pfad zur Excel-Datei.
        blatt: Name des Blatts.
        **optionen: Weitere Argumente für ``pd.read_excel``.

    Returns:
        Das Blatt als DataFrame, Überschriften ohne Leerzeichen am Rand.

    Raises:
        TabellenFehler: Wenn es das Blatt nicht gibt.
    """
    try:
        df = pd.read_excel(pfad, sheet_name=blatt, engine="openpyxl", **optionen)
    except ValueError as fehler:
        if "not found" in str(fehler):
            raise TabellenFehler(f"In {pfad.name} fehlt das Blatt „{blatt}“.") from fehler
        raise
    df.columns = [str(name).strip() for name in df.columns]
    return df


def _spalten_pruefen(df: pd.DataFrame, blatt: str, pflicht: list[str]) -> None:
    """Prüft, ob alle Pflichtspalten als Überschrift vorhanden sind.

    Args:
        df: Eingelesenes Blatt.
        blatt: Name des Blatts, für die Meldung.
        pflicht: Überschriften, die vorkommen müssen.

    Raises:
        TabellenFehler: Mit allen fehlenden Spalten.
    """
    fehlend = [spalte for spalte in pflicht if spalte not in df.columns]
    if fehlend:
        namen = ", ".join(f"„{spalte}“" for spalte in fehlend)
        art = "die Spalte" if len(fehlend) == 1 else "die Spalten"
        raise TabellenFehler(f"Im Blatt „{blatt}“ fehlt {art} {namen}. "
                             f"In der ersten Zeile müssen stehen: {', '.join(pflicht)}.")


def _zeile(index: int) -> int:
    """Rechnet einen DataFrame-Index in die Zeilennummer in Excel um.

    Zeile 1 ist die Überschrift, die erste Datenzeile hat Index 0.

    Example:
        >>> _zeile(0)
        2
    """
    return int(index) + 2


# ---------------------------------------------------------------- Blätter


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
        TabellenFehler: Wenn das Blatt oder eine Spalte fehlt oder eine
            Woche keine ganze Zahl ist.
    """
    # Spalten über ihren Namen lesen, nicht über die Position, damit
    # zusätzliche Spalten (z. B. "Frist") an beliebiger Stelle stehen dürfen.
    df = _blatt_lesen(pfad, "Aufgabenliste")
    _spalten_pruefen(df, "Aufgabenliste", SPALTEN_AUFGABEN)
    df = df.dropna(subset=["Modul"])
    df["Modul"] = df["Modul"].astype(str).str.strip()
    df["Notiz"] = _als_text(df["Notiz"])
    woche = pd.to_numeric(df["Woche"], errors="coerce")
    ungueltig = woche.isna() | (woche % 1 != 0)
    if ungueltig.any():
        i = ungueltig.idxmax()
        wert = "leer" if pd.isna(df.loc[i, "Woche"]) else f"„{df.loc[i, 'Woche']}“"
        raise TabellenFehler(f"Im Blatt „Aufgabenliste“, Zeile {_zeile(i)} ({df.loc[i, 'Modul']}), "
                             f"ist die Woche keine ganze Zahl: {wert}.")
    df["Woche"] = woche.astype(int)
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
        TabellenFehler: Wenn das Blatt fehlt oder weniger als vier
            Spalten hat.
    """
    df = _blatt_lesen(pfad, "Fächer", usecols="A:D")
    if df.shape[1] < 4:
        raise TabellenFehler("Im Blatt „Fächer“ werden die Spalten A bis D gebraucht: "
                             "Fach, Vorlesung, Übung, Prüfung.")
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
        TabellenFehler: Wenn das Blatt oder eine Spalte fehlt, ein Tag
            nicht Mo–Fr ist oder eine Uhrzeit nicht lesbar ist.
    """
    df = _blatt_lesen(pfad, "Stundenplan")
    _spalten_pruefen(df, "Stundenplan", SPALTEN_STUNDENPLAN)
    df = df.dropna(subset=["Fach"])[SPALTEN_STUNDENPLAN].copy()
    df["Fach"] = df["Fach"].astype(str).str.strip()
    df["Tag"] = df["Tag"].astype(str).str.strip()
    df["Raum"] = _als_text(df["Raum"])
    for i, termin in df.iterrows():
        if termin["Tag"] not in WOCHENTAGE:
            raise TabellenFehler(f"Im Blatt „Stundenplan“, Zeile {_zeile(i)} ({termin['Fach']}), "
                                 f"steht beim Tag „{termin['Tag']}“. Erlaubt sind {', '.join(WOCHENTAGE)}.")
        for spalte in ("Von", "Bis"):
            try:
                df.loc[i, spalte] = in_stunden(termin[spalte])
            except (ValueError, TypeError) as fehler:
                raise TabellenFehler(
                    f"Im Blatt „Stundenplan“, Zeile {_zeile(i)} ({termin['Fach']}), ist bei „{spalte}“ "
                    f"keine Uhrzeit eingetragen: „{termin[spalte]}“. Erwartet wird z. B. 08:30.") from fehler
    df["Von"] = df["Von"].astype(float)
    df["Bis"] = df["Bis"].astype(float)
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
