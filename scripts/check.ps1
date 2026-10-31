$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python tools/run_checks.py @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
