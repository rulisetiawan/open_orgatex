$path = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN\OtxWorkPlace.exe"
$asm = [System.Reflection.Assembly]::LoadFrom($path)
$type = $asm.GetType("Setex.OrgaTEX.WorkPlace.Helpers.ProgramManagerMenuReader")
$ctors = $type.GetConstructors([System.Reflection.BindingFlags]"Public,NonPublic,Instance")
foreach ($c in $ctors) {
    Write-Host "Ctor: $($c.GetParameters() | ForEach-Object { "$($_.ParameterType.FullName) $($_.Name)" })"
}
