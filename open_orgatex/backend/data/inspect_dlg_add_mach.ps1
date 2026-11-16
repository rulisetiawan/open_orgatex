$bin = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN"
$asm = [System.Reflection.Assembly]::LoadFrom("$bin\OtxMachineConfigLib.dll")

$type = $asm.GetType("OtxMachineConfig.Dialogs.DlgAddMachine")
if ($type) {
    Write-Host "=== DlgAddMachine Fields & Properties ==="
    foreach ($p in $type.GetProperties([System.Reflection.BindingFlags]"Public,NonPublic,Instance")) {
        Write-Host "Property: $($p.Name) ($($p.PropertyType.Name))"
    }
}
$type2 = $asm.GetType("OtxMachineConfig.UserControls.UCMachineEdit")
if ($type2) {
    Write-Host "`n=== UCMachineEdit Properties ==="
    foreach ($p in $type2.GetProperties([System.Reflection.BindingFlags]"Public,NonPublic,Instance")) {
        Write-Host "Property: $($p.Name) ($($p.PropertyType.Name))"
    }
}
