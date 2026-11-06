"""Diagramme und HTML-Bausteine für das Uni-Dashboard.

Die Funktionen bekommen fertige DataFrames aus ``daten.py`` und geben
Plotly-Figuren oder HTML-Text zurück. Mit Streamlit selbst haben sie
nichts zu tun, deshalb lassen sie sich auch ohne laufende App aufrufen.
"""

import math
from collections.abc import Callable
from datetime import date
from html import escape

import pandas as pd
import plotly.graph_objects as go

from uni_dashboard import daten
from uni_dashboard.themen import Thema


# Schrift der Diagramme; die Farben kommen aus dem Thema (themen.py)
SCHRIFT = "Inter, -apple-system, 'Segoe UI', sans-serif"


def stundenplan_grafik(stundenplan: pd.DataFrame, farbe_von: Callable[[str], str],
                       heute: date, thema: Thema) -> go.Figure:
    """Zeichnet den Stundenplan als Wochenraster Mo–Fr, 8–20 Uhr.

    Jeder Termin ist ein abgerundeter Glasblock in der Fachfarbe.
    Überschneiden sich Termine, stehen sie nebeneinander und lange
    Namen werden gekürzt, damit nichts überlappt. Der heutige Tag
    ist leicht hinterlegt.

    Args:
        stundenplan: Ergebnis von :func:`daten.lade_stundenplan`.
        farbe_von: Liefert zu einem Fachnamen die Farbe als Hex-Wert.
        heute: Aktuelles Datum, für die Hervorhebung des Tages.
        thema: Farben für Text, Raster und Tooltip.

    Returns:
        Fertige Plotly-Figur ohne Werkzeugleiste und Zoom.
    """
    fig = go.Figure()
    termine = daten.lanes_bestimmen(stundenplan)

    if heute.weekday() < 5:
        fig.add_vrect(x0=heute.weekday() - 0.5, x1=heute.weekday() + 0.5,
                      fillcolor=thema.akzent, opacity=0.07, line_width=0)

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
                      fillcolor=thema.glanz, opacity=0.3, line_width=0)

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
            text=f"<b>{name}</b><br><span style='color:{thema.text_leise}'>{unterzeile}</span>",
            font=dict(size=11, color=thema.text))

        # Formen in Plotly zeigen keinen Tooltip. Ein unsichtbarer Punkt
        # in der Mitte des Blocks übernimmt das.
        uhrzeit = f"{uhr(t['Von'])}–{uhr(t['Bis'])}"
        fig.add_trace(go.Scatter(
            x=[(x0 + x1) / 2], y=[(y0 + y1) / 2], mode="markers", marker=dict(size=40, opacity=0),
            hovertemplate=f"{t['Fach']} ({t['Art']})<br>{t['Tag']} {uhrzeit}"
                          f"<br>Raum: {t['Raum'] or '–'}<extra></extra>",
        ))

    fig.update_layout(
        height=440, margin=dict(l=0, r=0, t=4, b=0), showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=SCHRIFT, color=thema.text_leise),
        hoverlabel=dict(bgcolor=thema.tooltip, bordercolor=thema.glas_rand,
                        font=dict(family=SCHRIFT, color=thema.text)),
        xaxis=dict(range=[-0.5, 4.5], tickvals=list(range(5)), ticktext=daten.WOCHENTAGE,
                   side="top", showgrid=False, zeroline=False, fixedrange=True),
        # Achse umgedreht, damit der Morgen oben steht wie im Kalender
        yaxis=dict(range=[20.3, 7.7], tickvals=list(range(8, 21, 2)),
                   ticktext=[f"{h:02d}:00" for h in range(8, 21, 2)],
                   gridcolor=thema.linie, zeroline=False, fixedrange=True),
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


def wochen_grafik(tabelle: pd.DataFrame, thema: Thema) -> go.Figure:
    """Zeichnet je Vorlesungswoche eine Säule aus erledigt und offen.

    Args:
        tabelle: Aufgaben im gewählten Zeitraum, Ergebnis von
            :func:`daten.lade_aufgaben` nach Anwendung der Filter.
        thema: Farben für Säulen, Text, Raster und Tooltip.

    Returns:
        Plotly-Figur mit gestapelten Säulen.
    """
    zaehlung = (tabelle.groupby("Woche")["Erledigt"]
                .agg(erledigt="sum", gesamt="count").reset_index())
    zaehlung["offen"] = zaehlung["gesamt"] - zaehlung["erledigt"]
    wochen = "Woche " + zaehlung["Woche"].astype(str)

    fig = go.Figure()
    glas = [("erledigt", _rgba(thema.akzent, 0.6), _rgba(thema.akzent, 0.9), "Erledigt"),
            ("offen", thema.balken_offen, thema.glas_rand, "Offen")]
    for spalte, fuellung, rand, name in glas:
        fig.add_trace(go.Bar(
            name=name, x=wochen, y=zaehlung[spalte],
            marker=dict(color=fuellung, line=dict(color=rand, width=1.5)),
            hovertemplate="%{x}: %{y} " + name.lower() + "<extra></extra>",
        ))
    fig.update_layout(
        barmode="stack", barcornerradius=6, bargap=0.45, height=300,
        margin=dict(l=0, r=0, t=30, b=0),
        font=dict(family=SCHRIFT, size=12, color=thema.text_leise),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.14, x=0, traceorder="normal", font=dict(color=thema.text)),
        hoverlabel=dict(bgcolor=thema.tooltip, bordercolor=thema.glas_rand,
                        font=dict(family=SCHRIFT, color=thema.text)),
    )
    raster = dict(gridcolor=thema.linie, zeroline=False, fixedrange=True, rangemode="tozero")
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
            f"class='zahl'>{z['erledigt']}/{z['gesamt']}</text></svg>"
            f"<div class='name'>{escape(z['Modul'])}</div>"
            f"<div class='anteil'>{anteil * 100:.0f} %</div></div>")
    return "<div class='ringe'>" + "".join(kacheln) + "</div>"


def aufgaben_tabelle(tabelle: pd.DataFrame) -> str:
    """Baut die Aufgabenliste als HTML-Tabelle.

    Streamlits eigene Tabelle zeichnet auf eine Leinwand und lässt sich
    nicht durchsichtig machen. Als HTML scheint das Glas durch, und
    die Farben folgen dem Tag- oder Nachtmodus.

    Args:
        tabelle: Aufgaben in der gewünschten Reihenfolge, mit den
            Spalten ``Modul``, ``Woche``, ``Erledigt`` und ``Notiz``.

    Returns:
        HTML-Baustein für :func:`html`; bei vielen Zeilen scrollt er.
    """
    if tabelle.empty:
        return "<div class='leise'>Keine Aufgaben für diese Auswahl.</div>"
    zeilen = []
    for _, a in tabelle.iterrows():
        status = ("<span class='status erledigt'>Erledigt</span>" if a["Erledigt"]
                  else "<span class='status offen'>Offen</span>")
        zeilen.append(f"<tr><td class='modul'>{escape(a['Modul'])}</td><td class='zahl'>{a['Woche']}</td>"
                      f"<td>{status}</td><td>{escape(a['Notiz'])}</td></tr>")
    return ("<div class='tabelle-rahmen'><table class='tabelle'>"
            "<thead><tr><th>Modul</th><th class='zahl'>Woche</th><th>Status</th><th>Notiz</th></tr></thead>"
            "<tbody>" + "".join(zeilen) + "</tbody></table></div>")


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


def uhr(stunden: float) -> str:
    """Formatiert Dezimalstunden als Uhrzeit.

    Args:
        stunden: Uhrzeit in Stunden, z. B. 8.5.

    Returns:
        Uhrzeit im Format ``HH:MM``.

    Example:
        >>> uhr(8.5)
        '08:30'
    """
    return f"{int(stunden):02d}:{round(stunden % 1 * 60):02d}"
