# Uni-Dashboard

[![CI](https://github.com/Lindt01/uniDashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/Lindt01/uniDashboard/actions/workflows/ci.yml)

Wöchentlicher Überblick über mein Semester: Stundenplan, Prüfungstermine und
offene Aufgaben auf einer Seite. Die Daten pflege ich in einer Excel-Datei,
das Dashboard liest sie bei jedem Neuladen ein.

![Screenshot](docs/screenshot.png)

## Funktionen

- Stundenplan als Wochenraster, parallele Termine nebeneinander, der heutige Tag hervorgehoben
- Prüfungen mit Countdown, nicht feststehende Termine gesammelt
- Aufgabenliste mit Filtern zum Anklicken: Wochen, Module und Status (startet auf „Offen“)
- Fortschrittsring je Fach und Säulen je Woche, passen sich den gewählten Filtern an
- Tag- und Nachtmodus mit Glasflächen; beim Öffnen nach Uhrzeit gewählt (19–7 Uhr Nacht), jederzeit umschaltbar
- Aktualisiert sich selbst, sobald die Excel-Datei gespeichert wird

## Starten

Voraussetzung: Python 3.10 oder neuer.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
streamlit run app.py
```

Das Dashboard sucht die Excel-Datei in dieser Reihenfolge:

1. den Pfad in `excel_pfad.txt` im Projektordner, z. B. `C:\Users\name\Desktop\UNI.xlsx`
   (so kann die Tabelle liegen, wo man will)
2. `uni.xlsx` im Projektordner
3. `beispiel.xlsx` mit Beispieldaten

### Als Desktop-Programm (Windows)

Nach der Einrichtung oben einmal `verknuepfung_erstellen.bat` ausführen. Auf dem
Desktop liegt dann „Uni-Dashboard“: startet den Server im Hintergrund (ohne
Konsolenfenster) und öffnet das Dashboard als eigenes, maximiertes Fenster.
Fehlermeldungen landen in `dashboard.log`.

Excel sperrt die Datei beim automatischen Speichern in OneDrive. Damit das
Dashboard sie auch bei geöffneter Tabelle lesen kann, in Excel „Automatisches
Speichern“ ausschalten und mit Strg+S speichern.

### Offline

Nach der Installation der Pakete braucht das Dashboard kein Internet. Der Server
lauscht nur auf `localhost` (nicht im WLAN erreichbar), die Schriften liegen in
`static/fonts` (Inter und IBM Plex Mono, SIL Open Font License) und Nutzungsstatistiken von
Streamlit sind abgeschaltet.

## Aufbau der Excel-Datei

| Blatt | Spalten |
|---|---|
| `Fächer` | Fächer, Vorlesung, Übung, Prüfung (z. B. `11.02, 9:00` oder `TBA`) |
| `Stundenplan` | Fach, Art, Tag (`Mo`–`Fr`), Von, Bis, Raum |
| `Aufgabenliste` | Modul, Woche, Status (`Done` oder `X`), Notiz; optional Frist (`\` = keine Frist) |

In der Aufgabenliste werden die Spalten über ihre Überschrift gefunden, weitere
Spalten dürfen an beliebiger Stelle stehen.

`uni.xlsx` und `excel_pfad.txt` stehen in `.gitignore` und werden nicht hochgeladen.

## Projektstruktur

```
app.py            Oberfläche (Streamlit)
grafiken.py       Diagramme, Fortschrittsringe und Aufgabentabelle
themen.py         Farben für Tag- und Nachtmodus
stil.css          Gestaltung (Glasflächen, Karten, Filter), Farben aus themen.py
starten.pyw       Start als Desktop-Programm
daten.py          Einlesen und Aufbereiten der Excel-Blätter
pyproject.toml    Projektdaten, ruff- und pytest-Einstellungen
tests/            Tests für daten.py und themen.py
.github/workflows CI: ruff und pytest bei jedem Push
beispiel.xlsx     Beispieldaten
.streamlit/       Theme, Schrift, Server-Einstellungen
static/fonts/     Schriften (lokal statt Google Fonts)
```

## Entwicklung

Docstrings folgen dem Google-Stil, Funktionen haben Type Hints. Bei jedem Push
prüft GitHub Actions beides automatisch unter Python 3.10 und 3.12. Lokal:

```bash
pip install -r requirements-dev.txt
ruff check .   # Stil und Docstrings
pytest         # Tests in tests/ und Beispiele in den Docstrings
```

## Geplant

- [ ] Docker-Image
- [x] Tests für `daten.py`
- [x] GitHub Actions (Lint und Tests)
- [ ] Paketversionen festlegen und automatisch auf Sicherheitslücken prüfen (Dependabot, pip-audit)
- [ ] Betrieb im Homelab
- [x] Tag- und Nachtmodus
- [ ] Fristen: Spalte „Frist“ auswerten, Anzeige „Diese Woche fällig“, Überfälliges hervorheben
- [ ] Wochenrückblick: erledigte Aufgaben der letzten Woche im Vergleich zur Vorwoche
- [ ] Uni-Mails unten im Dashboard anzeigen (IMAP, nur lesend, Passwort in der Windows-Anmeldeinformationsverwaltung)

## Lizenz

Code unter der [MIT-Lizenz](LICENSE). Die Schriften in `static/fonts` stehen
unter der SIL Open Font License (Lizenztexte im selben Ordner).
