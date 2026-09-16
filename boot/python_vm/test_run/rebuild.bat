@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1
cd /d "UmerOS\boot\python_vm\build"
cmake -G Ninja -DCMAKE_BUILD_TYPE=Debug "UmerOS\boot\python_vm"
ninja -j1
echo BUILD_EXIT=%ERRORLEVEL%
