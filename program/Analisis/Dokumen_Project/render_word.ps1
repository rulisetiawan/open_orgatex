$ErrorActionPreference = 'Stop'
$inputPath = 'C:\Users\Lenovo Yoga 7i\Documents\PT.SMM\DIGITAL AUTOMATION DEPARTEMENT\DOKUMENTASI DAN NOTE\Dokumentasi\Internal Dokumen\Pengajuan_Project_Digitalisasi_Dan_Otomatisasi_PT_SMM_Ringkas.docx'
$outputPdf = 'D:\File HMI\Analisis\Dokumen_Project\render\proposal.pdf'
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($inputPath, $false, $true, $false)
    $document.Repaginate()
    Write-Output ('Pages: ' + $document.ComputeStatistics(2))
    $document.ExportAsFixedFormat($outputPdf, 17)
    Write-Output $outputPdf
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
