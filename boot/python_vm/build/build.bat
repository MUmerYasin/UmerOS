@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1
cd /d "F:\Pension Person Details\UmerOS\boot\python_vm\build"
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=Debug 2>&1
if errorlevel 1 (
    echo CMAKE FAILED
    exit /b 1
)
ninja -j4 2>&1
if errorlevel 1 (
    echo NINJA FAILED
    exit /b 1
)
echo BUILD SUCCESS
