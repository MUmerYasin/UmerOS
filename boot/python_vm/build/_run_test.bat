@echo off
cd /d "F:\Pension Person Details\UmerOS\boot\python_vm\build"
"F:\Pension Person Details\UmerOS\boot\python_vm\build\umeros_python.exe" "F:\Pension Person Details\UmerOS\boot\python_vm\test_run\t2.py" 2>&1
echo EXIT_CODE=%ERRORLEVEL%
