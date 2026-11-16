$path = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN\OtxWorkPlace.exe"
try {
    $asm = [System.Reflection.Assembly]::LoadFrom($path)
    Write-Host "OtxWorkPlace is .NET Assembly!"
    $types = $asm.GetTypes()
    Write-Host "Total types: $($types.Count)"
    foreach ($t in $types) {
        if ($t.Name -like "*Menu*" -or $t.Name -like "*Main*" -or $t.Name -like "*Form*" -or $t.Name -like "*Tree*") {
            Write-Host "Type: $($t.FullName)"
        }
    }
} catch {
    Write-Host "Error loading as .NET: $_"
}
