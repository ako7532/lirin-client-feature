param([int]$TargetPid = 0)

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$python = 'C:\Users\andrej-pc\AppData\Local\Programs\Python\Python311\python.exe'

# --- Per-branch runtime directory -------------------------------------------
# The injected loader resolves every file it touches (client_feature.py, the
# active-DLL marker, the entity snapshot, and the status log) relative to the
# injected DLL's own directory, and the Python feature derives its config/log/
# history paths from the script's directory.  Staging each branch into its own
# directory therefore keeps multiple branches' build artifacts and runtime
# state from colliding when working on several branches at once.
$loader = Join-Path $here 'client_feature_loader.dll'
$script = Join-Path $here 'client_feature.py'

$branch = 'unknown'
try {
    $gitOut = & git -C $here rev-parse --abbrev-ref HEAD 2>$null
    if ($LASTEXITCODE -eq 0 -and $gitOut) {
        $branch = ($gitOut | Select-Object -First 1)
    }
} catch { }
# Branch names may contain '/' (e.g. feature/foo); flatten them to a single
# safe directory segment.
$branch = [regex]::Replace($branch.Trim(), '[^A-Za-z0-9._-]', '-')
if (-not $branch) { $branch = 'detached' }

$runtimeDir = Join-Path $here ('.runtime\{0}' -f $branch)
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$status = Join-Path $runtimeDir 'python_window_loader.status.txt'
$active = Join-Path $runtimeDir 'client_feature_active.txt'
$featureLog = Join-Path $runtimeDir 'metin_scanner.log'

if (-not (Test-Path -LiteralPath $script)) { throw "Feature script missing: $script" }
if (-not (Test-Path -LiteralPath $loader)) { throw "Feature loader missing. Run build.ps1 -FeatureOnly first." }

# Stage this checkout's feature (and its optional trained model) into the
# branch runtime directory so the injected copy is exactly this branch's code.
Copy-Item -LiteralPath $script -Destination (Join-Path $runtimeDir 'client_feature.py') -Force
$model = Join-Path $here 'yin_yang_duel_model.json'
if (Test-Path -LiteralPath $model) {
    Copy-Item -LiteralPath $model -Destination (Join-Path $runtimeDir 'yin_yang_duel_model.json') -Force
}
# Seed the branch config from the repository copy the first time only, so a
# previously saved radius/anchor is not silently lost.
$runtimeConfig = Join-Path $runtimeDir 'client_feature_config.txt'
$repoConfig = Join-Path $here 'client_feature_config.txt'
if (-not (Test-Path -LiteralPath $runtimeConfig) -and (Test-Path -LiteralPath $repoConfig)) {
    Copy-Item -LiteralPath $repoConfig -Destination $runtimeConfig
}

$targets = @(Get-Process Lirin -ErrorAction Stop)
if ($TargetPid -gt 0) {
    $selected = @($targets | Where-Object { $_.Id -eq $TargetPid })
} else {
    $selected = @($targets | Where-Object { $_.MainWindowTitle -eq 'Lirin' })
    if ($selected.Count -eq 0 -and $targets.Count -eq 1) { $selected = $targets }
}
if ($selected.Count -ne 1) { throw 'Could not select one Lirin process. Pass -TargetPid <pid>.' }
$gamePid = $selected[0].Id

$oldLineCount = if (Test-Path -LiteralPath $status) { @(Get-Content -LiteralPath $status).Count } else { 0 }
$uniqueDll = Join-Path $runtimeDir ("client_feature_run_{0}.dll" -f [guid]::NewGuid().ToString('N'))
Copy-Item -LiteralPath $loader -Destination $uniqueDll
$previousActive = if (Test-Path -LiteralPath $active) { [System.IO.File]::ReadAllText($active) } else { $null }
[System.IO.File]::WriteAllText($active, [System.IO.Path]::GetFileName($uniqueDll), [System.Text.Encoding]::ASCII)
Write-Host "Loading client feature (branch '$branch') in Lirin PID $gamePid"
try {
    & $python (Join-Path $here 'inject.py') $gamePid --dll $uniqueDll
    if ($LASTEXITCODE -ne 0) { throw "Injector failed with exit code $LASTEXITCODE" }
} catch {
    if ($null -eq $previousActive) { Remove-Item -LiteralPath $active -ErrorAction SilentlyContinue }
    else { [System.IO.File]::WriteAllText($active, $previousActive, [System.Text.Encoding]::ASCII) }
    throw
}

$lines = @()
for ($i = 0; $i -lt 50; $i++) {
    if (Test-Path -LiteralPath $status) {
        $lines = @(Get-Content -LiteralPath $status | Select-Object -Skip $oldLineCount | Where-Object { $_ -match "^PID ${gamePid}:" })
        if ($lines.Count -gt 0 -and $lines[-1] -match 'released|failed|skipped|missing|mismatch') { break }
    }
    Start-Sleep -Milliseconds 200
}
$lines | ForEach-Object { Write-Host $_ }
if (-not ($lines | Where-Object { $_ -match 'Python script returned successfully' })) {
    throw 'Feature script did not report success. Check the status above and the game log.'
}
if (Test-Path -LiteralPath $featureLog) {
    Write-Host "Feature log: $featureLog"
    Get-Content -LiteralPath $featureLog -Tail 4 | ForEach-Object { Write-Host $_ }
}
$target = Get-Process -Id $gamePid -ErrorAction SilentlyContinue
if ($target) { Write-Host "Lirin PID $gamePid remains running (Responding: $($target.Responding))." }
else { Write-Host "Lirin PID $gamePid is no longer running." }
