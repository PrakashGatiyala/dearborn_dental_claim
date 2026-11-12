@echo off
REM ===========================================================================
REM  Starts all three systems in the COB claim chain, each in its own window.
REM
REM    VYNE (:8001/:5174)  ->  AS/400 (:8002/:5175)  ->  DEARBORN (:8000/:5173)
REM ===========================================================================
cd /d "%~dp0"

echo Generating COB claim dataset...
python cob_edi_generator.py --count 12

echo Seeding members, plans and primary EOBs so the agent can resolve them...
python seed_cob_claims.py

echo.
echo Starting backends and front ends...

start "DEARBORN backend  :8000" cmd /k "cd /d %~dp0backend && uvicorn main:app --port 8000 --reload"
start "VYNE backend      :8001" cmd /k "cd /d %~dp0vyne_mock\backend && start_backend.bat"
start "AS400 backend     :8002" cmd /k "cd /d %~dp0as400\backend && start_backend.bat"

timeout /t 5 /nobreak >nul

start "DEARBORN portal   :5173" cmd /k "cd /d %~dp0frontend && npm run dev"
start "VYNE portal       :5174" cmd /k "cd /d %~dp0vyne_mock\frontend && start_frontend.bat"
start "AS400 green screen:5175" cmd /k "cd /d %~dp0as400\frontend && start_frontend.bat"

echo.
echo   Vyne clearinghouse : http://localhost:5174
echo   HCSC AS/400        : http://localhost:5175   (OPER01 / DEMO123)
echo   Agent workbench    : http://localhost:5173
echo.
echo Once all six windows are up, send claims with:
echo     python vyne_sender.py --interval 30
echo.
pause
