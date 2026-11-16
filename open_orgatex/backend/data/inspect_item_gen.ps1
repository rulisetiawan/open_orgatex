$bin = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN"
$asm = [System.Reflection.Assembly]::LoadFrom("$bin\OtxProcessAnalyserLib.dll")

$type = $asm.GetType("Setex.OrgaTEX.OtxProcessAnalyserLib.Windows.ItemSourceDataGenerator")
if ($type) {
    Write-Host "=== ItemSourceDataGenerator Methods ==="
    foreach ($m in $type.GetMethods([System.Reflection.BindingFlags]"Public,NonPublic,Static,Instance")) {
        $p = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
        Write-Host "Method: $($m.Name)($p) -> $($m.ReturnType.Name)"
    }
}
