@echo off
cd /d "UmerOS"
python diagnose.py > diagnose_output.txt 2>&1
echo EXIT_CODE=%ERRORLEVEL% >> diagnose_output.txt
