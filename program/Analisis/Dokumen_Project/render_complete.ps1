$ErrorActionPreference = 'Stop'
$inputPath = 'C:\Users\Lenovo Yoga 7i\Documents\PT.SMM\DIGITAL AUTOMATION DEPARTEMENT\DOKUMENTASI DAN NOTE\Dokumentasi\Internal Dokumen\Pengajuan_Project_Digitalisasi_Dan_Otomatisasi_PT_SMM_Dilengkapi.docx'
$renderFolder = 'D:\File HMI\Analisis\Dokumen_Project\render_lengkap'
New-Item -ItemType Directory -Path $renderFolder -Force | Out-Null
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($inputPath, $false, $true, $false)
    $document.Repaginate()
    [void]$document.Fields.Update()
    $document.Repaginate()
    [void]$document.Fields.Update()
    foreach ($section in $document.Sections) {
        foreach ($footer in $section.Footers) { [void]$footer.Range.Fields.Update() }
    }
    $pages = [ordered]@{}
    for ($index = 0; $index -lt 14; $index++) {
        $bookmark = $document.Bookmarks.Item('scope_section_' + $index)
        $pages['scope_section_' + $index] = $bookmark.Range.Information(3)
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($bookmark)
    }
    $pages | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $renderFolder 'heading_pages.json') -Encoding utf8
    Write-Output ('Pages: ' + $document.ComputeStatistics(2))
    $document.ExportAsFixedFormat((Join-Path $renderFolder 'proposal.pdf'), 17)
}
finally {
    if ($null -ne $document) {
        $document.Close(0)
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
    }
    if ($null -ne $word) {
        $word.Quit(0)
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
    }
}
