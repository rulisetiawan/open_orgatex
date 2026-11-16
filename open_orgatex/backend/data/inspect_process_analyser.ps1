$bin = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN"
$asm = [System.Reflection.Assembly]::LoadFrom("$bin\OtxProcessAnalyserLib.dll")

Write-Host "=== Types in OtxProcessAnalyserLib ==="
$types = $asm.GetTypes()
foreach ($t in $types) {
    if ($t.Name -match "Data|Reader|File|Curve|Status|Batch|Service|Manager") {
        Write-Host "Type: $($t.FullName)"
    }
}
