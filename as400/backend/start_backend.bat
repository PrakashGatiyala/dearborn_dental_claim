@echo off
echo Starting HCSC AS/400 Claims Adjudication backend on http://localhost:8002
cd /d "%~dp0"
pip install -r requirements.txt -q
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
pause
