$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    & (Join-Path $Root 'scripts\run.ps1') status
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & (Join-Path $Root 'scripts\run.ps1') roles
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & (Join-Path $Root 'scripts\run.ps1') report `
        --input 'examples\interview-coach\pm-second-answer.json' `
        --output 'build\aipc-test-report.md' `
        --overwrite
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $Report = Join-Path $Root 'build\aipc-test-report.md'
    if (-not (Test-Path $Report)) {
        Write-Error "Expected report was not created: $Report"
        exit 1
    }
    $Text = Get-Content $Report -Raw -Encoding UTF8
    if (-not $Text.Contains('| 4.2 / 7 | 6.7 / 7 | +2.5 |')) {
        Write-Error 'Report does not contain the expected score comparison.'
        exit 1
    }

    & (Join-Path $Root 'scripts\run.ps1') shutdown
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Output 'AIPC local Skill end-to-end test passed.'
    exit 0
}
finally {
    Pop-Location
}
