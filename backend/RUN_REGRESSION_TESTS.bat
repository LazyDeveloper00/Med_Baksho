@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=py"
)

echo ==============================================
echo MediBaksho regression test suite
echo ==============================================

echo.
echo [1/2] Django system check...
%PY% manage.py check
if errorlevel 1 goto :fail

echo.
echo [2/2] Regression tests...
%PY% -m unittest discover -s tests -v
if errorlevel 1 goto :fail

echo.
echo ALL REGRESSION TESTS PASSED.
exit /b 0

:fail
echo.
echo REGRESSION TESTING FAILED. See the errors above.
exit /b 1
