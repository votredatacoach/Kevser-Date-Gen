[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python 3.11 ou plus récent est requis et doit être disponible dans le PATH.'
}

$Version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$Version -lt [version]'3.11') {
    throw "Python 3.11 ou plus récent est requis. Version détectée : $Version"
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    & python -m venv (Join-Path $RepoRoot '.venv')
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e $RepoRoot
Write-Host "Environnement prêt : $VenvPython"
