$bin = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN"
$asm = [System.Reflection.Assembly]::LoadFrom("$bin\OtxMachineConfigLib.dll")

$type = $asm.GetType("OtxMachineConfig.Transfer.ControllerCommunication")
if ($type) {
    Write-Host "=== Methods in ControllerCommunication ==="
    foreach ($m in $type.GetMethods([System.Reflection.BindingFlags]"Public,NonPublic,Static,Instance")) {
        $p = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
        Write-Host "Method: $($m.Name)($p) -> $($m.ReturnType.Name)"
    }
}

$type2 = $asm.GetType("OtxMachineConfig.ServiceClasses.MachineBackupHelper")
if ($type2) {
    Write-Host "`n=== Methods in MachineBackupHelper ==="
    foreach ($m in $type2.GetMethods([System.Reflection.BindingFlags]"Public,NonPublic,Static,Instance")) {
        $p = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
        Write-Host "Method: $($m.Name)($p) -> $($m.ReturnType.Name)"
    }
}
