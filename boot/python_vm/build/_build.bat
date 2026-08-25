@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1
cd /d "F:\Pension Person Details\UmerOS\boot\python_vm\build"
"C:\Users\MC Raja Jang\AppData\Roaming\Python\Python314\Scripts\ninja.exe" 2>&1
echo BUILD_EXIT=%ERRORLEVEL%
