$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & uv run --locked --cache-dir data/cache/uv python scripts/download_dukascopy.py @args
    $result = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $result
