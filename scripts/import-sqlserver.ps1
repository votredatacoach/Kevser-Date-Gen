[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Server,
    [string]$Database = 'Adventure',
    [Parameter(Mandatory)]
    [string]$DataRoot,
    [switch]$Recreate
)

$ErrorActionPreference = 'Stop'
$SqlCmd = Get-Command sqlcmd -ErrorAction Stop
$ResolvedRoot = (Resolve-Path -LiteralPath $DataRoot).Path
$SqlRoot = Join-Path $ResolvedRoot 'sql'
$RecreateDatabase = if ($Recreate) { '1' } else { '0' }
$Manifest = Join-Path $ResolvedRoot 'manifest.sha256'

if (-not (Test-Path -LiteralPath $Manifest)) {
    throw "Manifeste introuvable : $Manifest. Régénérez le bundle avant l'import."
}
$RootPrefix = $ResolvedRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
$ManifestEntries = 0
foreach ($Line in Get-Content -LiteralPath $Manifest) {
    if ([string]::IsNullOrWhiteSpace($Line)) { continue }
    if ($Line -notmatch '^([0-9a-fA-F]{64})  (.+)$') {
        throw "Ligne de manifeste invalide : $Line"
    }
    $ExpectedHash = $Matches[1].ToLowerInvariant()
    $RelativePath = $Matches[2].Replace('/', [IO.Path]::DirectorySeparatorChar)
    $FilePath = [IO.Path]::GetFullPath((Join-Path $ResolvedRoot $RelativePath))
    if (-not $FilePath.StartsWith($RootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Chemin de manifeste hors du bundle : $RelativePath"
    }
    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        throw "Fichier déclaré dans le manifeste introuvable : $RelativePath"
    }
    $ActualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $FilePath).Hash.ToLowerInvariant()
    if ($ActualHash -ne $ExpectedHash) {
        throw "Empreinte invalide pour $RelativePath. L'import est annulé avant toute modification SQL."
    }
    $ManifestEntries++
}
if ($ManifestEntries -eq 0) { throw 'Le manifeste ne contient aucun fichier.' }
Write-Host "Manifeste vérifié : $ManifestEntries fichiers intègres."

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
    & $SqlCmd.Source -S $Server -d $TargetDatabase -E -b -i $Path -v "DatabaseName=$Database" "DataRoot=$ResolvedRoot" "RecreateDatabase=$RecreateDatabase"
    if ($LASTEXITCODE -ne 0) { throw "Échec de $Script (code $LASTEXITCODE)." }
}

Write-Host 'Import terminé. Lancez validate-sqlserver.ps1 pour les contrôles métier.'
