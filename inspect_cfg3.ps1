$asm = [Reflection.Assembly]::LoadFrom('C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN\OtxMachineConfigLib.dll')
$t = $asm.GetType('OtxMachineConfig.ServiceClasses.ConfigImportExportService')
$m = $t.GetMethod('ImportConfigFile', [Reflection.BindingFlags]'Static,Public,NonPublic')
$body = $m.GetMethodBody()
Write-Host "ImportConfigFile IL size: $($body.GetILAsByteArray().Length)"

# Let's inspect references to files and paths in this class
$strs = [System.Collections.Generic.List[string]]::new()
$bytes = $body.GetILAsByteArray()

# Let's search strings inside OtxMachineConfigLib.dll
$raw = [System.IO.File]::ReadAllBytes('C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN\OtxMachineConfigLib.dll')
$strMatches = [System.Text.RegularExpressions.Regex]::Matches([System.Text.Encoding]::ASCII.GetString($raw), '[A-Za-z0-9_\-\.\\]{4,50}\.CNF|[A-Za-z0-9_\-\.\\]{4,50}\.CFG|TYPECONF|MACHCONF')
$strMatches | Select-Object -ExpandProperty Value -Unique | ForEach-Object { Write-Host "Found config ref: $_" }
