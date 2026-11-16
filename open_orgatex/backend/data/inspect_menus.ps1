$bin = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN"
$asm = [System.Reflection.Assembly]::LoadFrom("$bin\OtxWorkPlace.exe")

$readerType = $asm.GetType("Setex.OrgaTEX.WorkPlace.Helpers.ProgramManagerMenuReader")
if ($readerType) {
    Write-Host "Found ProgramManagerMenuReader"
    $methods = $readerType.GetMethods([System.Reflection.BindingFlags]"Public,NonPublic,Static,Instance")
    foreach ($m in $methods) {
        Write-Host "  $($m.Name)"
    }
} else {
    Write-Host "ProgramManagerMenuReader not found directly"
}

# Find all Form, Menu, or Window classes in OtxWorkPlace
$types = $asm.GetTypes()
$navs = $types | Where-Object { $_.Name -match "Menu|Nav|Bar|Ribbon|Main|Tree" }
foreach ($n in $navs) {
    Write-Host "Navigation Type: $($n.FullName)"
}
