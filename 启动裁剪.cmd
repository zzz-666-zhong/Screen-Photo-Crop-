@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist "%~dp0.crop-env\Scripts\python.exe" (
  echo 请先按使用说明安装独立环境 .crop-env。
  pause
  exit /b 2
)
"%~dp0.crop-env\Scripts\python.exe" "%~dp0screen_crop.py" %*
set "crop_exit=%errorlevel%"
if not "%crop_exit%"=="0" pause
exit /b %crop_exit%
