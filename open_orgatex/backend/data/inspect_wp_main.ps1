$path = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN\OtxWorkPlace.exe"
$asm = [System.Reflection.Assembly]::LoadFrom($path)
$type = $asm.GetType("Setex.OrgaTEX.WorkPlace.MainWindow")
Write-Host "MainWindow in OtxWorkPlace:"
$methods = $type.GetMethods([System.Reflection.BindingFlags]"Public,NonPublic,Instance")
foreach ($m in $methods) {
    if ($m.Name -like "*Load*" -or $m.Name -like "*Init*" -or $m.Name -like "*Module*" -or $m.Name -like "*Nav*") {
        Write-Host "  Method: $($m.Name)"
    }
}
