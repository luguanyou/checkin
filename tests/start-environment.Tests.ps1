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

$tempDirectory = Join-Path ([IO.Path]::GetTempPath()) ("kaoqing-start-test-{0}" -f [Guid]::NewGuid().ToString('N'))

try {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $scriptPath = Join-Path $projectRoot 'scripts\start.ps1'
    $testEnvPath = Join-Path $projectRoot 'api\.env.test.example'
    if (-not (Test-Path -LiteralPath $scriptPath)) {
        throw "Missing startup script: $scriptPath"
    }

    $testEnv = [IO.File]::ReadAllText($testEnvPath)
    Assert-True ($testEnv -match '(?m)^ADMIN_PASSWORD=\s*$') 'The test environment must explicitly disable development admin bootstrap.'

    . $scriptPath

    $envPath = Join-Path $tempDirectory 'nested\.env'
    $firstResult = Initialize-ApiEnvironment -Path $envPath
    Assert-True ($firstResult.Created -eq $true) 'The first call must report a newly created file.'
    Assert-True (Test-Path -LiteralPath $envPath) 'The environment file was not created.'

    $content = [IO.File]::ReadAllText($envPath)
    $settings = ConvertFrom-StringData $content
    Assert-True ($settings.DATABASE_URL -eq 'mysql+pymysql://attendance:attendance@127.0.0.1:33306/attendance') 'The development database URL is incorrect.'
    Assert-True ($settings.FRONTEND_ORIGIN -eq 'http://127.0.0.1:5173') 'The frontend origin is incorrect.'
    Assert-True ($settings.REFRESH_COOKIE_SECURE -eq 'false') 'Local refresh cookies must not require HTTPS.'
    Assert-True ($settings.ADMIN_USERNAME -eq 'admin') 'The generated administrator username is incorrect.'
    Assert-True ($settings.ADMIN_PASSWORD.Length -ge 12 -and $settings.ADMIN_PASSWORD.Length -le 128) 'The generated administrator password has an invalid length.'
    Assert-True ($settings.JWT_SECRET.Length -ge 32) 'The generated JWT secret is too short.'
    Assert-True ($firstResult.Username -eq $settings.ADMIN_USERNAME) 'The returned username must match the file.'
    Assert-True ($firstResult.Password -eq $settings.ADMIN_PASSWORD) 'The returned password must match the file.'

    $originalBytes = [Convert]::ToBase64String([IO.File]::ReadAllBytes($envPath))
    $secondResult = Initialize-ApiEnvironment -Path $envPath
    $currentBytes = [Convert]::ToBase64String([IO.File]::ReadAllBytes($envPath))
    Assert-True ($secondResult.Created -eq $false) 'The second call must report an existing file.'
    Assert-True ($null -eq $secondResult.Password) 'An existing password must not be returned or displayed.'
    Assert-True ($currentBytes -eq $originalBytes) 'An existing environment file must not be modified.'

    Write-Output 'start-environment.Tests.ps1: PASS'
    exit 0
}
catch {
    Write-Error "start-environment.Tests.ps1: FAIL - $($_.Exception.Message)"
    exit 1
}
finally {
    if (Test-Path -LiteralPath $tempDirectory) {
        [IO.Directory]::Delete($tempDirectory, $true)
    }
}
