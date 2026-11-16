$ErrorActionPreference='Stop'
$plannerServerPath=Join-Path $PSScriptRoot 'server.py'
$plannerListeners=Get-NetTCPConnection -LocalPort 8768 -State Listen -ErrorAction SilentlyContinue
foreach ($plannerPid in ($plannerListeners | Select-Object -ExpandProperty OwningProcess -Unique)) {
    $plannerProcessInfo=Get-CimInstance Win32_Process -Filter "ProcessId=$plannerPid"
    if ($plannerProcessInfo.Name -notmatch '^python(w)?\.exe$' -or -not $plannerProcessInfo.CommandLine.Contains($plannerServerPath)) { throw 'Port 8768 dipakai proses lain. Tidak dihentikan.' }
    Stop-Process -Id $plannerPid
}
$plannerPython='C:\Users\Lenovo Yoga 7i\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
Start-Process -FilePath $plannerPython -ArgumentList @('"'+$plannerServerPath+'"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardError (Join-Path $PSScriptRoot 'server-error.log') -RedirectStandardOutput (Join-Path $PSScriptRoot 'server.log')
