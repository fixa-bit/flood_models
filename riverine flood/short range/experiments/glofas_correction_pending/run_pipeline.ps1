param([ValidateSet('status','bootstrap','download','prepare','train','forecast','all')][string]$Action = 'all')
$ErrorActionPreference = 'Stop'
$modelDirectory = Split-Path -Parent $PSScriptRoot
$projectPython = Join-Path $modelDirectory '../experiments/marala_observed/.venv/Scripts/python.exe'
Push-Location -LiteralPath $modelDirectory
try {
    & $projectPython -u -m glofas_correction.run_pipeline --action $Action --resume
    if ($LASTEXITCODE -ne 0) { throw "GloFAS pipeline failed with exit code $LASTEXITCODE. See glofas_correction/LAST_ERROR.json." }
} finally { Pop-Location }
