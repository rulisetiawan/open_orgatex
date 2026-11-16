$asm = [Reflection.Assembly]::LoadFrom('C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN\OtxMachineConfigLib.dll')
$t = $asm.GetType('OtxMachineConfig.ServiceClasses.ConfigImportExportService')

Write-Host "=== All Fields & Properties in ConfigImportExportService ==="
$t.GetFields([Reflection.BindingFlags]'Static,NonPublic,Public,Instance') | ForEach-Object {
    Write-Host "$($_.FieldType.Name) $($_.Name)"
}

Write-Host "`n=== All Types in SecomCEDefines ==="
$secomAsm = [Reflection.Assembly]::LoadFrom('C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN\SecomCEDefines.dll')
$secomAsm.GetTypes() | Where-Object { $_.Name -match 'TypeConf|Config|File' } | ForEach-Object {
    Write-Host $_.FullName
}
