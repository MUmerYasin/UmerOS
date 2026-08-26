# Build script for UmerOS Python VM
$ErrorActionPreference = "Stop"

$buildDir = "F:\Pension Person Details\UmerOS\boot\python_vm\build"
$vcvarsall = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"

# Write the CMD build script
$cmdScript = @"
@echo off
call "$vcvarsall" x64
cd /d "$buildDir"
echo === CMAKE ===
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=Debug
if errorlevel 1 (
    echo CMAKE FAILED
    exit /b 1
)
echo === NINJA ===
ninja -j4
if errorlevel 1 (
    echo NINJA FAILED
    exit /b 1
)
echo === BUILD SUCCESS ===
"@

$batPath = Join-Path $buildDir "run_build.bat"
$cmdScript | Set-Content -Path $batPath -Encoding ASCII -Force

Write-Host "Running build..."
$proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$batPath`"" -Wait -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $buildDir "build_out.txt") -RedirectStandardError (Join-Path $buildDir "build_err.txt")
Write-Host "Exit code: $($proc.ExitCode)"

$outFile = Join-Path $buildDir "build_out.txt"
$errFile = Join-Path $buildDir "build_err.txt"
Write-Host "=== STDOUT ==="
Get-Content $outFile -ErrorAction SilentlyContinue
Write-Host "=== STDERR ==="
Get-Content $errFile -ErrorAction SilentlyContinue
