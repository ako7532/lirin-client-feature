$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = 'C:\Users\andrej-pc\AppData\Local\Programs\Python\Python311\python.exe'
$targets = @(Get-Process Lirin -ErrorAction Stop | Where-Object { $_.MainWindowTitle -eq 'Lirin' })
if ($targets.Count -ne 1) {
    throw "Expected one visible Lirin game window; found $($targets.Count)."
}
$gamePid = $targets[0].Id
$status = Join-Path $here 'python_window_loader.status.txt'
$inventory = Join-Path $here 'python_modules_v3.tsv'
$oldLineCount = if (Test-Path -LiteralPath $status) { @(Get-Content -LiteralPath $status).Count } else { 0 }
$oldInventoryTime = if (Test-Path -LiteralPath $inventory) { (Get-Item -LiteralPath $inventory).LastWriteTimeUtc } else { $null }

Write-Host "Inventorying loaded Python modules in visible Lirin PID $gamePid"
& $python (Join-Path $here 'inject.py') $gamePid --dll (Join-Path $here 'python_window_loader_v3.dll')
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
        Write-Host 'Module inventory exists but was not updated by this attempt.'
    } else {
        try {
            $rows = @(Get-Content -LiteralPath $inventory -ErrorAction Stop)
            Write-Host "Module inventory: $($rows.Count - 1) modules, $($info.Length) bytes"
            Write-Host "Saved to: $inventory"
            $rows | Select-Object -First 16
        } catch {
            Write-Host "Could not read module inventory: $($_.Exception.Message)"
        }
    }
} else {
    Write-Host 'Module inventory file not present.'
}
