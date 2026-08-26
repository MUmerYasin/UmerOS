@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64
cd /d "F:\Pension Person Details\UmerOS\boot\python_vm\build"
echo === CMAKE ===
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=Debug 2>&1
if errorlevel 1 (
    echo CMAKE FAILED
    exit /b 1
)
echo === NINJA ===
ninja -j4 2>&1
if errorlevel 1 (
    echo NINJA FAILED
    exit /b 1
)
echo === BUILD SUCCESS ===
