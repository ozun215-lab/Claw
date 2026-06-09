param([string]$Folder, [int]$Top = 20, [datetime]$Start = "2020-01-01", [datetime]$End = "2021-04-01")

Add-Type -AssemblyName System.Drawing
$ErrorActionPreference = 'SilentlyContinue'

$files = Get-ChildItem -Path $Folder -File -Recurse -Include *.jpg,*.jpeg,*.JPG,*.JPEG | Where-Object { $_.LastWriteTime -ge $Start -and $_.LastWriteTime -le $End -and $_.Length -gt 200000 }
Write-Host "Scanning $($files.Count) files..."

$results = New-Object System.Collections.ArrayList
$cnt = 0
foreach ($f in $files) {
    $cnt++
    if ($cnt % 100 -eq 0) { Write-Host "  $cnt / $($files.Count)" }
    try {
        $img = [System.Drawing.Image]::FromFile($f.FullName)
        $thumb = New-Object System.Drawing.Bitmap 48, 48
        $g = [System.Drawing.Graphics]::FromImage($thumb)
        $g.DrawImage($img, 0, 0, 48, 48)
        $g.Dispose()
        $img.Dispose()

        $whiteCount = 0
        $total = 48 * 48
        for ($y = 0; $y -lt 48; $y++) {
            for ($x = 0; $x -lt 48; $x++) {
                $p = $thumb.GetPixel($x, $y)
                if ($p.R -gt 175 -and $p.G -gt 175 -and $p.B -gt 175 -and [math]::Abs($p.R - $p.G) -lt 25 -and [math]::Abs($p.G - $p.B) -lt 25) {
                    $whiteCount++
                }
            }
        }
        $thumb.Dispose()
        $ratio = [math]::Round($whiteCount / $total, 3)
        if ($ratio -gt 0.35) {
            $null = $results.Add([PSCustomObject]@{ File = $f.FullName; WhiteRatio = $ratio; KB = [math]::Round($f.Length/1024,0); Date = $f.LastWriteTime.ToString("yyyy-MM-dd") })
        }
    } catch { }
}

Write-Host "`nTop $Top files by white-background ratio:`n"
$results | Sort-Object WhiteRatio -Descending | Select-Object -First $Top | Format-Table -AutoSize -Wrap
