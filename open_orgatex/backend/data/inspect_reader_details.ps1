$bin = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN"
$asm = [System.Reflection.Assembly]::LoadFrom("$bin\OtxWorkPlace.exe")
$readerType = $asm.GetType("Setex.OrgaTEX.WorkPlace.Helpers.ProgramManagerMenuReader")

# Inspect fields and methods
Write-Host "=== Fields ==="
foreach ($f in $readerType.GetFields([System.Reflection.BindingFlags]"Public,NonPublic,Static,Instance")) {
    Write-Host "Field: $($f.Name) ($($f.FieldType.Name))"
}

Write-Host "`n=== Methods & Parameters ==="
foreach ($m in $readerType.GetMethods([System.Reflection.BindingFlags]"Public,NonPublic,Static,Instance")) {
    $params = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
    Write-Host "Method: $($m.Name)($params) -> $($m.ReturnType.Name)"
}
