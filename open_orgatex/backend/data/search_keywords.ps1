$bin = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN"
$files = Get-ChildItem -Path $bin -Include *.dll,*.exe -Recurse

Write-Host "Total binaries to inspect: $($files.Count)"

$ftpFiles = @()
$planFiles = @()

foreach ($file in $files) {
    try {
        $bytes = [System.IO.File]::ReadAllBytes($file.FullName)
        $text = [System.Text.Encoding]::ASCII.GetString($bytes)
        
        if ($text -match "(?i)\bftp\b|ftps|sftp|ftpclient|ftpserver") {
            $ftpFiles += $file.Name
        }
        if ($text -match "(?i)\bplanning\b|batchplan|productionplan") {
            $planFiles += $file.Name
        }
    } catch {}
}

Write-Host "`n=== Files mentioning FTP ==="
$ftpFiles | Select-Object -Unique | ForEach-Object { Write-Host " - $_" }

Write-Host "`n=== Files mentioning Planning ==="
$planFiles | Select-Object -Unique | ForEach-Object { Write-Host " - $_" }
