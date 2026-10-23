Push-Location -LiteralPath $PSScriptRoot
try {
    python serve.py
} finally {
    Pop-Location
}
