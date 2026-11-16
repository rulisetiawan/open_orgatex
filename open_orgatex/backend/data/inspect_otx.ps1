$bin = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN"

# Check assemblies
$checkFiles = @("OtxWorkPlace.exe", "OtxWorkPlaceCore.dll", "OtxBatchProvider.dll", "OtxCSLib.dll", "OtxUserInterface.dll")

foreach ($fn in $checkFiles) {
    $fp = Join-Path $bin $fn
    if (Test-Path $fp) {
        Write-Host "=== Inspecting $fn ==="
        try {
            $asm = [System.Reflection.Assembly]::LoadFrom($fp)
            $types = $asm.GetTypes()
            $matching = $types | Where-Object { $_.FullName -match "Plan|Ftp|Batch|Queue|Scheduler|Communicat" }
            foreach ($t in $matching) {
                Write-Host "  $($t.FullName)"
            }
        } catch {
            Write-Host "  Error loading: $_"
        }
    }
}
