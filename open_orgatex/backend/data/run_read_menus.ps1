$path = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN\OtxWorkPlace.exe"
$asm = [System.Reflection.Assembly]::LoadFrom($path)
$type = $asm.GetType("Setex.OrgaTEX.WorkPlace.Helpers.ProgramManagerMenuReader")
try {
    $inst = [System.Activator]::CreateInstance($type)
    $res = $inst.ReadAllUserMenus()
    Write-Host "ReadAllUserMenus result: $res"
} catch {
    Write-Host "Error invoking: $_"
}
