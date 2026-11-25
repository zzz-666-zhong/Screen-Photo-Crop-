# Native desktop / 原生桌面版

`Crop.Core` contains deterministic OpenCV geometry, checkpointing and research receipts. `Crop.Desktop` contains the WPF UI. `Crop.Verify` runs image-processing and batch-behavior regressions without real hardware.

```powershell
dotnet build desktop/Crop.Desktop/Crop.Desktop.csproj -c Release
dotnet run --project desktop/Crop.Verify/Crop.Verify.csproj -c Release
```

The root `启动裁剪.cmd` publishes and runs the new app. `安装环境.cmd` builds only. Python and model weights are required only for the retained legacy entry points.

Windows x64 only. A first source build downloads locked OpenCvSharp package versions through NuGet. Do not remove native DLLs from the self-contained distribution. OpenCvSharp is Apache-2.0; OpenCV's bundled notices and upstream licenses accompany the binary distribution.

真实样本结果与限制见 [VALIDATION.md](VALIDATION.md)。源程序使用同一批次锁、原子 JSON/PNG 写入和文件哈希保护；暂停/退出在当前照片完成后生效。应用不修改输入照片，不触发采集设备，不把自动结果写成人工训练真值。
