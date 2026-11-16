$bin = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN"
$asm = [System.Reflection.Assembly]::LoadFrom("$bin\OtxProcessAnalyserLib.dll")

$type = $asm.GetType("Setex.OrgaTEX.OtxProcessAnalyserLib.UserControls.PAFrmCurveActiveBatch")
if ($type) {
    Write-Host "=== PAFrmCurveActiveBatch Methods ==="
    foreach ($m in $type.GetMethods([System.Reflection.BindingFlags]"Public,NonPublic,Static,Instance")) {
        if ($m.Name -match "Load|Read|Init|File|Path|Batch|Data") {
            Write-Host "Method: $($m.Name)"
        }
    }
}

$type2 = $asm.GetType("Setex.OrgaTEX.OtxProcessAnalyserLib.Windows.SelectNativeLogFile")
if ($type2) {
    Write-Host "`n=== SelectNativeLogFile Methods & Fields ==="
    foreach ($f in $type2.GetFields([System.Reflection.BindingFlags]"Public,NonPublic,Static,Instance")) {
        Write-Host "Field: $($f.Name) ($($f.FieldType.Name))"
    }
}
