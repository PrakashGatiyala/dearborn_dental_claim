@echo off
echo Starting HCSC AS/400 green screen on http://localhost:5175
cd /d "%~dp0"
if not exist node_modules call npm install
call npm approve-scripts --allow-scripts-pending 2>nul
call npm run dev
pause
