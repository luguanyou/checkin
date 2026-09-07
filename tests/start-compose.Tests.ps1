$ErrorActionPreference = 'Stop'

function Assert-Match {
    param(
        [string]$Text,
        [string]$Pattern,
        [string]$Message
    )

    if ($Text -notmatch $Pattern) {
        throw $Message
    }
}

try {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $composePath = Join-Path $projectRoot 'api\compose.dev.yaml'
    $testComposePath = Join-Path $projectRoot 'api\compose.test.yaml'
    $testEnvironmentPath = Join-Path $projectRoot 'api\.env.test.example'
    $pytestConfigPath = Join-Path $projectRoot 'api\tests\conftest.py'
    $gitignorePath = Join-Path $projectRoot '.gitignore'

    if (-not (Test-Path -LiteralPath $composePath)) {
        throw "Missing development Compose file: $composePath"
    }
    if (-not (Test-Path -LiteralPath $gitignorePath)) {
        throw "Missing .gitignore file: $gitignorePath"
    }
    if (-not (Test-Path -LiteralPath $testComposePath)) {
        throw "Missing test Compose file: $testComposePath"
    }
    if (-not (Test-Path -LiteralPath $testEnvironmentPath)) {
        throw "Missing test environment example: $testEnvironmentPath"
    }
    if (-not (Test-Path -LiteralPath $pytestConfigPath)) {
        throw "Missing pytest configuration: $pytestConfigPath"
    }

    $compose = Get-Content -LiteralPath $composePath -Raw
    $testCompose = Get-Content -LiteralPath $testComposePath -Raw
    $testEnvironment = Get-Content -LiteralPath $testEnvironmentPath -Raw
    $pytestConfig = Get-Content -LiteralPath $pytestConfigPath -Raw
    $gitignore = Get-Content -LiteralPath $gitignorePath -Raw

    Assert-Match $compose 'image:\s*mysql:8\.4' 'Compose must use MySQL 8.4.'
    Assert-Match $compose 'MYSQL_DATABASE:\s*attendance' 'Compose must create the attendance database.'
    Assert-Match $compose '127\.0\.0\.1:33306:3306' 'MySQL must bind to local port 33306.'
    Assert-Match $compose 'healthcheck:' 'Compose must define a MySQL health check.'
    Assert-Match $compose 'attendance_mysql_data:/var/lib/mysql' 'MySQL must mount the named data volume.'
    Assert-Match $compose '(?ms)^volumes:\s*\r?\n\s+attendance_mysql_data:' 'Compose must declare the named data volume.'
    Assert-Match $testCompose '127\.0\.0\.1:33307:3306' 'Test MySQL must use isolated local port 33307.'
    Assert-Match $testEnvironment '127\.0\.0\.1:33307/attendance_test' 'The test environment must target isolated port 33307.'
    Assert-Match $pytestConfig '127\.0\.0\.1:33307/attendance_test' 'Pytest must default to isolated port 33307.'
    Assert-Match $gitignore '(?m)^/api/\.env\s*$' '.gitignore must protect api/.env.'
    Assert-Match $gitignore '(?m)^/\.env\.local\s*$' '.gitignore must protect .env.local.'

    Write-Output 'start-compose.Tests.ps1: PASS'
    exit 0
}
catch {
    Write-Error "start-compose.Tests.ps1: FAIL - $($_.Exception.Message)"
    exit 1
}
