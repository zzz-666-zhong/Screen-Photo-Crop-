# ScreenCrop 1.2.5 原生桌面版 / Native desktop

| 项目 / Project | 职责 / Role |
| --- | --- |
| `Crop.Core` | OpenCV 几何检测、透视校正、批次日志和可追溯输出。 / OpenCV geometry, perspective correction, batch journaling, and traceable outputs. |
| `Crop.Desktop` | WPF 工作台、分页、四角复核、失败标记、语言切换和内置使用说明。 / WPF workspace, pagination, corner review, capture failure marking, language switching, and built-in help. |
| `Crop.Verify` | 合成拖影、几何、位深、文件冲突和批次恢复检查。 / Regression checks for synthetic blur, crop geometry, bit depth, file conflicts, and recovery. |

从仓库根目录运行以下命令。 / Run these commands from the repository root.

```powershell
dotnet build desktop/Crop.Desktop/Crop.Desktop.csproj -c Release
dotnet run --project desktop/Crop.Verify/Crop.Verify.csproj -c Release
dotnet publish desktop/Crop.Desktop/Crop.Desktop.csproj -c Release -r win-x64 --self-contained true -o desktop/artifacts/win-x64
```

Windows x64 源码构建使用 .NET 10 SDK 和固定版本的 OpenCvSharp，首次需还原 NuGet。`启动裁剪.cmd` 会运行已有构建，缺少可执行文件时再构建。升级源码副本后，运行 `安装环境.cmd` 重新构建。分发时复制完整的自包含目录并保留许可证。

The Windows x64 build uses the .NET 10 SDK and a pinned OpenCvSharp version. The first build restores NuGet dependencies. `启动裁剪.cmd` builds only when the executable is missing. Run `安装环境.cmd` to rebuild an updated source checkout. Distribute the complete self-contained folder and its licenses.

界面翻译和六主题指南作为程序集资源随应用发布。 / The UI translations and six-topic guide ship as embedded resources. [使用指南 / Usage](../docs/USAGE.md) · [模型说明 / Model card](../docs/MODEL_CARD.md) · [验证 / Validation](VALIDATION.md)
