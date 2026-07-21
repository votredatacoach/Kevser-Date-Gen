[CmdletBinding()]
param(
    [ValidateSet('client', 'demo', 'smoke')]
    [string]$Profile = 'client',
    [double]$Scale = 1.0,
    [Nullable[int]]$Shards,
    [long]$Seed = 20260717,
    [string]$Output,
    [switch]$SQLite,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    & (Join-Path $PSScriptRoot 'bootstrap.ps1')
}
if (-not $Output) {
    $Output = Join-Path $RepoRoot "generated\$Profile"
}

$Arguments = @('-m', 'kevser_date_gen', '--profile', $Profile, '--scale', $Scale, '--seed', $Seed, '--output', $Output)
if ($null -ne $Shards) { $Arguments += @('--shards', $Shards.Value) }
if ($SQLite) { $Arguments += '--sqlite' }
if ($Force) { $Arguments += '--force' }

& $Python @Arguments
if ($LASTEXITCODE -ne 0) { throw "La génération a échoué avec le code $LASTEXITCODE." }
