# Portable PostgreSQL for running LifeOS without Docker on Windows (no admin rights needed).
# Binaries: EDB "postgresql-16.x-windows-x64-binaries.zip" unpacked to %LOCALAPPDATA%\lifeos-tools\pgsql.
# Cluster: %LOCALAPPDATA%\lifeos-tools\pgdata, localhost:5432, user/password/db = lifeos.
#
#   powershell -File infra/scripts/local-postgres.ps1 start|stop|status
#
# Then point Django at it:  DATABASE_URL=postgres://lifeos:lifeos@localhost:5432/lifeos
param([ValidateSet('start', 'stop', 'status')][string]$Action = 'status')

$root = Join-Path $env:LOCALAPPDATA 'lifeos-tools'
$bin = Join-Path $root 'pgsql\bin'
$data = Join-Path $root 'pgdata'
$log = Join-Path $root 'postgres.log'

if (-not (Test-Path (Join-Path $bin 'pg_ctl.exe'))) {
    Write-Error "PostgreSQL binaries not found in $bin"
    exit 1
}

switch ($Action) {
    'start' {
        # Separate hidden console and no -Wait: the postgres child must not inherit this
        # shell's handles, and PowerShell's -Wait would also wait for that child to exit.
        Start-Process -FilePath (Join-Path $bin 'pg_ctl.exe') `
            -ArgumentList @('-D', "`"$data`"", '-l', "`"$log`"", '-o', '"-p 5432"', 'start') `
            -WindowStyle Hidden
        $isReady = Join-Path $bin 'pg_isready.exe'
        for ($i = 0; $i -lt 30; $i++) {
            & $isReady -h localhost -p 5432 -q
            if ($LASTEXITCODE -eq 0) { Write-Output 'PostgreSQL is accepting connections on localhost:5432'; exit 0 }
            Start-Sleep -Seconds 1
        }
        Write-Error "PostgreSQL did not start; see $log"
        exit 1
    }
    'stop' { & (Join-Path $bin 'pg_ctl.exe') -D $data stop -m fast }
    'status' { & (Join-Path $bin 'pg_ctl.exe') -D $data status }
}
