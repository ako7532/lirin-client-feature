param([switch]$LoaderOnly, [switch]$WindowOnly, [switch]$FeatureOnly)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# Locate vcvars64.bat, preferring vswhere (works on GitHub's windows-latest
# runner) and falling back to common install paths.
$vcvars = $null
$vswhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
if (Test-Path -LiteralPath $vswhere) {
    $installPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null
    if ($installPath) {
        $candidate = Join-Path $installPath 'VC\Auxiliary\Build\vcvars64.bat'
        if (Test-Path -LiteralPath $candidate) { $vcvars = $candidate }
    }
}
if (-not $vcvars) {
    foreach ($candidate in @(
        'C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat',
        'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat',
        'C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat',
        'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat'
    )) {
        if (Test-Path -LiteralPath $candidate) { $vcvars = $candidate; break }
    }
}
if (-not $vcvars) { throw "Visual Studio x64 build tools not found (vcvars64.bat)" }
if (-not $LoaderOnly -and -not $WindowOnly -and -not $FeatureOnly) {
    $command = 'call "' + $vcvars + '" >nul && cl /nologo /LD /W4 /EHsc /Fo"' + $here + '\load_probe.obj" /Fe"' + $here + '\load_probe.dll" "' + $here + '\load_probe.cpp" user32.lib'
    & cmd.exe /d /c $command
    if ($LASTEXITCODE -ne 0) { throw "C++ build failed with exit code $LASTEXITCODE" }
}
if (-not $WindowOnly -and -not $FeatureOnly) {
    $command = 'call "' + $vcvars + '" >nul && cl /nologo /LD /W4 /EHsc /Fo"' + $here + '\python_loader.obj" /Fe"' + $here + '\python_loader.dll" "' + $here + '\python_loader.cpp"'
    & cmd.exe /d /c $command
    if ($LASTEXITCODE -ne 0) { throw "Python loader build failed with exit code $LASTEXITCODE" }
}
if (-not $FeatureOnly) {
    $command = 'call "' + $vcvars + '" >nul && cl /nologo /LD /W4 /EHsc /DUSE_WINDOW_HOOK /Fo"' + $here + '\python_window_loader.obj" /Fe"' + $here + '\python_window_loader.dll" "' + $here + '\python_loader.cpp" user32.lib'
    & cmd.exe /d /c $command
    if ($LASTEXITCODE -ne 0) { throw "Python window loader build failed with exit code $LASTEXITCODE" }
}
if (-not $LoaderOnly -and -not $WindowOnly) {
    $command = 'call "' + $vcvars + '" >nul && cl /nologo /LD /W4 /EHsc /DUSE_WINDOW_HOOK /DUSE_FEATURE_SCRIPT /Fo"' + $here + '\client_feature_loader.obj" /Fe"' + $here + '\client_feature_loader.dll" "' + $here + '\python_loader.cpp" user32.lib'
    & cmd.exe /d /c $command
    if ($LASTEXITCODE -ne 0) { throw "Client feature loader build failed with exit code $LASTEXITCODE" }
}
