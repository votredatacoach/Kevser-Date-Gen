[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Server,
    [string]$Database = 'Adventure',
    [Parameter(Mandatory)]
    [string]$DataRoot
)

$ErrorActionPreference = 'Stop'
$SqlCmd = Get-Command sqlcmd -ErrorAction Stop
$ResolvedRoot = (Resolve-Path -LiteralPath $DataRoot).Path
$SqlRoot = Join-Path $ResolvedRoot 'sql'

$Scripts = @(
    '00_create_database.sql',
    '01_schema.sql',
    '02_schema_corrections.sql',
    '03_bulk_load.sql',
    '04_indexes.sql'
)

foreach ($Script in $Scripts) {
    $Path = Join-Path $SqlRoot $Script
    if (-not (Test-Path -LiteralPath $Path)) { throw "Script introuvable : $Path" }
    Write-Host "Exécution de $Script"
    $TargetDatabase = if ($Script -eq '00_create_database.sql') { 'master' } else { $Database }
    & $SqlCmd.Source -S $Server -d $TargetDatabase -E -b -i $Path -v "DatabaseName=$Database" "DataRoot=$ResolvedRoot"
    if ($LASTEXITCODE -ne 0) { throw "Échec de $Script (code $LASTEXITCODE)." }
}

Write-Host 'Import terminé. Lancez validate-sqlserver.ps1 pour les contrôles métier.'
