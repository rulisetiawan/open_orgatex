$bin = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN"

$asm = [System.Reflection.Assembly]::LoadFrom("$bin\OtxMachineConfigLib.dll")
Write-Host "=== Inspecting OtxMachineConfigLib ==="
$types = $asm.GetTypes()
foreach ($t in $types) {
    if ($t.Name -match "Machine|Path|Share|Status|Config|Network") {
        Write-Host "Type: $($t.FullName)"
        $props = $t.GetProperties()
        foreach ($p in $props) {
            if ($p.Name -match "Path|Share|Folder|Status|Address|Ip") {
                Write-Host "   Property: $($p.Name) ($($p.PropertyType.Name))"
            }
        }
    }
}
