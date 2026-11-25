@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "crop_app=%~dp0desktop\artifacts\win-x64\ScreenCrop.exe"
if exist "%crop_app%" goto launch
where dotnet >nul 2>&1
if errorlevel 1 (
  echo 首次构建需要 .NET 10 SDK。安装地址：https://dotnet.microsoft.com/download/dotnet/10.0
  echo 后续使用已构建的版本无需 Python 或模型文件。
  pause
  exit /b 2
)
echo 正在构建原生裁剪工作台，首次需要联网下载依赖...
dotnet publish "%~dp0desktop\Crop.Desktop\Crop.Desktop.csproj" -c Release -r win-x64 --self-contained true -o "%~dp0desktop\artifacts\win-x64" --nologo
if errorlevel 1 (
  echo 构建失败，请查看上方信息。
  pause
  exit /b 1
)
:launch
start "" "%crop_app%" %*
exit /b 0
