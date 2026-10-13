$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = 'C:\Users\andrej-pc\AppData\Local\Programs\Python\Python311\python.exe'
$targets = @(Get-Process Lirin -ErrorAction Stop | Where-Object { $_.MainWindowTitle -eq 'Lirin' })
if ($targets.Count -ne 1) {
    throw "Expected one visible Lirin game window; found $($targets.Count)."
}
$gamePid = $targets[0].Id
Write-Host "Injecting Python test DLL into visible Lirin PID $gamePid"
& $python (Join-Path $here 'inject.py') $gamePid --dll (Join-Path $here 'python_loader.dll')
if ($LASTEXITCODE -ne 0) { throw "Injector failed with exit code $LASTEXITCODE" }

$status = Join-Path $here 'python_loader.status.txt'
for ($i = 0; $i -lt 50; $i++) {
    if (Test-Path -LiteralPath $status) {
        $lines = @(Get-Content -LiteralPath $status | Where-Object { $_ -match "^PID ${gamePid}:" })
        if ($lines.Count -gt 0 -and $lines[-1] -match 'released|failed|skipped|missing') { break }
    }
    Start-Sleep -Milliseconds 200
}
if (Test-Path -LiteralPath $status) {
    Get-Content -LiteralPath $status | Where-Object { $_ -match "^PID ${gamePid}:" }
}
$marker = Join-Path $here 'python_probe.loaded.txt'
if (Test-Path -LiteralPath $marker) {
    Write-Host 'Python probe output:'
    Get-Content -LiteralPath $marker
} else {
    Write-Host 'Python probe output file not present.'
}
