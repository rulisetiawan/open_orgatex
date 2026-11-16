$bin = "C:\Users\ruli_smm\New folder\tes\OrgaTEX\BIN"
$files = Get-ChildItem -Path $bin -File

Write-Host "Searching for STATUS.ACT and STATUS path references in top-level files ($($files.Count) files)..."

$matches = @()

foreach ($file in $files) {
    try {
        $bytes = [System.IO.File]::ReadAllBytes($file.FullName)
        $text = [System.Text.Encoding]::ASCII.GetString($bytes)
        
        if ($text -match "(?i)STATUS\.ACT") {
            Write-Host "Found STATUS.ACT in: $($file.Name)"
            $matches += $file.FullName
        }
    } catch {}
}

Write-Host "`nTotal matching files: $($matches.Count)"
