[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Server,
    [string]$Database = 'Adventure',
    [string]$DataRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) 'generated\client')
)

$ErrorActionPreference = 'Stop'
$SqlCmd = Get-Command sqlcmd -ErrorAction Stop
$Validation = Join-Path $DataRoot 'sql\05_validation.sql'
if (-not (Test-Path -LiteralPath $Validation)) { throw "Script introuvable : $Validation" }
& $SqlCmd.Source -S $Server -d $Database -E -b -i $Validation -v "DatabaseName=$Database"
if ($LASTEXITCODE -ne 0) { throw "La validation SQL Server a échoué (code $LASTEXITCODE)." }
