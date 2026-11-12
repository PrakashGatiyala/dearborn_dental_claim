@echo off
echo Starting Vyne Dental Mock Backend on http://localhost:8001
cd /d "%~dp0"
pip install -r requirements.txt -q
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
pause
