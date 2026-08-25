@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1
cd /d "F:\Pension Person Details\UmerOS\boot\python_vm\build"
echo print(2) > "F:\Pension Person Details\UmerOS\boot\python_vm\test_run\t2.py"
umeros_python.exe "F:\Pension Person Details\UmerOS\boot\python_vm\test_run\t2.py" 2>&1
