# Builds dist\MarekovEasyMxMasterSwitcher.exe. Needs Python 3.12 (the `py` launcher).
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -q -r requirements.txt
if ($LASTEXITCODE) { exit $LASTEXITCODE }

.\.venv\Scripts\pyinstaller.exe --noconfirm --onefile --windowed `
    --name MarekovEasyMxMasterSwitcher `
    --icon src\mxswitcher\app.ico `
    --add-data "src\mxswitcher\Panel.qml;mxswitcher" `
    --add-data "src\mxswitcher\app.ico;mxswitcher" `
    --add-data "src\mxswitcher\fonts;mxswitcher\fonts" `
    src\main.py
exit $LASTEXITCODE
