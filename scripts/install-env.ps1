$ErrorActionPreference = 'Stop'

$Utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $Utf8
[Console]::OutputEncoding = $Utf8
$OutputEncoding = $Utf8
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$InfoPath = Join-Path $Root 'info.json'
$Requirements = Join-Path $Root 'requirements.txt'

if (-not (Test-Path $InfoPath)) {
    Write-Error "Missing info.json: $InfoPath"
    exit 1
}
if (-not (Test-Path $Requirements)) {
    Write-Error "Missing requirements.txt: $Requirements"
    exit 1
}

$Info = Get-Content $InfoPath -Raw -Encoding UTF8 | ConvertFrom-Json
$Base = if ($env:LOCAL_SKILL_HOME) {
    $env:LOCAL_SKILL_HOME
} else {
    Join-Path $env:USERPROFILE '.openvino'
}
$VenvRoot = Join-Path $Base 'venv'
$Venv = Join-Path $VenvRoot $Info.venv_name
$Python = Join-Path $Venv 'Scripts\python.exe'
$LogDir = Join-Path $Base 'log'
$StateDir = Join-Path $Base 'state'
$RequirementsHashFile = Join-Path $StateDir 'interview-coach-agent-requirements.sha256'

New-Item -ItemType Directory -Force -Path $VenvRoot, $LogDir, $StateDir | Out-Null

function Write-LocalSkillLog {
    param([string]$Message)
    $Line = '[{0}] [install-env pid={1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $PID, $Message
    Add-Content -Path (Join-Path $LogDir 'interview-coach-agent-install.log') -Encoding UTF8 -Value $Line
}

if (-not (Test-Path $Python)) {
    Write-LocalSkillLog "Creating venv at $Venv"
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py "-$($Info.python_version)" -m venv $Venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv $Venv
    } else {
        Write-Error 'Python is required to create the local Skill environment.'
        exit 1
    }
}

$RequirementsHash = (Get-FileHash $Requirements -Algorithm SHA256).Hash.ToLowerInvariant()
$InstalledHash = if (Test-Path $RequirementsHashFile) {
    (Get-Content $RequirementsHashFile -Raw -Encoding ASCII).Trim()
} else {
    ''
}
if ($InstalledHash -ne $RequirementsHash) {
    Write-LocalSkillLog "Installing requirements from $Requirements"
    & $Python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Python -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Set-Content -Path $RequirementsHashFile -Encoding ASCII -Value $RequirementsHash
} else {
    Write-LocalSkillLog 'Requirements hash unchanged; skipping pip install.'
}

Write-LocalSkillLog 'Environment is ready.'
Write-Output "Environment ready: $Venv"
exit 0
