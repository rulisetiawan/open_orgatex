$asm = [Reflection.Assembly]::LoadFrom('C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN\OtxMachineConfigLib.dll')
$t = $asm.GetType('OtxMachineConfig.ServiceClasses.ConfigImportExportService')
$methods = $t.GetMethods([Reflection.BindingFlags]'Static,Instance,Public,NonPublic')
foreach ($m in $methods) {
    Write-Host "$($m.Name) (IsStatic: $($m.IsStatic))"
}
