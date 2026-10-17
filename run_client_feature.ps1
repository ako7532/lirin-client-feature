param([int]$TargetPid = 0, [switch]$RecorderPairExperiment)

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
$manualQueueModule = Join-Path $here 'manual_queue_logging.py'

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
$manualQueueMetadata = Join-Path $runtimeDir 'manual_queue_runtime_metadata.json'
$recorderPairMode = Join-Path $runtimeDir 'hunter_recorder_pair.mode.txt'

if (-not (Test-Path -LiteralPath $script)) { throw "Feature script missing: $script" }
if (-not (Test-Path -LiteralPath $loader)) { throw "Feature loader missing. Run build.ps1 -FeatureOnly first." }
if (-not (Test-Path -LiteralPath $manualQueueModule)) { throw "Manual queue logger missing: $manualQueueModule" }

# Stage this checkout's feature (and its optional trained model) into the
# branch runtime directory so the injected copy is exactly this branch's code.
Copy-Item -LiteralPath $script -Destination (Join-Path $runtimeDir 'client_feature.py') -Force
Copy-Item -LiteralPath $manualQueueModule -Destination (Join-Path $runtimeDir 'manual_queue_logging.py') -Force
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

# The opt-in native writer is tied to this exact executable, not only PE metadata.
if ($RecorderPairExperiment) {
    if (-not $selected[0].Path) { throw 'Cannot verify Lirin EXE path/hash for recorder-pair experiment.' }
    $actualGameHash = (Get-FileHash -LiteralPath $selected[0].Path -Algorithm SHA256).Hash
    if ($actualGameHash -ne '8B6F5EA90AE62F4FB54752B187897D60962AD80FF71BFC0A7BF277D5A52A75A0') {
        throw 'Lirin EXE SHA-256 mismatch; recorder-pair experiment not injected.'
    }
}

# Explicit test-only opt-in, read once by the feature. No recorder settings change.
$pairMode = if ($RecorderPairExperiment) { 'on' } else { 'off' }
[System.IO.File]::WriteAllText($recorderPairMode, $pairMode, [System.Text.Encoding]::ASCII)
Write-Host "Native recorder-pair experiment: $pairMode (not a physical click)"

$oldLineCount = if (Test-Path -LiteralPath $status) { @(Get-Content -LiteralPath $status).Count } else { 0 }
$uniqueDll = Join-Path $runtimeDir ("client_feature_run_{0}.dll" -f [guid]::NewGuid().ToString('N'))
Copy-Item -LiteralPath $loader -Destination $uniqueDll
$previousActive = if (Test-Path -LiteralPath $active) { [System.IO.File]::ReadAllText($active) } else { $null }
[System.IO.File]::WriteAllText($active, [System.IO.Path]::GetFileName($uniqueDll), [System.Text.Encoding]::ASCII)

# Capture reproducible run identity before injection. The in-game logger reads
# this file only; it never invokes Git or a subprocess from the game thread.
$gitHead = (& git -C $here rev-parse HEAD 2>$null | Select-Object -First 1)
$gitStatus = @(& git -C $here status --porcelain=v1 --untracked-files=all 2>$null)
$gitStatusText = ($gitStatus -join "`n")
$sha256 = [System.Security.Cryptography.SHA256]::Create()
try {
    $statusBytes = [System.Text.Encoding]::UTF8.GetBytes($gitStatusText)
    $statusHash = ([System.BitConverter]::ToString($sha256.ComputeHash($statusBytes))).Replace('-', '').ToLowerInvariant()
} finally {
    $sha256.Dispose()
}
$metadata = [ordered]@{
    captured_utc = [DateTime]::UtcNow.ToString('o')
    git_head = if ($gitHead) { $gitHead.Trim() } else { $null }
    git_dirty = ($gitStatus.Count -gt 0)
    git_status_sha256 = $statusHash
    git_status_entry_count = $gitStatus.Count
    branch = $branch
    recorder_pair_experiment = [bool]$RecorderPairExperiment
    executable_path = $selected[0].Path
    executable_sha256 = if ($selected[0].Path) { (Get-FileHash -LiteralPath $selected[0].Path -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    repository_python_sha256 = (Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
    staged_python_sha256 = (Get-FileHash -LiteralPath (Join-Path $runtimeDir 'client_feature.py') -Algorithm SHA256).Hash.ToLowerInvariant()
    repository_dll_sha256 = (Get-FileHash -LiteralPath $loader -Algorithm SHA256).Hash.ToLowerInvariant()
    staged_dll_sha256 = (Get-FileHash -LiteralPath $uniqueDll -Algorithm SHA256).Hash.ToLowerInvariant()
    staged_dll_name = [System.IO.Path]::GetFileName($uniqueDll)
}
$metadataJson = $metadata | ConvertTo-Json -Depth 3
[System.IO.File]::WriteAllText($manualQueueMetadata, $metadataJson, (New-Object System.Text.UTF8Encoding($false)))
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
