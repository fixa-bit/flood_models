param([string]$ProjectId = $env:EE_PROJECT, [switch]$Authenticate)

$ErrorActionPreference = 'Stop'
if (-not $ProjectId) {
    $ProjectId = Read-Host 'Enter your Earth Engine-enabled Google Cloud project ID'
}
if (-not $ProjectId) { throw 'An Earth Engine-enabled project ID is required.' }
$extractPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $extractPython)) {
    python -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
& $extractPython -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Could not install Earth Engine dependencies.' }
$extractArguments = @((Join-Path $PSScriptRoot 'extract_precipitation.py'), '--project', $ProjectId)
if ($Authenticate) { $extractArguments += '--authenticate' }
& $extractPython @extractArguments
if ($LASTEXITCODE -ne 0) { throw 'Extraction or QA did not finish successfully. Review the error before rebuilding the portal.' }
$workspaceDirectory = $PSScriptRoot
while (-not (Test-Path -LiteralPath (Join-Path $workspaceDirectory 'data_portal/build_dashboard.py'))) {
    $workspaceDirectory = Split-Path -Parent $workspaceDirectory
    if (-not $workspaceDirectory) { throw 'Could not locate the portal workspace.' }
}
& $extractPython (Join-Path $workspaceDirectory 'data_portal/build_dashboard.py')
if ($LASTEXITCODE -ne 0) { throw 'Portal rebuild failed.' }
Write-Host 'Extraction and portal snapshot updated. Open http://127.0.0.1:8787/#summary and reload the snapshot.'
