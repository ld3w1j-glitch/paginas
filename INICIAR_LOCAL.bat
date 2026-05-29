@echo off
cd /d "%~dp0"
if not exist venv (
  py -m venv venv
)
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
start http://127.0.0.1:5000
venv\Scripts\python.exe run.py
pause
