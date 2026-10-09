@echo off
chcp 65001 >nul
call "%~dp0启动裁剪.cmd" --setup-only
if errorlevel 1 exit /b %errorlevel%
echo 环境安装完成，可以双击“启动裁剪.cmd”使用。
echo Setup complete. Double-click the crop launcher to begin.
pause
