$ErrorActionPreference = 'Stop'

$Utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $Utf8
[Console]::OutputEncoding = $Utf8
$OutputEncoding = $Utf8
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$Root = Split-Path -Parent $PSScriptRoot
$Bin = Join-Path $Root 'bin'
$Platform = Join-Path $Bin 'platform.exe'

if (Test-Path $Platform) {
    $IsAipc = (& $Platform --is-aipc).Trim()
    if ($IsAipc -ne '1') {
        Write-Output 'This skill requires an Intel AIPC platform.'
        exit 1
    }
}

Push-Location $Root
try {
    & (Join-Path $PSScriptRoot 'install-env.ps1')
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $Info = Get-Content (Join-Path $Root 'info.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $Base = if ($env:LOCAL_SKILL_HOME) {
        $env:LOCAL_SKILL_HOME
    } else {
        Join-Path $env:USERPROFILE '.openvino'
    }
    $Python = Join-Path (Join-Path (Join-Path $Base 'venv') $Info.venv_name) 'Scripts\python.exe'
    if (-not (Test-Path $Python)) {
        Write-Error "Local Skill Python was not created: $Python"
        exit 1
    }

    & $Python (Join-Path $PSScriptRoot 'client.py') @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
