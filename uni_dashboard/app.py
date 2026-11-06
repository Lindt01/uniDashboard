"""Uni-Dashboard: Stundenplan, Prüfungen und Aufgaben aus uni.xlsx.

Streamlit führt diese Datei bei jeder Interaktion von oben nach unten
neu aus. Die Diagramme stehen in ``grafiken.py``, hier oben nur kleine
Hilfen, darunter der Seitenaufbau in der Reihenfolge, in der er erscheint:
Kennzahlen, Fächer/Stundenplan/Prüfungen, Aufgaben, Fortschritt.

Start (im Projektordner):
    streamlit run uni_dashboard/app.py
"""

import time
from datetime import date, datetime
from html import escape
from pathlib import Path

import streamlit as st

from uni_dashboard import daten, grafiken, themen

PAKET = Path(__file__).resolve().parent
# Eigene Daten liegen im Projektordner, nicht im Paket
PROJEKT = PAKET.parent
EXCEL, PFAD_HINWEIS = daten.excel_finden(PROJEKT)
# Sekunden bis zum nächsten Leseversuch, wenn die Excel gesperrt war.
# (Kein Docstring: Freistehende Texte zeigt Streamlit auf der Seite an.)
NEUER_VERSUCH_NACH = 3.0

# Apple-Systemfarben. Jedes Fach behält seine Farbe überall (Stundenplan,
# Fächerliste, Ringe), vergeben in der Reihenfolge des Blatts 'Fächer'.
FARBEN = ["#007aff", "#ff9500", "#34c759", "#af52de", "#ff2d55", "#30b0c7", "#5856d6", "#ffcc00"]
TAGNAMEN = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
OHNE_LEISTE = {"displayModeBar": False}


# ---------------------------------------------------------------- Hilfen


def _tage_bis(termin: datetime, heute: date) -> str:
    """Beschreibt den Abstand zu einem Termin in Worten.

    Args:
        termin: Zeitpunkt des Termins.
        heute: Bezugsdatum.

    Returns:
        ``"heute"``, ``"morgen"``, ``"in N Tagen"`` oder ``"vorbei"``.

    Example:
        >>> _tage_bis(datetime(2027, 2, 11, 9), date(2027, 2, 1))
        'in 10 Tagen'
    """
    tage = (termin.date() - heute).days
    if tage == 0:
        return "heute"
    if tage == 1:
        return "morgen"
    return f"in {tage} Tagen" if tage > 0 else "vorbei"


def html(text: str) -> None:
    """Gibt einen HTML-Baustein auf der Seite aus.

    Inhalte aus der Excel müssen vorher mit ``escape`` maskiert werden,
    da der Text ungefiltert als HTML eingefügt wird.

    Args:
        text: HTML-Quelltext.
    """
    st.markdown(text, unsafe_allow_html=True)


def wochen_text(wochen: list[int]) -> str:
    """Beschreibt eine Auswahl von Wochen kurz für die Überschrift.

    Args:
        wochen: Aufsteigend sortierte Wochennummern, mindestens eine.

    Returns:
        Zusammenhängende Wochen als Bereich, sonst als Aufzählung.

    Example:
        >>> wochen_text([1, 2, 3])
        'Woche 1–3'
        >>> wochen_text([1, 3])
        'Woche 1, 3'
    """
    if len(wochen) == 1:
        return f"Woche {wochen[0]}"
    if wochen == list(range(wochen[0], wochen[-1] + 1)):
        return f"Woche {wochen[0]}–{wochen[-1]}"
    return "Woche " + ", ".join(map(str, wochen))


def wahl_behalten(schluessel: str) -> None:
    """Verhindert, dass ein Umschalter durch erneutes Klicken leer wird.

    ``st.segmented_control`` wählt den aktiven Knopf ab, wenn man ihn
    noch einmal anklickt. Als ``on_change`` eingetragen, setzt diese
    Funktion dann die vorherige Wahl wieder ein.

    Args:
        schluessel: ``key`` des Umschalters in ``st.session_state``.
    """
    merker = f"{schluessel}_vorher"
    if st.session_state[schluessel] is None:
        st.session_state[schluessel] = st.session_state[merker]
    st.session_state[merker] = st.session_state[schluessel]


def aenderungszeit(pfad: Path) -> float:
    """Liefert die Änderungszeit einer Datei, 0 wenn es sie (gerade) nicht gibt.

    Args:
        pfad: Zu prüfende Datei.

    Returns:
        Zeitstempel der letzten Änderung in Sekunden.
    """
    try:
        return pfad.stat().st_mtime
    except OSError:
        return 0.0


@st.fragment(run_every="3s")
def auf_aenderung_pruefen(stand: float, tag: date, erneut_versuchen: bool) -> None:
    """Lädt die Seite neu, wenn sich etwas geändert hat oder ein neuer Versuch fällig ist.

    Als Fragment läuft die Funktion alle 3 Sekunden für sich allein,
    ohne die ganze Seite neu aufzubauen. Die komplette Seite wird neu
    ausgeführt, wenn die Excel gespeichert wurde, ein neuer Tag beginnt
    oder die Datei beim letzten Mal nur vorübergehend gesperrt war.

    Args:
        stand: Änderungszeit der Excel beim letzten Seitenaufbau.
        tag: Datum beim letzten Seitenaufbau.
        erneut_versuchen: True, wenn das letzte Laden an einer Sperre
            gescheitert ist (:class:`daten.DateiGesperrt`).
    """
    # Streamlit führt ein Fragment beim Seitenaufbau sofort einmal mit aus.
    # Ohne diese Wartezeit würde ein gesperrtes Laden die Seite in einer
    # Endlosschleife neu starten, bevor der Hinweis überhaupt erscheint.
    faellig = time.monotonic() - st.session_state.get("letzter_lauf", 0.0) >= NEUER_VERSUCH_NACH
    if (erneut_versuchen and faellig) or aenderungszeit(EXCEL) != stand or date.today() != tag:
        st.rerun(scope="app")


# ---------------------------------------------------------------- Daten

st.set_page_config(page_title="Uni WiSe 2026/27", layout="wide")

# Startwerte der Umschalter, einmal pro Sitzung: Ansicht nach Uhrzeit,
# Aufgaben gefiltert auf offene. Danach gilt, was angeklickt wurde.
for schluessel, start in [("ansicht", themen.nach_uhrzeit(datetime.now()).name), ("status", "Offen")]:
    st.session_state.setdefault(schluessel, start)
    st.session_state.setdefault(f"{schluessel}_vorher", start)

# Das Thema muss vor dem Umschalter feststehen, damit schon die ganze
# Seite in den richtigen Farben gezeichnet wird.
thema = themen.THEMEN[st.session_state["ansicht"]]
# Beim ersten Seitenaufbau der Sitzung bauen sich die Flächen nacheinander
# auf (aufbau.css). Bei jedem weiteren Durchlauf bleibt die Animation weg.
# Alles steht in einem einzigen <style>-Element, damit Streamlit beim
# nächsten Durchlauf nur dessen Inhalt tauscht und nichts neu zeichnet.
stile = [thema.css(), (PAKET / "stil.css").read_text(encoding="utf-8")]
if not st.session_state.get("aufgebaut"):
    stile.append((PAKET / "aufbau.css").read_text(encoding="utf-8"))
    st.session_state["aufgebaut"] = True
html("<style>" + "\n".join(stile) + "</style>")
heute = date.today()
woche_jetzt = daten.aktuelle_woche(heute)

# Laden. Gelingt es, wird der Stand für später gemerkt. Scheitert es, zeigt
# das Dashboard den letzten guten Stand mit einem Hinweis, statt leer zu werden.
stand = aenderungszeit(EXCEL)
st.session_state["letzter_lauf"] = time.monotonic()
try:
    tabellen = daten.lade_alles(EXCEL)
    st.session_state["letzter_stand"] = (tabellen, datetime.now())
    fehler = None
except daten.ExcelFehler as ausnahme:
    fehler = ausnahme
# Eine Sperre geht von selbst vorbei: dann alle 3 s neu versuchen. Bei einem
# Fehler in der Tabelle erst wieder, wenn sie gespeichert wurde.
auf_aenderung_pruefen(stand, heute, erneut_versuchen=isinstance(fehler, daten.DateiGesperrt))

# ---------------------------------------------------------------- Kopf und Kennzahlen

kopf, schalter = st.columns([3, 1], vertical_alignment="center")
with schalter:
    st.segmented_control(
        "Ansicht", list(themen.THEMEN), key="ansicht", label_visibility="collapsed",
        on_change=wahl_behalten, args=("ansicht",),
        format_func=lambda n: {"Tag": ":material/light_mode: Tag", "Nacht": ":material/dark_mode: Nacht"}[n],
    )
with kopf:
    html("<h1 class='titel'>Wintersemester 2026/27</h1>"
         f"<div class='untertitel'>{TAGNAMEN[heute.weekday()]}, {heute:%d.%m.%Y} · "
         f"Vorlesungswoche {woche_jetzt}</div>")

# ---------------------------------------------------------------- Hinweise

if PFAD_HINWEIS:
    st.warning(PFAD_HINWEIS, icon=":material/folder_off:")
if fehler:
    gesperrt = isinstance(fehler, daten.DateiGesperrt)
    weiter = ("Neuer Versuch läuft automatisch." if gesperrt
              else "Nach dem Korrigieren und Speichern lädt das Dashboard von selbst neu.")
    letzter = st.session_state.get("letzter_stand")
    if letzter is None:
        # Noch nie erfolgreich geladen: nichts, was man zeigen könnte
        st.error(f"{fehler} {weiter}", icon=":material/error:")
        st.stop()
    tabellen, geladen_um = letzter
    st.warning(f"{fehler} {weiter} Angezeigt wird der Stand von {geladen_um:%H:%M} Uhr.",
               icon=":material/hourglass_top:" if gesperrt else ":material/edit_note:")
aufgaben, faecher, stundenplan = tabellen.aufgaben, tabellen.faecher, tabellen.stundenplan

alle_module = list(dict.fromkeys(list(faecher["Fach"]) + list(aufgaben["Modul"])))
farbe_je_fach = {fach: FARBEN[i % len(FARBEN)] for i, fach in enumerate(alle_module)}

pruefungen = faecher.dropna(subset=["Prüfungstermin"]).sort_values("Prüfungstermin")
kommende = pruefungen[pruefungen["Prüfungstermin"].dt.date >= heute]

offen_gesamt = int((~aufgaben["Erledigt"]).sum())
erledigt_gesamt = int(aufgaben["Erledigt"].sum())
quote = erledigt_gesamt / len(aufgaben) * 100 if len(aufgaben) else 0
heute_kurz = daten.WOCHENTAGE[heute.weekday()] if heute.weekday() < 5 else None
heute_faecher = stundenplan[stundenplan["Tag"] == heute_kurz]["Fach"].unique()

if len(kommende):
    naechste = kommende.iloc[0]
    pruefung_wert = _tage_bis(naechste["Prüfungstermin"], heute)
    pruefung_zusatz = f"{naechste['Fach']}, {naechste['Prüfungstermin']:%d.%m.}"
else:
    pruefung_wert, pruefung_zusatz = "–", "keine Termine"

kacheln = [
    ("Offene Aufgaben", offen_gesamt, f"von {len(aufgaben)} insgesamt"),
    ("Erledigt", f"{quote:.0f} %", f"{erledigt_gesamt} Aufgaben"),
    ("Nächste Prüfung", pruefung_wert, pruefung_zusatz),
    ("Heute", "frei" if not len(heute_faecher)
     else f"{len(heute_faecher)} {'Fach' if len(heute_faecher) == 1 else 'Fächer'}",
     ", ".join(heute_faecher) or "keine Veranstaltungen"),
]
html("<div class='kacheln'>" + "".join(
    f"<div class='kachel'><div class='etikett'>{e}</div><div class='wert'>{w}</div>"
    f"<div class='zusatz'>{escape(z)}</div></div>" for e, w, z in kacheln) + "</div>")

# ---------------------------------------------------------------- Fächer | Stundenplan | Prüfungen

links, mitte, rechts = st.columns([1, 2.8, 1], gap="small")

with links.container(key="karte_faecher"):
    zeilen = []
    for _, fach in faecher.iterrows():
        termine = stundenplan[stundenplan["Fach"] == fach["Fach"]]
        details = [escape(f"{t['Art']} {t['Tag']} {grafiken.uhr(t['Von'])}" + (f" · {t['Raum']}" if t["Raum"] else ""))
                   for _, t in termine.iterrows()]
        zeilen.append(
            f"<div class='fach' style='--fach:{farbe_je_fach[fach['Fach']]}'><div class='punkt'></div>"
            f"<div><div class='name'>{escape(fach['Fach'])}</div>"
            f"<div class='leise'>{'<br>'.join(details) or 'keine festen Termine'}</div></div></div>")
    html("<div class='kartentitel'>Fächer</div>" + "".join(zeilen))

with mitte.container(key="karte_stundenplan"):
    html("<div class='kartentitel'>Stundenplan</div>")
    st.plotly_chart(grafiken.stundenplan_grafik(stundenplan, farbe_je_fach.get, heute, thema),
                    width="stretch", config=OHNE_LEISTE)

with rechts.container(key="karte_pruefungen"):
    zeilen = []
    for _, p in pruefungen.iterrows():
        termin = p["Prüfungstermin"]
        zeilen.append(
            f"<div class='pruefung'><div class='name'>{escape(p['Fach'])}</div>"
            f"<div class='leise'>{TAGNAMEN[termin.weekday()][:2]}, {termin:%d.%m.%Y · %H:%M}</div>"
            f"<div class='countdown'>{_tage_bis(termin, heute)}</div></div>")
    offen = faecher[faecher["Prüfung"].astype(str).str.upper().str.strip() == "TBA"]["Fach"]
    if len(offen):
        zeilen.append(f"<div class='leise' style='margin-top:10px'>Termin noch offen: {escape(', '.join(offen))}</div>")
    html("<div class='kartentitel'>Prüfungen</div>" + "".join(zeilen))

# ---------------------------------------------------------------- Aufgaben

with st.container(key="karte_aufgaben"):
    html("<div class='kartentitel'>Aufgaben</div>")

    # Filter als Knöpfe zum Anklicken; nichts gewählt heißt jeweils "alle"
    alle_wochen = list(range(1, max(int(aufgaben["Woche"].max()), woche_jetzt) + 1))
    f1, f2 = st.columns([3, 1], gap="medium")
    wochen = f1.pills("Wochen", alle_wochen, selection_mode="multi", key="filter_wochen",
                      format_func=lambda w: f"Woche {w}" + (" · jetzt" if w == woche_jetzt else ""))
    status = f2.segmented_control("Status", ["Alle", "Offen", "Erledigt"], key="status",
                                  on_change=wahl_behalten, args=("status",))
    module = st.pills("Module", sorted(aufgaben["Modul"].unique()), selection_mode="multi",
                      key="filter_module")

    wochen = sorted(wochen) or alle_wochen
    auswahl = aufgaben[aufgaben["Woche"].isin(wochen)]
    if module:
        auswahl = auswahl[auswahl["Modul"].isin(module)]

    liste = auswahl
    if status == "Offen":
        liste = liste[~liste["Erledigt"]]
    elif status == "Erledigt":
        liste = liste[liste["Erledigt"]]

    anzeige = liste.sort_values(["Erledigt", "Woche", "Modul"])
    html(grafiken.aufgaben_tabelle(anzeige))

with st.container(key="karte_fortschritt"):
    erledigt = int(auswahl["Erledigt"].sum())
    zeitraum = wochen_text(wochen)
    html(f"<div class='kartentitel'>Fortschritt {zeitraum}</div>")
    if len(auswahl):
        html(f"<div class='leise' style='margin:-6px 0 14px'>{erledigt} von {len(auswahl)} Aufgaben "
             f"erledigt ({erledigt / len(auswahl) * 100:.0f} %)</div>")
        g1, g2 = st.columns([1.3, 1], gap="large")
        with g1:
            html(grafiken.ringe_html(auswahl, farbe_je_fach.get))
        g2.plotly_chart(grafiken.wochen_grafik(auswahl, thema), width="stretch", config=OHNE_LEISTE)
    else:
        html("<div class='leise'>Für diesen Zeitraum sind keine Aufgaben eingetragen.</div>")
