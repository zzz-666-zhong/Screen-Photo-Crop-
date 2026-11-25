# ScreenCrop 发布指南 / Publishing

原生桌面版的版本号取自 `desktop/Crop.Desktop/Crop.Desktop.csproj`。发布新的桌面版本时，同步核对 `BatchSnapshot.CurrentVersion`、[更新记录](../CHANGELOG.md) 和验证记录。旧 Python 脚本的版本号用于对应历史实验。

## Windows x64 自包含构建

从干净的仓库根目录运行以下命令。

```powershell
dotnet run --project desktop/Crop.Verify/Crop.Verify.csproj -c Release
dotnet publish desktop/Crop.Desktop/Crop.Desktop.csproj -c Release -r win-x64 --self-contained true -o desktop/artifacts/win-x64
```

解压或复制整个 `win-x64` 目录后即可运行 `ScreenCrop.exe`。如需上传 Windows 可运行附件，可将这个自包含目录整体压缩，保留所有 DLL、资源和许可证。

## 源码 ZIP

[release-files.txt](../release-files.txt) 是源码归档的公开文件清单，包含原生项目和历史 Python 模型。Python 打包工具只用标准库。

```powershell
python scripts/build_release.py
```

当前版本的归档文件为 `dist/screen-photo-crop-v1.2.4.zip`，同时生成 `.zip.sha256` 和包内逐文件校验清单。新增项目文件或图标资源时，把对应路径加入清单。提交前用 `git diff --cached --name-only` 检查将要上传的文件，原照片、批次备份、失败清单、日志、本机配置和构建目录应留在本地。

## GitHub 校验与附件

推送后可在 Actions 查看原生桌面构建与核心回归，以及旧版 Python 测试和源码打包。创建 GitHub Release 时，可提供源码归档及校验文件，也可另附 Windows x64 自包含 ZIP。随附说明可参考 [更新记录](../CHANGELOG.md)。

The self-contained Windows build uses .NET 10 and publishes with both runtime binaries and license notices. The Python packaging script builds the allowlisted source archive, including the historical model files. Keep private photos and batch outputs outside the published source.
