$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = 'C:\Users\andrej-pc\AppData\Local\Programs\Python\Python311\python.exe'
$targets = @(Get-Process Lirin -ErrorAction Stop | Where-Object { $_.MainWindowTitle -eq 'Lirin' })
if ($targets.Count -ne 1) {
    throw "Expected one visible Lirin game window; found $($targets.Count)."
}
$gamePid = $targets[0].Id
$status = Join-Path $here 'python_window_loader.status.txt'
$inventory = Join-Path $here 'python_symbols_v5.txt'
$errorReport = Join-Path $here 'python_probe_v5.error.txt'
$oldLineCount = if (Test-Path -LiteralPath $status) { @(Get-Content -LiteralPath $status).Count } else { 0 }
$oldInventoryTime = if (Test-Path -LiteralPath $inventory) { (Get-Item -LiteralPath $inventory).LastWriteTimeUtc } else { $null }

Write-Host "Inventorying selected Python module symbols in visible Lirin PID $gamePid"
& $python (Join-Path $here 'inject.py') $gamePid --dll (Join-Path $here 'python_window_loader_v5.dll')
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

if (Test-Path -LiteralPath $inventory) {
    $info = Get-Item -LiteralPath $inventory
    if ($oldInventoryTime -and $info.LastWriteTimeUtc -le $oldInventoryTime) {
        Write-Host 'Symbol inventory exists but was not updated by this attempt.'
    } else {
        try {
            $rows = @(Get-Content -LiteralPath $inventory -ErrorAction Stop)
            Write-Host "Symbol inventory: $($rows.Count - 1) symbols, $($info.Length) bytes"
            Write-Host "Saved to: $inventory"
            $records = @($rows | ConvertFrom-Csv -Delimiter "`t")
            $records | Group-Object module | ForEach-Object { Write-Host "$($_.Name): $($_.Count) symbols" }
        } catch {
            Write-Host "Could not read symbol inventory: $($_.Exception.Message)"
        }
    }
} else {
    Write-Host 'Symbol inventory file not present.'
}

if (Test-Path -LiteralPath $errorReport) {
    Write-Host 'Python exception report:'
    Get-Content -LiteralPath $errorReport
}


