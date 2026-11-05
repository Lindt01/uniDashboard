@echo off
rem Legt eine Verknuepfung "Uni-Dashboard" auf dem Desktop an.
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo .venv fehlt. Bitte zuerst einrichten:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

powershell -NoProfile -Command ^
  "$ziel = [Environment]::GetFolderPath('Desktop') + '\Uni-Dashboard.lnk';" ^
  "$v = (New-Object -ComObject WScript.Shell).CreateShortcut($ziel);" ^
  "$v.TargetPath = '%~dp0.venv\Scripts\pythonw.exe';" ^
  "$v.Arguments = 'starten.pyw';" ^
  "$v.WorkingDirectory = '%~dp0';" ^
  "$v.IconLocation = '%~dp0docs\icon.ico';" ^
  "$v.Description = 'Uni-Dashboard';" ^
  "$v.Save()"

echo Verknuepfung "Uni-Dashboard" liegt jetzt auf dem Desktop.
pause
