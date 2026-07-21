[CmdletBinding()]
param(
    [string]$Version = '1.0.0',
    [string]$DataRoot
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $RepoRoot 'dist'
New-Item -ItemType Directory -Path $Dist -Force | Out-Null
& (Join-Path $PSScriptRoot 'test.ps1')

$SourceZip = Join-Path $Dist "Kevser-Date-Gen-v$Version-source.zip"
$SourceItems = @('README.md', 'LICENSE', 'CHANGELOG.md', 'pyproject.toml', 'src', 'schema', 'profiles', 'scripts', 'tests', 'docs') | ForEach-Object { Join-Path $RepoRoot $_ }
Compress-Archive -LiteralPath $SourceItems -DestinationPath $SourceZip -Force

if ($DataRoot) {
    $ResolvedData = (Resolve-Path -LiteralPath $DataRoot).Path
    $DataZip = Join-Path $Dist "Kevser-Date-Gen-v$Version-client-data.zip"
    Compress-Archive -Path (Join-Path $ResolvedData '*') -DestinationPath $DataZip -Force
}

Write-Host "Package source : $SourceZip"
