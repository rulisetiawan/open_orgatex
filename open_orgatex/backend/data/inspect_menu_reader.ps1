$path = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN\OtxWorkPlace.exe"
$asm = [System.Reflection.Assembly]::LoadFrom($path)
$type = $asm.GetType("Setex.OrgaTEX.WorkPlace.Helpers.ProgramManagerMenuReader")
Write-Host "Methods in ProgramManagerMenuReader:"
$methods = $type.GetMethods([System.Reflection.BindingFlags]"Public,NonPublic,Static,Instance")
foreach ($m in $methods) {
    Write-Host "  Method: $($m.Name) ($($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }))"
}
