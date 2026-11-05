"""Startet das Dashboard ohne Konsolenfenster und öffnet es in einem eigenen Fenster.

Die Endung ``.pyw`` sorgt dafür, dass Windows das Skript mit
``pythonw.exe`` ausführt, also ohne schwarzes Konsolenfenster.
Läuft der Server schon (z. B. vom letzten Start), wird nur das
Fenster geöffnet.
"""

import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ORDNER = Path(__file__).parent
PORT = 8501
ADRESSE = f"http://localhost:{PORT}"


def server_laeuft() -> bool:
    """Prüft, ob auf dem Port bereits ein Server antwortet.

    Returns:
        True, wenn eine Verbindung zu ``localhost:PORT`` möglich ist.
    """
    with socket.socket() as verbindung:
        verbindung.settimeout(0.3)
        return verbindung.connect_ex(("127.0.0.1", PORT)) == 0


def server_starten() -> None:
    """Startet Streamlit im Hintergrund und wartet, bis es erreichbar ist.

    Ausgaben und Fehlermeldungen landen in ``dashboard.log``. Gewartet
    wird höchstens 30 Sekunden.
    """
    # pythonw.exe hat keine Konsole, Streamlit braucht aber eine für
    # seine Ausgaben. Daher python.exe aus demselben Ordner, mit
    # unterdrücktem Fenster.
    python = Path(sys.executable).with_name("python.exe")
    protokoll = open(ORDNER / "dashboard.log", "w", encoding="utf-8")
    subprocess.Popen([str(python), "-m", "streamlit", "run", "app.py"],
                     cwd=ORDNER, stdout=protokoll, stderr=subprocess.STDOUT,
                     creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(60):
        if server_laeuft():
            return
        time.sleep(0.5)


def browser_finden() -> Path | None:
    """Sucht einen Chromium-Browser, der den App-Modus beherrscht.

    Geprüft werden die üblichen Installationsorte von Chrome, Edge
    und Brave, in dieser Reihenfolge.

    Returns:
        Pfad zur ausführbaren Datei, oder None, wenn keiner gefunden wurde.
    """
    orte = [os.environ.get(name, "") for name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    programme = [
        r"Google\Chrome\Application\chrome.exe",
        r"Microsoft\Edge\Application\msedge.exe",
        r"BraveSoftware\Brave-Browser\Application\brave.exe",
    ]
    for programm in programme:
        for ort in orte:
            pfad = Path(ort) / programm
            if ort and pfad.exists():
                return pfad
    return None


def fenster_oeffnen() -> None:
    """Öffnet das Dashboard als eigenes Fenster ohne Tabs und Adresszeile.

    Ohne passenden Browser wird es als normaler Tab im Standardbrowser
    geöffnet.
    """
    browser = browser_finden()
    if browser is None:
        webbrowser.open(ADRESSE)
    else:
        subprocess.Popen([str(browser), f"--app={ADRESSE}"])


if not server_laeuft():
    server_starten()
fenster_oeffnen()
