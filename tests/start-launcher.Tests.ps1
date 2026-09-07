$ErrorActionPreference = 'Stop'

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Match {
    param(
        [string]$Text,
        [string]$Pattern,
        [string]$Message
    )

    Assert-True ($Text -match $Pattern) $Message
}

try {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $scriptPath = Join-Path $projectRoot 'scripts\start.ps1'
    $batchPath = Join-Path $projectRoot 'start.bat'

    if (-not (Test-Path -LiteralPath $scriptPath)) {
        throw "Missing startup script: $scriptPath"
    }

    $tokens = $null
    $parseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        $scriptPath,
        [ref]$tokens,
        [ref]$parseErrors
    ) | Out-Null
    Assert-True ($parseErrors.Count -eq 0) "start.ps1 has parse errors: $($parseErrors -join '; ')"

    $script = Get-Content -LiteralPath $scriptPath -Raw
    Assert-Match $script "'attendance-dev'" 'The launcher must use the attendance-dev Compose project.'
    Assert-Match $script "'sync',\s*'--group',\s*'dev'" 'The launcher must run uv sync --group dev.'
    Assert-Match $script "'install'" 'The launcher must run npm install.'
    Assert-Match $script "'alembic',\s*'upgrade',\s*'head'" 'The launcher must migrate the database to head.'
    Assert-Match $script 'uvicorn attendance_api\.main:app --host 127\.0\.0\.1 --port 8000' 'The launcher must start Uvicorn on the local API port.'
    Assert-Match $script 'npm run dev' 'The launcher must start Vite.'
    Assert-Match $script '/api/v1/health/ready' 'The launcher must poll API readiness.'
    Assert-Match $script 'http://127\.0\.0\.1:5173' 'The launcher must use the frontend URL.'
    Assert-Match $script 'Start-Process' 'The launcher must create service windows and open the browser.'
    Assert-Match $script 'Assert-Command docker[\s\S]*Assert-Command uv[\s\S]*Assert-Command node[\s\S]*Assert-Command npm' 'Prerequisites must be checked in the expected order.'

    if (-not (Test-Path -LiteralPath $batchPath)) {
        throw "Missing double-click entry point: $batchPath"
    }
    $batch = Get-Content -LiteralPath $batchPath -Raw
    Assert-Match $batch '(?i)-ExecutionPolicy Bypass' 'start.bat must use a process-scoped execution policy bypass.'
    Assert-Match $batch '(?i)scripts\\start\.ps1' 'start.bat must invoke scripts\start.ps1.'
    Assert-Match $batch '(?i)exit /b %START_EXIT_CODE%' 'start.bat must propagate the launcher exit code.'
    Assert-Match $batch '(?is)if not .*?\(.*?pause.*?\)' 'start.bat must pause inside the failure branch.'
    Assert-True (([regex]::Matches($batch, '(?im)^\s*pause\s*$')).Count -eq 1) 'start.bat must contain exactly one failure pause.'

    Write-Output 'start-launcher.Tests.ps1: PASS'
    exit 0
}
catch {
    Write-Error "start-launcher.Tests.ps1: FAIL - $($_.Exception.Message)"
    exit 1
}
