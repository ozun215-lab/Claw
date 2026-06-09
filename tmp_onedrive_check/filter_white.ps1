param([string]$Folder, [int]$Top = 10)

Add-Type -AssemblyName System.Drawing

$results = @()
$files = Get-ChildItem -Path $Folder -File -Include *.jpg,*.jpeg,*.png,*.JPG,*.JPEG,*.PNG -Recurse -ErrorAction SilentlyContinue

foreach ($f in $files) {
    try {
        $img = [System.Drawing.Image]::FromFile($f.FullName)
        # downscale: create a small thumbnail (100x100) to sample quickly
        $thumb = New-Object System.Drawing.Bitmap 80, 80
        $g = [System.Drawing.Graphics]::FromImage($thumb)
        $g.DrawImage($img, 0, 0, 80, 80)
        $g.Dispose()
        $img.Dispose()

        $whiteCount = 0
        $total = 80 * 80
        for ($y = 0; $y -lt 80; $y++) {
            for ($x = 0; $x -lt 80; $x++) {
                $p = $thumb.GetPixel($x, $y)
                # 흰 종이 = R/G/B all > 180 and close to each other
                if ($p.R -gt 180 -and $p.G -gt 180 -and $p.B -gt 180) {
                    $whiteCount++
                }
            }
        }
        $thumb.Dispose()
        $ratio = [math]::Round($whiteCount / $total, 3)
        $results += [PSCustomObject]@{ File = $f.FullName; WhiteRatio = $ratio; SizeKB = [math]::Round($f.Length/1024,0); Modified = $f.LastWriteTime }
    } catch {
        # skip
    }
}

$results | Sort-Object WhiteRatio -Descending | Select-Object -First $Top | Format-Table -AutoSize
