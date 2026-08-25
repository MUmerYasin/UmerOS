@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1
cd /d "F:\Pension Person Details\UmerOS\boot\python_vm\build"
echo --- Test: print(2) via -c flag ---
echo print(2) | umeros_python.exe -c 2>&1
echo --- Test: print(2) via file ---
echo. > "F:\Pension Person Details\UmerOS\boot\python_vm\test_run\test2.py"
echo print(2) > "F:\Pension Person Details\UmerOS\boot\python_vm\test_run\test2.py"
umeros_python.exe "F:\Pension Person Details\UmerOS\boot\python_vm\test_run\test2.py" 2>&1
