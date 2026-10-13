param([int]$TargetPid = 0)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = 'C:\Users\andrej-pc\AppData\Local\Programs\Python\Python311\python.exe'
$targets = @(Get-Process Lirin -ErrorAction Stop)
if ($TargetPid -gt 0) {
    $matches = @($targets | Where-Object { $_.Id -eq $TargetPid })
    if ($matches.Count -ne 1) { throw "Lirin PID $TargetPid was not found." }
    $gamePid = $TargetPid
} else {
    $visible = @($targets | Where-Object { $_.MainWindowTitle -eq 'Lirin' })
    if ($visible.Count -eq 1) {
        $gamePid = $visible[0].Id
    } elseif ($targets.Count -eq 1) {
        $gamePid = $targets[0].Id
    } else {
        throw 'Could not select one Lirin process. Pass its PID with -TargetPid.'
    }
}

$status = Join-Path $here 'python_window_loader.status.txt'
$report = Join-Path $here 'python_ingame_v6.txt'
$errorReport = Join-Path $here 'python_probe_v6.error.txt'
$oldLineCount = if (Test-Path -LiteralPath $status) { @(Get-Content -LiteralPath $status).Count } else { 0 }
$oldReportTime = if (Test-Path -LiteralPath $report) { (Get-Item -LiteralPath $report).LastWriteTimeUtc } else { $null }

Write-Host "Running read-only in-game Python test in Lirin PID $gamePid"
& $python (Join-Path $here 'inject.py') $gamePid --dll (Join-Path $here 'python_window_loader_v6.dll')
if ($LASTEXITCODE -ne 0) { throw "Injector failed with exit code $LASTEXITCODE" }

$lines = @()
for ($i = 0; $i -lt 50; $i++) {
    if (Test-Path -LiteralPath $status) {
        $lines = @(Get-Content -LiteralPath $status | Select-Object -Skip $oldLineCount | Where-Object { $_ -match "^PID ${gamePid}:" })
        if ($lines.Count -gt 0 -and $lines[-1] -match 'released|failed|skipped|missing') { break }
    }
    Start-Sleep -Milliseconds 200
}
if ($lines.Count -gt 0) { $lines | ForEach-Object { Write-Host $_ } }
else { Write-Host 'No new status lines for this PID.' }

if (Test-Path -LiteralPath $report) {
    $info = Get-Item -LiteralPath $report
    if ($oldReportTime -and $info.LastWriteTimeUtc -le $oldReportTime) {
        Write-Host 'Report exists but was not updated by this attempt.'
    } else {
        try {
            Write-Host "In-game report ($($info.Length) bytes):"
            Get-Content -LiteralPath $report -ErrorAction Stop | Select-Object -First 4
            Write-Host "Saved to: $report"
        } catch { Write-Host "Could not read report: $($_.Exception.Message)" }
    }
} else { Write-Host 'In-game report file not present.' }

if (Test-Path -LiteralPath $errorReport) {
    Write-Host 'Python exception report:'
    Get-Content -LiteralPath $errorReport
}
$target = Get-Process -Id $gamePid -ErrorAction SilentlyContinue
if ($target) { Write-Host "Lirin PID $gamePid remains running (Responding: $($target.Responding))." }
else { Write-Host "Lirin PID $gamePid is no longer running." }
