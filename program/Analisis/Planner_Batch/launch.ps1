$ErrorActionPreference = 'Stop'
$plannerRoot = $PSScriptRoot
$plannerPython = 'C:\Users\Lenovo Yoga 7i\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $plannerPython)) { throw 'Python lokal tidak ditemukan. Sesuaikan plannerPython di launch.ps1.' }
$plannerUrl = 'http://127.0.0.1:8768'
$plannerReady = $false
try { $plannerState = Invoke-RestMethod -Uri "$plannerUrl/api/state" -TimeoutSec 2; $plannerReady = $plannerState.product -eq 'SETEX-OFFLINE-PLANNER' } catch {}
if (-not $plannerReady) {
    $plannerProcess = Start-Process -FilePath $plannerPython -ArgumentList @('"' + (Join-Path $plannerRoot 'server.py') + '"') -WorkingDirectory $plannerRoot -WindowStyle Hidden -PassThru -RedirectStandardError (Join-Path $plannerRoot 'server-error.log') -RedirectStandardOutput (Join-Path $plannerRoot 'server.log')
    for ($plannerTry=0; $plannerTry -lt 20; $plannerTry++) {
        Start-Sleep -Milliseconds 250
        try { $plannerState = Invoke-RestMethod -Uri "$plannerUrl/api/state" -TimeoutSec 1; $plannerReady = $plannerState.product -eq 'SETEX-OFFLINE-PLANNER'; if ($plannerReady) { break } } catch {}
        if ($plannerProcess.HasExited) { break }
    }
}
if (-not $plannerReady) { throw 'Helper tidak bisa berjalan pada port 8768. Periksa Planner_Batch\server-error.log.' }
Start-Process $plannerUrl
