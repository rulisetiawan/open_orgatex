$asm = [Reflection.Assembly]::LoadFrom('C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN\OtxMachineConfigLib.dll')
$t = $asm.GetType('OtxMachineConfig.ServiceClasses.ConfigImportExportService')
Write-Host "=== ConfigImportExportService Methods ==="
$t.GetMethods() | ForEach-Object {
    $params = ($_.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
    Write-Host "$($_.ReturnType.Name) $($_.Name)($params)"
}

Write-Host "`n=== MachineConfigService Methods ==="
$t2 = $asm.GetType('OtxMachineConfig.ServiceClasses.MachineConfigService')
$t2.GetMethods() | ForEach-Object {
    $params = ($_.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
    Write-Host "$($_.ReturnType.Name) $($_.Name)($params)"
}
