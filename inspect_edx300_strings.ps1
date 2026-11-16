$bytes = [System.IO.File]::ReadAllBytes('C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN\edx300.exe')
$ascii = [System.Text.Encoding]::ASCII.GetString($bytes)

Write-Host "=== Search for CNF / BTRV / SQL / TABLES in edx300.exe ==="
$patterns = @(
    'TYPECONF[A-Za-z0-9_\.]*',
    'MACHCONF[A-Za-z0-9_\.]*',
    'SECOM[A-Za-z0-9_\.]*',
    '[A-Za-z0-9_]{3,20}\.btd',
    '[A-Za-z0-9_]{3,20}\.cnf',
    'program_components',
    'steps',
    'step_functions',
    'typeconf',
    'functions',
    'DEF_TC'
)

foreach ($pat in $patterns) {
    $matches = [System.Text.RegularExpressions.Regex]::Matches($ascii, $pat, 'IgnoreCase')
    $unique = $matches | Select-Object -ExpandProperty Value -Unique
    if ($unique) {
        Write-Host "Matches for $pat :"
        $unique | ForEach-Object { Write-Host "   $_" }
    }
}
