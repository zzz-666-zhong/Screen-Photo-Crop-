# ScreenCrop 1.2.4 原生桌面版 / Native desktop

- `Crop.Core` 负责 OpenCV 几何检测、透视校正、按照片保存的批次日志和可追溯输出。
- `Crop.Desktop` 提供 WPF 工作台、分页、四角复核、失败标记和批次工具。
- `Crop.Verify` 运行合成拖影、边框定位、PNG 位深、文件冲突和批次恢复检查。

从仓库根目录运行以下命令。

```powershell
dotnet build desktop/Crop.Desktop/Crop.Desktop.csproj -c Release
dotnet run --project desktop/Crop.Verify/Crop.Verify.csproj -c Release
dotnet publish desktop/Crop.Desktop/Crop.Desktop.csproj -c Release -r win-x64 --self-contained true -o desktop/artifacts/win-x64
```

Windows x64 源码构建使用 .NET 10 SDK 和固定版本的 OpenCvSharp。首次构建需还原 NuGet。`启动裁剪.cmd` 运行本机已有构建，缺少可执行文件时才构建。升级已有副本时可先运行 `安装环境.cmd`。分发 Windows 自包含版时，复制整个目录并保留许可证。

自动检测与批次分流见 [模型说明](../docs/MODEL_CARD.md)，回归和历史真实照片对照见 [验证记录](VALIDATION.md)。旧 Python 入口和预训练权重用于历史复现。
