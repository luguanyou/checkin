[CmdletBinding()]
param(
    [switch]$SkipBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function New-RandomSecret {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateRange(1, 1024)]
        [int]$ByteCount
    )

    $bytes = New-Object byte[] $ByteCount
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }

    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Initialize-ApiEnvironment {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (Test-Path -LiteralPath $Path) {
        return [PSCustomObject]@{
            Created = $false
            Username = $null
            Password = $null
        }
    }

    $parentDirectory = Split-Path -Parent $Path
    if ($parentDirectory) {
        [IO.Directory]::CreateDirectory($parentDirectory) | Out-Null
    }

    $jwtSecret = New-RandomSecret -ByteCount 48
    $adminPassword = New-RandomSecret -ByteCount 18
    $content = @"
APP_ENV=development
DATABASE_URL=mysql+pymysql://attendance:attendance@127.0.0.1:33306/attendance
JWT_SECRET=$jwtSecret
FRONTEND_ORIGIN=http://127.0.0.1:5173
ACCESS_TOKEN_TTL_SECONDS=900
REFRESH_TOKEN_TTL_SECONDS=604800
REFRESH_COOKIE_SECURE=false
ADMIN_USERNAME=admin
ADMIN_DISPLAY_NAME=Super Administrator
ADMIN_PASSWORD=$adminPassword
"@

    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, $content, $utf8WithoutBom)

    return [PSCustomObject]@{
        Created = $true
        Username = 'admin'
        Password = $adminPassword
    }
}

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found. Install it and try again."
    }
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory
    )

    $originalLocation = Get-Location
    try {
        Set-Location -LiteralPath $WorkingDirectory
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
        }
    }
    finally {
        Set-Location -LiteralPath $originalLocation
    }
}

function Wait-HttpEndpoint {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri,

        [Parameter(Mandatory = $true)]
        [string]$Name,

        [ValidateRange(1, 600)]
        [int]$TimeoutSeconds = 60
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                return
            }
        }
        catch {
            # The service may still be starting. The timeout below reports the final failure.
        }

        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $deadline)

    throw "$Name did not become ready at $Uri within $TimeoutSeconds seconds. Check its service window for details."
}

function Start-DevelopmentStack {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $apiRoot = Join-Path $projectRoot 'api'
    $apiEnvPath = Join-Path $apiRoot '.env'
    $apiReadyUrl = 'http://127.0.0.1:8000/api/v1/health/ready'
    $frontendUrl = 'http://127.0.0.1:5173'

    try {
        Write-Host '[1/7] Checking prerequisites...'
        Assert-Command docker
        Assert-Command uv
        Assert-Command node
        Assert-Command npm
        Invoke-Native -FilePath docker -Arguments @('info') -WorkingDirectory $projectRoot

        Write-Host '[2/7] Preparing local environment...'
        $environment = Initialize-ApiEnvironment -Path $apiEnvPath

        Write-Host '[3/7] Starting development MySQL...'
        Invoke-Native -FilePath docker -Arguments @(
            'compose', '-p', 'attendance-dev', '-f', 'compose.dev.yaml',
            'up', '-d', '--wait'
        ) -WorkingDirectory $apiRoot

        Write-Host '[4/7] Synchronizing dependencies...'
        Invoke-Native -FilePath uv -Arguments @('sync', '--group', 'dev') -WorkingDirectory $apiRoot
        Invoke-Native -FilePath npm -Arguments @('install') -WorkingDirectory $projectRoot

        Write-Host '[5/7] Applying database migrations...'
        Invoke-Native -FilePath uv -Arguments @('run', 'alembic', 'upgrade', 'head') -WorkingDirectory $apiRoot

        Write-Host '[6/7] Starting API and frontend windows...'
        Start-Process -FilePath 'powershell.exe' -WorkingDirectory $apiRoot -ArgumentList @(
            '-NoLogo', '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-Command',
            'uv run uvicorn attendance_api.main:app --host 127.0.0.1 --port 8000'
        ) | Out-Null
        Start-Process -FilePath 'powershell.exe' -WorkingDirectory $projectRoot -ArgumentList @(
            '-NoLogo', '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-Command',
            'npm run dev'
        ) | Out-Null

        Write-Host '[7/7] Waiting for services...'
        Wait-HttpEndpoint -Uri $apiReadyUrl -Name 'Attendance API' -TimeoutSeconds 60
        Wait-HttpEndpoint -Uri $frontendUrl -Name 'Vite frontend' -TimeoutSeconds 60

        Write-Host ''
        Write-Host 'Attendance application is ready.' -ForegroundColor Green
        Write-Host "Frontend: $frontendUrl"
        Write-Host 'API docs: http://127.0.0.1:8000/docs'
        if ($environment.Created) {
            Write-Host ''
            Write-Host 'Initial local administrator credentials:' -ForegroundColor Yellow
            Write-Host "Username: $($environment.Username)"
            Write-Host "Password: $($environment.Password)"
            Write-Host "Saved in: $apiEnvPath"
        }

        if (-not $SkipBrowser) {
            Start-Process $frontendUrl | Out-Null
        }

        return 0
    }
    catch {
        Write-Error "Startup failed: $($_.Exception.Message)"
        return 1
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    exit (Start-DevelopmentStack)
}
