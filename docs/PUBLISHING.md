# ScreenCrop 发布指南 / Publishing

原生版的版本号取自 `desktop/Crop.Desktop/Crop.Desktop.csproj`。发布时核对 `BatchSnapshot.CurrentVersion`、中英 [更新记录](../CHANGELOG.md) 和 [验证记录](../desktop/VALIDATION.md)。旧 Python 版本用于历史实验追溯。

The native version comes from `desktop/Crop.Desktop/Crop.Desktop.csproj`. Check `BatchSnapshot.CurrentVersion`, the bilingual [changelog](../CHANGELOG.md), and the [validation record](../desktop/VALIDATION.md) before a release. The historical Python version identifies the legacy tools used in earlier experiments.

## Windows x64 自包含构建 / Self-contained build

从干净的仓库根目录运行。 / Run from a clean checkout at the repository root.

```powershell
dotnet run --project desktop/Crop.Verify/Crop.Verify.csproj -c Release
dotnet publish desktop/Crop.Desktop/Crop.Desktop.csproj -c Release -r win-x64 --self-contained true -o desktop/artifacts/win-x64
```

发布二进制 ZIP 时，把整个 `win-x64` 目录打包，保留所有 DLL、资源和许可证。解压到一个目录后运行 `ScreenCrop.exe`。

For a binary ZIP, include the entire `win-x64` folder with DLLs, resources, and licenses. Extract it into one directory and run `ScreenCrop.exe`.

## 源码 ZIP / Source archive

[release-files.txt](../release-files.txt) 是源码归档的公开文件清单，包含原生项目、双语资源和历史 Python 模型。打包脚本使用 Python 标准库。

[release-files.txt](../release-files.txt) lists the public files for the source archive, including the native project, bilingual resources, and historical Python models. The packager uses the Python standard library.

```powershell
python scripts/build_release.py
```

1.2.5 生成 `dist/screen-photo-crop-v1.2.5.zip`、`.zip.sha256` 和包内逐文件清单。新增源码或界面资源时同步更新清单。提交前可用 `git diff --cached --name-only` 检查暂存文件，把原图、批次结果、失败清单、日志、备份和本机配置留在本地。

Version 1.2.5 produces `dist/screen-photo-crop-v1.2.5.zip`, a `.zip.sha256` file, and an internal per-file manifest. Add new sources and UI resources to the allowlist. Inspect staged files with `git diff --cached --name-only`. Keep originals, batch results, failure lists, logs, backups, and personal settings local.

## GitHub 校验与附件 / GitHub checks and assets

推送后可在 Actions 查看原生桌面构建、核心回归、历史 Python 测试和源码打包。创建 GitHub Release 时可附上源码 ZIP、校验文件和 Windows x64 自包含 ZIP。

After pushing, check Actions for the native build, core regressions, legacy Python tests, and source packaging. A GitHub Release can include the source archive, its checksum, and a separate self-contained Windows x64 ZIP.
