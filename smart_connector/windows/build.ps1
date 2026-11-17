$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path "$PSScriptRoot/../..").Path
Set-Location $root
python -m PyInstaller --noconfirm --clean --onedir --windowed --uac-admin --name HUGINNConnector `
  --paths . --hidden-import win32timezone --hidden-import win32crypt `
  --hidden-import servicemanager --hidden-import win32serviceutil `
  --hidden-import win32service --hidden-import pywintypes `
  --collect-all oracledb --collect-all cryptography `
  --distpath work/connector-dist --workpath work/connector-build --specpath work smart_connector/entry.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
Copy-Item smart_connector/README.md work/connector-dist/HUGINNConnector/README.md
$compiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
& $compiler "/DPayload=$root/work/connector-dist/HUGINNConnector" "/DOutput=$root/work/connector-output" smart_connector/windows/connector.iss
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed' }
& $compiler "/DPayload=$root/work/connector-dist/HUGINNConnector" "/DOutput=$root/work/connector-upgrade-fixture" /DAppVersion=0.2.0 smart_connector/windows/connector.iss
if ($LASTEXITCODE -ne 0) { throw 'Synthetic upgrade fixture failed' }
$setup = "$root/work/connector-output/HUGINN_Smart_Connector_Setup.exe"
$hash = (Get-FileHash $setup -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  HUGINN_Smart_Connector_Setup.exe" | Set-Content "$setup.sha256" -Encoding ascii
@{ version = '0.2.1'; commit = (git rev-parse HEAD); python = (python --version); signed = $false;
   status = 'CI candidate; Oracle/TOTVS Cloud validation required' } | ConvertTo-Json | Set-Content "$root/work/connector-output/build-info.json"
