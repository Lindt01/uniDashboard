"""Farbschemata für Tag und Nacht.

Jedes Thema liefert zwei Dinge: CSS-Variablen für ``stil.css`` und
Farben für die Plotly-Diagramme in ``grafiken.py``, die keine
CSS-Variablen verstehen. So stehen alle Farben an einer Stelle.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Thema:
    """Alle Farben eines Erscheinungsbilds.

    Attributes:
        name: Anzeigename im Umschalter, ``"Tag"`` oder ``"Nacht"``.
        hintergrund: CSS-Hintergrund der ganzen Seite (Verläufe erlaubt).
        text: Haupttextfarbe.
        text_leise: Farbe für Nebensächliches (Räume, Untertitel).
        akzent: Farbe für Hervorhebungen und erledigte Aufgaben.
        rot: Warnfarbe, nur für überfällige Fristen.
        linie: Rasterlinien und Trennlinien.
        glas: Füllung der Karten, halbdurchsichtig.
        glas_innen: Füllung von Elementen innerhalb einer Karte.
        glas_rand: Heller Rand, der die Glaskante andeutet.
        glanz: Lichtkante oben an jedem Glaselement.
        schatten: Schatten unter den Karten.
        balken_offen: Füllung der offenen Aufgaben im Säulendiagramm.
        tooltip: Hintergrund der Tooltips in den Diagrammen.
    """

    name: str
    hintergrund: str
    text: str
    text_leise: str
    akzent: str
    rot: str
    linie: str
    glas: str
    glas_innen: str
    glas_rand: str
    glanz: str
    schatten: str
    balken_offen: str
    tooltip: str

    def css(self) -> str:
        """Gibt die Farben als CSS-Variablen auf ``:root`` aus.

        Returns:
            CSS-Regel, die vor ``stil.css`` eingefügt wird.
        """
        werte = {
            "hintergrund": self.hintergrund, "text": self.text, "text-leise": self.text_leise,
            "akzent": self.akzent, "rot": self.rot, "linie": self.linie, "glas": self.glas,
            "glas-innen": self.glas_innen, "glas-rand": self.glas_rand,
            "glanz": self.glanz, "glas-schatten": self.schatten, "tooltip": self.tooltip,
        }
        return ":root {" + "".join(f" --{k}: {v};" for k, v in werte.items()) + " }"


TAG = Thema(
    name="Tag",
    # Schlichtes helles Grau, etwas dunkler als die Glasfelder, damit
    # sich diese abheben; Grün nur als Akzent.
    hintergrund="linear-gradient(180deg, #e4e5e8 0%, #d6d8dc 100%)",
    text="#1d1d1f",
    text_leise="#55585e",
    akzent="#1a8a4f",
    rot="#d70015",
    linie="rgba(0, 0, 0, 0.08)",
    glas="rgba(255, 255, 255, 0.30)",
    glas_innen="rgba(255, 255, 255, 0.28)",
    glas_rand="rgba(255, 255, 255, 0.65)",
    glanz="rgba(255, 255, 255, 0.95)",
    schatten="0 8px 30px rgba(0, 0, 0, 0.08)",
    balken_offen="rgba(255, 255, 255, 0.45)",
    tooltip="rgba(255, 255, 255, 0.96)",
)

NACHT = Thema(
    name="Nacht",
    hintergrund=(
        "radial-gradient(ellipse 55% 45% at 10% 5%, rgba(110, 110, 115, 0.35), transparent 70%),"
        "radial-gradient(ellipse 50% 50% at 90% 25%, rgba(80, 80, 86, 0.35), transparent 70%),"
        "radial-gradient(ellipse 60% 50% at 70% 95%, rgba(95, 95, 100, 0.3), transparent 70%),"
        "linear-gradient(160deg, #2c2c2e 0%, #232325 50%, #1c1c1e 100%)"
    ),
    text="#f5f5f7",
    text_leise="#a1a1a6",
    akzent="#30d158",
    rot="#ff453a",
    linie="rgba(255, 255, 255, 0.08)",
    glas="rgba(255, 255, 255, 0.06)",
    glas_innen="rgba(255, 255, 255, 0.06)",
    glas_rand="rgba(255, 255, 255, 0.14)",
    glanz="rgba(255, 255, 255, 0.18)",
    schatten="0 8px 32px rgba(0, 0, 0, 0.35)",
    balken_offen="rgba(255, 255, 255, 0.12)",
    tooltip="rgba(44, 44, 46, 0.95)",
)

THEMEN = {TAG.name: TAG, NACHT.name: NACHT}
"""Alle Themen nach Anzeigename, in der Reihenfolge des Umschalters."""


def nach_uhrzeit(jetzt: datetime) -> Thema:
    """Wählt das Thema passend zur Tageszeit.

    Args:
        jetzt: Aktueller Zeitpunkt.

    Returns:
        :data:`NACHT` von 19 bis 7 Uhr, sonst :data:`TAG`.

    Example:
        >>> nach_uhrzeit(datetime(2026, 11, 5, 21, 0)).name
        'Nacht'
    """
    return NACHT if jetzt.hour >= 19 or jetzt.hour < 7 else TAG
