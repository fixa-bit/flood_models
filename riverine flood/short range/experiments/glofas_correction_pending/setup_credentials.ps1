param([switch]$ReplaceExisting)
$ErrorActionPreference = 'Stop'
$credentialPath = Join-Path $env:USERPROFILE '.cdsapirc'
if ((Test-Path -LiteralPath $credentialPath) -and -not $ReplaceExisting) {
    Write-Host 'An existing .cdsapirc was preserved. Use -ReplaceExisting only to replace it deliberately.'
    exit 0
}
Write-Host 'Sign in at https://ewds.climate.copernicus.eu/how-to-api and obtain your personal access token.'
Write-Host 'Accept the CEMS-FLOODS dataset terms in your own EWDS account if requested.'
$secureToken = Read-Host 'Paste the EWDS personal access token (input is hidden)' -AsSecureString
$tokenValue = [System.Net.NetworkCredential]::new('', $secureToken).Password.Trim()
if ([string]::IsNullOrWhiteSpace($tokenValue) -or $tokenValue.Contains("`n") -or $tokenValue.Contains("`r")) {
    throw 'The token is empty or contains a newline. No file was written.'
}
$credentialText = "url: https://ewds.climate.copernicus.eu/api`nkey: $tokenValue`n"
[System.IO.File]::WriteAllText($credentialPath, $credentialText, [System.Text.UTF8Encoding]::new($false))
$tokenValue = $null
$credentialText = $null
$secureToken.Dispose()
Write-Host "EWDS credentials saved to $credentialPath. The token was not printed or saved in this project."
