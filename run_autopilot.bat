@echo off
cd /d "%~dp0"
set "PYTHON_EXE=C:\Users\MAYANK SINGH\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" auto_quota_uploader.py %*
) else (
    py auto_quota_uploader.py %*
)
