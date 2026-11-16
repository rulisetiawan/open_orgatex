$secomAsm = [Reflection.Assembly]::LoadFrom('C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN\SecomCEDefines.dll')

Write-Host "=== TypeconfFileNames ==="
$t1 = $secomAsm.GetType('OtxCSLib.Secom.Configuration.TypeconfFileNames')
$t1.GetFields([Reflection.BindingFlags]'Static,Public,NonPublic') | ForEach-Object {
    Write-Host "$($_.Name) = $($_.GetValue($null))"
}

Write-Host "`n=== TypeconfConstants ==="
$t2 = $secomAsm.GetType('OtxCSLib.Secom.Configuration.TypeconfConstants')
$t2.GetFields([Reflection.BindingFlags]'Static,Public,NonPublic') | ForEach-Object {
    Write-Host "$($_.Name) = $($_.GetValue($null))"
}

Write-Host "`n=== CEFileNames ==="
$t3 = $secomAsm.GetType('OtxCSLib.Secom.CEFileNames')
$t3.GetFields([Reflection.BindingFlags]'Static,Public,NonPublic') | ForEach-Object {
    Write-Host "$($_.Name) = $($_.GetValue($null))"
}

Write-Host "`n=== Typeconf_ID ==="
$t4 = $secomAsm.GetType('OtxCSLib.Secom.Configuration.Typeconf_ID')
$t4.GetFields([Reflection.BindingFlags]'Static,Public,NonPublic') | ForEach-Object {
    Write-Host "$($_.Name) = $($_.GetValue($null))"
}
