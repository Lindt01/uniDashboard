@echo off
rem Legt eine Verknuepfung "Uni-Dashboard" auf dem Desktop an.
rem Das Skript liegt in windows\, alle Pfade beziehen sich auf den Projektordner darueber.
pushd "%~dp0.."
set "PROJEKT=%CD%"
popd

if not exist "%PROJEKT%\.venv\Scripts\pythonw.exe" (
    echo .venv fehlt. Bitte zuerst im Projektordner einrichten:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo   pip install -e . --no-deps
    pause
    exit /b 1
)

powershell -NoProfile -Command ^
  "$ziel = [Environment]::GetFolderPath('Desktop') + '\Uni-Dashboard.lnk';" ^
  "$v = (New-Object -ComObject WScript.Shell).CreateShortcut($ziel);" ^
  "$v.TargetPath = '%PROJEKT%\.venv\Scripts\pythonw.exe';" ^
  "$v.Arguments = 'windows\starten.pyw';" ^
  "$v.WorkingDirectory = '%PROJEKT%';" ^
  "$v.IconLocation = '%PROJEKT%\docs\logo.ico';" ^
  "$v.Description = 'Uni-Dashboard';" ^
  "$v.Save()"

echo Verknuepfung "Uni-Dashboard" liegt jetzt auf dem Desktop.
pause
