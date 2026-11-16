$bin = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN"
$dlls = Get-ChildItem -Path $bin -Filter "Otx*.dll"
foreach ($d in $dlls) {
    try {
        $asm = [System.Reflection.Assembly]::LoadFrom($d.FullName)
        $types = $asm.GetTypes()
        foreach ($t in $types) {
            $interfaces = $t.GetInterfaces()
            foreach ($iface in $interfaces) {
                if ($iface.Name -like "*Module*" -or $iface.Name -like "*Plugin*") {
                    Write-Host "Found Module: $($t.FullName) in $($d.Name) (implements $($iface.Name))"
                }
            }
        }
    } catch {}
}
