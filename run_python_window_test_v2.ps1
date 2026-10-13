$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = 'C:\Users\andrej-pc\AppData\Local\Programs\Python\Python311\python.exe'
$targets = @(Get-Process Lirin -ErrorAction Stop | Where-Object { $_.MainWindowTitle -eq 'Lirin' })
if ($targets.Count -ne 1) {
    throw "Expected one visible Lirin game window; found $($targets.Count)."
}
$gamePid = $targets[0].Id
$status = Join-Path $here 'python_window_loader.status.txt'
$marker = Join-Path $here 'python_probe_v2.loaded.txt'
$oldLineCount = if (Test-Path -LiteralPath $status) { @(Get-Content -LiteralPath $status).Count } else { 0 }
$oldMarkerTime = if (Test-Path -LiteralPath $marker) { (Get-Item -LiteralPath $marker).LastWriteTimeUtc } else { $null }

Write-Host "Injecting fresh window-thread Python test DLL into visible Lirin PID $gamePid"
& $python (Join-Path $here 'inject.py') $gamePid --dll (Join-Path $here 'python_window_loader_v2.dll')
if ($LASTEXITCODE -ne 0) { throw "Injector failed with exit code $LASTEXITCODE" }

$lines = @()
for ($i = 0; $i -lt 50; $i++) {
    if (Test-Path -LiteralPath $status) {
        $lines = @(Get-Content -LiteralPath $status | Select-Object -Skip $oldLineCount | Where-Object { $_ -match "^PID ${gamePid}:" })
        if ($lines.Count -gt 0 -and $lines[-1] -match 'released|failed|skipped|missing') { break }
    }
    Start-Sleep -Milliseconds 200
}
if ($lines.Count -gt 0) {
    $lines | ForEach-Object { Write-Host $_ }
} else {
    Write-Host 'No new status lines for this PID.'
}

if (Test-Path -LiteralPath $marker) {
    $info = Get-Item -LiteralPath $marker
    if ($oldMarkerTime -and $info.LastWriteTimeUtc -le $oldMarkerTime) {
        Write-Host 'Probe output exists but was not updated by this attempt.'
    } else {
        Write-Host "Python probe output ($($info.Length) bytes):"
        if ($info.Length -gt 0) {
            try { Get-Content -LiteralPath $marker -ErrorAction Stop }
            catch { Write-Host "Could not read probe output: $($_.Exception.Message)" }
        }
    }
} else {
    Write-Host 'Python probe output file not present.'
}
