@echo off
echo Starting Vyne Dental Mock Frontend on http://localhost:5174
cd /d "%~dp0"
if not exist node_modules call npm install
call npm run dev
pause
