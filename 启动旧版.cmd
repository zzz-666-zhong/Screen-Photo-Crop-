@echo off
chcp 65001 >nul
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"
if exist "%~dp0.crop-env\Scripts\python.exe" (
  "%~dp0.crop-env\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
  if not errorlevel 1 goto local_python
)
if exist "%~dp0..\.crop-env\Scripts\python.exe" (
  "%~dp0..\.crop-env\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
  if not errorlevel 1 goto parent_python
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 goto system_python
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 goto python_launcher
echo 未找到 Python 3.10 或更新版本。请先安装 Python，再重新双击本文件。
echo Python 3.10+ was not found. Install Python and run this launcher again.
pause
exit /b 2

:local_python
"%~dp0.crop-env\Scripts\python.exe" "%~dp0launch_crop.py" %*
goto finished
:parent_python
"%~dp0..\.crop-env\Scripts\python.exe" "%~dp0launch_crop.py" %*
goto finished
:system_python
python "%~dp0launch_crop.py" %*
goto finished
:python_launcher
py -3 "%~dp0launch_crop.py" %*
:finished
set "crop_exit=%errorlevel%"
if not "%crop_exit%"=="0" pause
exit /b %crop_exit%
