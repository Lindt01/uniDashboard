"""Uni-Dashboard: Stundenplan, Prüfungen und Aufgaben aus uni.xlsx.

Streamlit führt diese Datei bei jeder Interaktion von oben nach unten
neu aus. Oben stehen die Funktionen für Grafiken und HTML-Bausteine,
darunter der Seitenaufbau in der Reihenfolge, in der er erscheint:
Kennzahlen, Fächer/Stundenplan/Prüfungen, Aufgaben, Fortschritt.

Start:
    streamlit run app.py
"""

import math
import zipfile
from collections.abc import Callable
from datetime import date, datetime
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import daten

ORDNER = Path(__file__).parent
EXCEL = ORDNER / "uni.xlsx"
if not EXCEL.exists():
    EXCEL = ORDNER / "beispiel.xlsx"

# Apple-Systemfarben. Jedes Fach behält seine Farbe überall (Stundenplan,
# Fächerliste, Ringe), vergeben in der Reihenfolge des Blatts 'Fächer'.
FARBEN = ["#007aff", "#ff9500", "#34c759", "#af52de", "#ff2d55", "#30b0c7", "#5856d6", "#ffcc00"]
# Grundton des Glas-Hintergrunds; eine Zeile ändern, um die ganze Stimmung zu wechseln
GRUNDTON = "#007aff"
FARBE_ERLEDIGT = "#007aff"
FARBE_OFFEN = "#ffffff"
TEXT = "#1d1d1f"
TEXT_LEISE = "#6e6e73"
LINIE = "#f2f2f7"
SCHRIFT = "Inter, -apple-system, 'Segoe UI', sans-serif"
TAGNAMEN = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
OHNE_LEISTE = {"displayModeBar": False}


# ---------------------------------------------------------------- Grafiken

def stundenplan_grafik(stundenplan: pd.DataFrame, farbe_von: Callable[[str], str],
                       heute: date) -> go.Figure:
    """Zeichnet den Stundenplan als Wochenraster Mo–Fr, 8–20 Uhr.

    Jeder Termin ist ein abgerundeter Glasblock in der Fachfarbe.
    Überschneiden sich Termine, stehen sie nebeneinander und lange
    Namen werden gekürzt, damit nichts überlappt. Der heutige Tag
    ist leicht hinterlegt.

    Args:
        stundenplan: Ergebnis von :func:`daten.lade_stundenplan`.
        farbe_von: Liefert zu einem Fachnamen die Farbe als Hex-Wert.
        heute: Aktuelles Datum, für die Hervorhebung des Tages.

    Returns:
        Fertige Plotly-Figur ohne Werkzeugleiste und Zoom.
    """
    fig = go.Figure()
    termine = daten.lanes_bestimmen(stundenplan)

    if heute.weekday() < 5:
        fig.add_vrect(x0=heute.weekday() - 0.5, x1=heute.weekday() + 0.5,
                      fillcolor=FARBE_ERLEDIGT, opacity=0.05, line_width=0)

    for _, t in termine.iterrows():
        tag = daten.WOCHENTAGE.index(t["Tag"])
        breite = 0.94 / t["Spuren"]
        x0 = tag - 0.47 + t["Spur"] * breite
        x1 = x0 + breite - 0.025
        y0, y1 = t["Von"] + 0.05, t["Bis"] - 0.05
        farbe = farbe_von(t["Fach"])

        # Glas: getönte Fläche, heller Rand, Glanz in der oberen Hälfte
        fig.add_shape(type="path", path=_abgerundet(x0, x1, y0, y1),
                      fillcolor=_rgba(farbe, 0.22), line=dict(color=_rgba(farbe, 0.45), width=1))
        fig.add_shape(type="path", path=_abgerundet(x0 + 0.006, x1 - 0.006, y0 + 0.03, y0 + (y1 - y0) * 0.45),
                      fillcolor="rgba(255,255,255,0.35)", line_width=0)

        # Kürzen nach verfügbarer Breite: parallele Termine haben nur
        # einen Bruchteil der Tagesspalte zur Verfügung.
        name = escape(t["Fach"])
        if t["Spuren"] > 1 and " " in name:
            name = "".join(wort[0] for wort in name.split())
        elif t["Spuren"] > 1 and len(name) > 6:
            name = name[:5] + "."
        elif len(name) > 14 and " " in name:
            name = name.replace(" ", "<br>", 1)
        unterzeile = escape(t["Art"])
        if t["Raum"] and t["Spuren"] == 1:
            unterzeile += f" · {escape(t['Raum'])}"
        fig.add_annotation(
            x=x0 + 0.04, y=y0 + 0.1, xanchor="left", yanchor="top", align="left", showarrow=False,
            text=f"<b>{name}</b><br><span style='color:{TEXT_LEISE}'>{unterzeile}</span>",
            font=dict(size=11, color=TEXT))

        # Formen in Plotly zeigen keinen Tooltip. Ein unsichtbarer Punkt
        # in der Mitte des Blocks übernimmt das.
        uhrzeit = f"{_uhr(t['Von'])}–{_uhr(t['Bis'])}"
        fig.add_trace(go.Scatter(
            x=[(x0 + x1) / 2], y=[(y0 + y1) / 2], mode="markers", marker=dict(size=40, opacity=0),
            hovertemplate=f"{t['Fach']} ({t['Art']})<br>{t['Tag']} {uhrzeit}"
                          f"<br>Raum: {t['Raum'] or '–'}<extra></extra>",
        ))

    fig.update_layout(
        height=440, margin=dict(l=0, r=0, t=4, b=0), showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=SCHRIFT, color=TEXT_LEISE),
        hoverlabel=dict(bgcolor="white", bordercolor=LINIE, font=dict(family=SCHRIFT, color=TEXT)),
        xaxis=dict(range=[-0.5, 4.5], tickvals=list(range(5)), ticktext=daten.WOCHENTAGE,
                   side="top", showgrid=False, zeroline=False, fixedrange=True),
        # Achse umgedreht, damit der Morgen oben steht wie im Kalender
        yaxis=dict(range=[20.3, 7.7], tickvals=list(range(8, 21, 2)),
                   ticktext=[f"{h:02d}:00" for h in range(8, 21, 2)],
                   gridcolor=LINIE, zeroline=False, fixedrange=True),
    )
    return fig


def _abgerundet(x0: float, x1: float, y0: float, y1: float,
                rx: float = 0.035, ry: float = 0.18) -> str:
    """Erzeugt den SVG-Pfad eines Rechtecks mit runden Ecken.

    Plotly kennt keine abgerundeten Rechtecke, deshalb wird die Form
    als Pfad mit quadratischen Bézierkurven an den Ecken gezeichnet.
    Die Radien sind in Achseneinheiten angegeben und werden getrennt
    für x und y gesetzt, weil beide Achsen unterschiedlich skaliert sind.

    Args:
        x0: Linke Kante.
        x1: Rechte Kante.
        y0: Obere Kante (Startzeit).
        y1: Untere Kante (Endzeit).
        rx: Eckenradius in x-Richtung (Anteil eines Tages).
        ry: Eckenradius in y-Richtung (Stunden).

    Returns:
        SVG-Pfad für ``fig.add_shape(type="path", path=...)``.
    """
    rx = min(rx, (x1 - x0) / 2)
    ry = min(ry, (y1 - y0) / 2)
    return (f"M {x0 + rx},{y0} L {x1 - rx},{y0} Q {x1},{y0} {x1},{y0 + ry} "
            f"L {x1},{y1 - ry} Q {x1},{y1} {x1 - rx},{y1} L {x0 + rx},{y1} "
            f"Q {x0},{y1} {x0},{y1 - ry} L {x0},{y0 + ry} Q {x0},{y0} {x0 + rx},{y0} Z")


def wochen_grafik(tabelle: pd.DataFrame) -> go.Figure:
    """Zeichnet je Vorlesungswoche eine Säule aus erledigt und offen.

    Args:
        tabelle: Aufgaben im gewählten Zeitraum, Ergebnis von
            :func:`daten.lade_aufgaben` nach Anwendung der Filter.

    Returns:
        Plotly-Figur mit gestapelten Säulen.
    """
    zaehlung = (tabelle.groupby("Woche")["Erledigt"]
                .agg(erledigt="sum", gesamt="count").reset_index())
    zaehlung["offen"] = zaehlung["gesamt"] - zaehlung["erledigt"]
    wochen = "Woche " + zaehlung["Woche"].astype(str)

    fig = go.Figure()
    glas = [("erledigt", _rgba(FARBE_ERLEDIGT, 0.6), _rgba(FARBE_ERLEDIGT, 0.9), "Erledigt"),
            ("offen", _rgba(FARBE_OFFEN, 0.55), "rgba(0,0,0,0.08)", "Offen")]
    for spalte, fuellung, rand, name in glas:
        fig.add_trace(go.Bar(
            name=name, x=wochen, y=zaehlung[spalte],
            marker=dict(color=fuellung, line=dict(color=rand, width=1.5)),
            hovertemplate="%{x}: %{y} " + name.lower() + "<extra></extra>",
        ))
    fig.update_layout(
        barmode="stack", barcornerradius=6, bargap=0.45, height=300,
        margin=dict(l=0, r=0, t=30, b=0),
        font=dict(family=SCHRIFT, size=12, color=TEXT_LEISE),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.14, x=0, traceorder="normal"),
        hoverlabel=dict(bgcolor="white", bordercolor=LINIE, font=dict(family=SCHRIFT, color=TEXT)),
    )
    raster = dict(gridcolor=LINIE, zeroline=False, fixedrange=True, rangemode="tozero")
    # Bei wenigen Aufgaben ganze Zahlen erzwingen, sonst zeigt Plotly 0.5er-Schritte
    if zaehlung["gesamt"].max() <= 10:
        raster["dtick"] = 1
    fig.update_yaxes(**raster)
    fig.update_xaxes(fixedrange=True)
    return fig


def ringe_html(tabelle: pd.DataFrame, farbe_von: Callable[[str], str]) -> str:
    """Baut für jedes Fach einen Fortschrittsring als SVG.

    In der Mitte steht ``erledigt/gesamt``, beim Darüberfahren mit der
    Maus erscheinen die offenen Aufgaben. Fächer mit offenen Aufgaben
    stehen vorne (die meisten zuerst), fertige Fächer am Ende.

    Args:
        tabelle: Aufgaben im gewählten Zeitraum.
        farbe_von: Liefert zu einem Fachnamen die Farbe als Hex-Wert.

    Returns:
        HTML-Baustein für :func:`html`.
    """
    zaehlung = (tabelle.groupby("Modul")["Erledigt"]
                .agg(erledigt="sum", gesamt="count").reset_index())
    zaehlung["offen"] = zaehlung["gesamt"] - zaehlung["erledigt"]
    # Zwei Schritte: erst nach Menge sortieren, dann fertige Fächer stabil
    # nach hinten schieben, ohne die Reihenfolge davor zu verlieren.
    zaehlung = zaehlung.sort_values(["offen", "gesamt"], ascending=False)
    zaehlung = zaehlung.sort_values("offen", key=lambda s: s == 0, kind="stable")

    radius, staerke = 32, 9
    umfang = 2 * math.pi * radius
    kacheln = []
    for _, z in zaehlung.iterrows():
        farbe = farbe_von(z["Modul"])
        anteil = z["erledigt"] / z["gesamt"]
        offene = tabelle[(tabelle["Modul"] == z["Modul"]) & ~tabelle["Erledigt"]]["Notiz"]
        hinweis = "Offen:\n" + "\n".join(f"– {n[:60]}" for n in offene) if len(offene) else "Alles erledigt"
        bogen = ""
        # Der Bogen ist ein Kreis mit gestrichelter Linie: Strichlänge =
        # erledigter Anteil des Umfangs, Start oben durch Drehung um -90°.
        if anteil > 0:
            bogen = (f"<circle cx='42' cy='42' r='{radius}' fill='none' stroke='{farbe}' "
                     f"stroke-width='{staerke}' stroke-linecap='round' "
                     f"stroke-dasharray='{umfang * anteil:.1f} {umfang:.1f}' transform='rotate(-90 42 42)' "
                     f"class='bogen'/>")
        kacheln.append(
            f"<div class='ring' style='--fach:{farbe}'><svg width='84' height='84' viewBox='0 0 84 84' role='img'>"
            f"<title>{escape(hinweis)}</title>"
            f"<circle cx='42' cy='42' r='{radius}' fill='none' stroke='{farbe}' "
            f"stroke-opacity='0.16' stroke-width='{staerke}'/>{bogen}"
            f"<text x='42' y='47' text-anchor='middle' font-size='15' font-weight='600' "
            f"fill='{TEXT}'>{z['erledigt']}/{z['gesamt']}</text></svg>"
            f"<div class='name'>{escape(z['Modul'])}</div>"
            f"<div class='anteil'>{anteil * 100:.0f} %</div></div>")
    return "<div class='ringe'>" + "".join(kacheln) + "</div>"


# ---------------------------------------------------------------- Hilfen

def _rgba(farbe: str, deckkraft: float) -> str:
    """Wandelt eine Hex-Farbe in eine CSS-Farbe mit Transparenz um.

    Args:
        farbe: Farbe im Format ``#rrggbb``.
        deckkraft: Deckkraft von 0 (durchsichtig) bis 1 (deckend).

    Returns:
        CSS-Farbwert ``rgba(r,g,b,a)``.

    Example:
        >>> _rgba("#007aff", 0.5)
        'rgba(0,122,255,0.5)'
    """
    r, g, b = (int(farbe[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{deckkraft})"


def _uhr(stunden: float) -> str:
    """Formatiert Dezimalstunden als Uhrzeit.

    Args:
        stunden: Uhrzeit in Stunden, z. B. 8.5.

    Returns:
        Uhrzeit im Format ``HH:MM``.

    Example:
        >>> _uhr(8.5)
        '08:30'
    """
    return f"{int(stunden):02d}:{round(stunden % 1 * 60):02d}"


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


@st.fragment(run_every="3s")
def auf_aenderung_pruefen(stand: float, tag: date) -> None:
    """Lädt die Seite neu, sobald die Excel gespeichert wurde oder ein neuer Tag beginnt.

    Als Fragment läuft die Funktion alle 3 Sekunden für sich allein,
    ohne die ganze Seite neu aufzubauen. Erst bei einer Änderung wird
    die komplette Seite neu ausgeführt.

    Args:
        stand: Änderungszeit der Excel beim letzten Seitenaufbau.
        tag: Datum beim letzten Seitenaufbau.
    """
    if EXCEL.stat().st_mtime != stand or date.today() != tag:
        st.rerun(scope="app")


# ---------------------------------------------------------------- Daten

st.set_page_config(page_title="Uni WiSe 2026/27", layout="wide")
html(f"<style>:root {{ --grundton: {GRUNDTON}; }}\n"
     f"{(ORDNER / 'stil.css').read_text(encoding='utf-8')}</style>")

heute = date.today()
auf_aenderung_pruefen(EXCEL.stat().st_mtime, heute)

try:
    aufgaben = daten.lade_aufgaben(EXCEL)
    faecher = daten.lade_faecher(EXCEL)
    stundenplan = daten.lade_stundenplan(EXCEL)
except (OSError, ValueError, KeyError, zipfile.BadZipFile) as fehler:
    # z. B. während Excel gerade speichert
    st.info(f"{EXCEL.name} konnte gerade nicht gelesen werden ({fehler}). Neuer Versuch in wenigen Sekunden.")
    st.stop()
woche_jetzt = daten.aktuelle_woche(heute)

alle_module = list(dict.fromkeys(list(faecher["Fach"]) + list(aufgaben["Modul"])))
farbe_je_fach = {fach: FARBEN[i % len(FARBEN)] for i, fach in enumerate(alle_module)}

pruefungen = faecher.dropna(subset=["Prüfungstermin"]).sort_values("Prüfungstermin")
kommende = pruefungen[pruefungen["Prüfungstermin"].dt.date >= heute]

# ---------------------------------------------------------------- Kopf und Kennzahlen

html("<h1 class='titel'>Wintersemester 2026/27</h1>"
     f"<div class='untertitel'>{TAGNAMEN[heute.weekday()]}, {heute:%d.%m.%Y} · "
     f"Vorlesungswoche {woche_jetzt}</div>")

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
    ("Heute", "frei" if not len(heute_faecher) else f"{len(heute_faecher)} Fächer",
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
        details = [escape(f"{t['Art']} {t['Tag']} {_uhr(t['Von'])}" + (f" · {t['Raum']}" if t["Raum"] else ""))
                   for _, t in termine.iterrows()]
        zeilen.append(
            f"<div class='fach' style='--fach:{farbe_je_fach[fach['Fach']]}'><div class='punkt'></div>"
            f"<div><div class='name'>{escape(fach['Fach'])}</div>"
            f"<div class='leise'>{'<br>'.join(details) or 'keine festen Termine'}</div></div></div>")
    html("<div class='kartentitel'>Fächer</div>" + "".join(zeilen))

with mitte.container(key="karte_stundenplan"):
    html("<div class='kartentitel'>Stundenplan</div>")
    st.plotly_chart(stundenplan_grafik(stundenplan, farbe_je_fach.get, heute),
                    use_container_width=True, config=OHNE_LEISTE)

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

    hoechste_woche = max(int(aufgaben["Woche"].max()), woche_jetzt, 2)
    f1, f2, f3 = st.columns([2, 2, 1.3], gap="medium")
    von, bis = f1.select_slider("Zeitraum", options=list(range(1, hoechste_woche + 1)),
                                value=(1, hoechste_woche), format_func=lambda w: f"Woche {w}")
    module = f2.multiselect("Module", sorted(aufgaben["Modul"].unique()), placeholder="Alle Module")
    status = f3.segmented_control("Status", ["Alle", "Offen", "Erledigt"], default="Alle") or "Alle"

    auswahl = aufgaben[aufgaben["Woche"].between(von, bis)]
    if module:
        auswahl = auswahl[auswahl["Modul"].isin(module)]

    liste = auswahl
    if status == "Offen":
        liste = liste[~liste["Erledigt"]]
    elif status == "Erledigt":
        liste = liste[liste["Erledigt"]]

    anzeige = liste.assign(Status=liste["Erledigt"].map({True: "Erledigt", False: "Offen"}))
    anzeige = anzeige.sort_values(["Erledigt", "Woche", "Modul"])[["Modul", "Woche", "Status", "Notiz"]]
    st.dataframe(
        anzeige, hide_index=True, use_container_width=True,
        height=min(38 + 35 * len(anzeige), 420),
        column_config={
            "Modul": st.column_config.TextColumn(width="small"),
            "Woche": st.column_config.NumberColumn(width="small"),
            "Status": st.column_config.TextColumn(width="small"),
            "Notiz": st.column_config.TextColumn(width="large"),
        },
    )

# ---------------------------------------------------------------- Fortschritt

with st.container(key="karte_fortschritt"):
    erledigt = int(auswahl["Erledigt"].sum())
    zeitraum = f"Woche {von}" if von == bis else f"Woche {von}–{bis}"
    html(f"<div class='kartentitel'>Fortschritt {zeitraum}</div>")
    if len(auswahl):
        html(f"<div class='leise' style='margin:-6px 0 14px'>{erledigt} von {len(auswahl)} Aufgaben "
             f"erledigt ({erledigt / len(auswahl) * 100:.0f} %)</div>")
        g1, g2 = st.columns([1.3, 1], gap="large")
        with g1:
            html(ringe_html(auswahl, farbe_je_fach.get))
        g2.plotly_chart(wochen_grafik(auswahl), use_container_width=True, config=OHNE_LEISTE)
    else:
        html("<div class='leise'>Für diesen Zeitraum sind keine Aufgaben eingetragen.</div>")
