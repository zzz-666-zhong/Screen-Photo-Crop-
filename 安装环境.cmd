@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo 构建 C# / WPF 原生桌面应用，需要 .NET 10 SDK。
dotnet publish "%~dp0desktop\Crop.Desktop\Crop.Desktop.csproj" -c Release -r win-x64 --self-contained true -o "%~dp0desktop\artifacts\win-x64" --nologo
if errorlevel 1 (
  echo 构建失败。请安装 .NET 10 SDK 后重试。
  pause
  exit /b 1
)
echo 已完成。双击“启动裁剪.cmd”即可使用。
pause
