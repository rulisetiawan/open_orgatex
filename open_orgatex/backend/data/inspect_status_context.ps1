$bin = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN"
$targetDlls = @(
    "OtxProcessAnalyserLib.dll",
    "OtxMachineConfigLib.dll",
    "OtxDataLinker.dll",
    "OtxBatchProvider.dll",
    "OtxCSLib.dll",
    "OtxController.dll",
    "cdc800.exe",
    "zkx200.exe"
)

foreach ($dll in $targetDlls) {
    $fp = Join-Path $bin $dll
    if (Test-Path $fp) {
        $bytes = [System.IO.File]::ReadAllBytes($fp)
        $text = [System.Text.Encoding]::ASCII.GetString($bytes)
        
        $hasStatusAct = $text -match "STATUS\.ACT"
        $hasStatus = $text -match "STATUS"
        Write-Host "File ${dll} -> STATUS.ACT=${hasStatusAct}, STATUS=${hasStatus}"
        
        # Extract surrounding context around STATUS.ACT if found
        if ($hasStatusAct) {
            $regex = [regex]"(?i).{0,60}STATUS\.ACT.{0,60}"
            $matches = $regex.Matches($text)
            foreach ($m in $matches) {
                $clean = ($m.Value -replace '[^\x20-\x7E]', ' ').Trim()
                Write-Host "   Context: $clean"
            }
        }
    }
}
