[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    & (Join-Path $PSScriptRoot 'bootstrap.ps1')
}
& $Python -m unittest discover -s (Join-Path $RepoRoot 'tests') -v
if ($LASTEXITCODE -ne 0) { throw "Les tests ont échoué (code $LASTEXITCODE)." }
