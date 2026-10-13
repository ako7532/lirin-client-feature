param([switch]$LoaderOnly, [switch]$WindowOnly, [switch]$FeatureOnly)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$vcvars = 'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat'
if (-not (Test-Path -LiteralPath $vcvars)) { throw "Visual Studio x64 build tools not found: $vcvars" }
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
