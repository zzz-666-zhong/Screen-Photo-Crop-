# ScreenCrop · 抖动拍屏照片批量裁剪 / Batch screen-photo cropping

[简体中文](#快速开始) · [English](#english)

**Windows 原生桌面版 1.2.5**。手持拍屏出现拖影时，只要目标外边界仍能辨认，ScreenCrop 就可以尝试逐张定位四角，裁出完整画面并校正透视。边界证据充分的结果可自动保存，证据较弱的照片进入复核。输出从原照片采样，保留拍摄时的拖影和暗色内容。

[使用指南](docs/USAGE.md) · [检测与模型说明](docs/MODEL_CARD.md) · [验证记录](desktop/VALIDATION.md) · [更新记录](CHANGELOG.md)

## 快速开始

1. 完整解压或克隆仓库，在 Windows x64 上双击 **`启动裁剪.cmd`**。首次从源码构建需 .NET 10 SDK 并联网还原 NuGet 依赖。更新过已有的源码目录时，先运行一次 `安装环境.cmd` 重新构建。已有构建可直接运行 `desktop/artifacts/win-x64/ScreenCrop.exe`。
2. 选择原照片目录、直接选择多张照片，或把照片拖入工作台。选择一个新的结果目录。目标本身是正方形时勾选「目标图片为正方形」。首轮可保留原生裁剪分辨率和 `0` 像素内切。
3. 点击「开始整批处理」，再处理「待复核」并抽查「自动通过」。底部可下拉选页，或输入页码后按 Enter 跳转。
4. 点击缩略图放大检查原照片，可调整四角、换候选框并预览。四角不可辨、目标出框或被大片反光遮挡时，可标记为拍摄失败，并导出重拍清单。

Windows x64 自包含构建可以整体复制到另一台电脑。请保留同目录的 DLL、资源和许可证。

在主窗口顶部选择「简体中文」或「English」。工作台、设置、菜单、提示和帮助会同步切换，软件会记住选择。点击「使用说明」或按 **F1** 可打开内置指南。

## 抖动画面如何裁切

- **逐张定位。** 轮廓与线段生成四边形候选，必要时从锐化副本补找候选。断裂边缘也能提供定位线索。
- **核对边界。** 检查四边支持率、边缘对比、外侧背景和候选歧义。扩展搜索为贴边、近拍、斜拍和浅色弱边补充候选，供人工复核。
- **从原图校正透视。** 拖影较重但轮廓可辨时，可在复核中手动调整后保存。结果仍保留运动模糊。合成拖影检查和真实照片对照的适用范围见 [验证记录](desktop/VALIDATION.md)。

## 批次与输出

| 项目 | 内容 |
| --- | --- |
| `裁剪成功/` | 保存自动通过与人工确认的裁剪，可导出 PNG 或 JPEG。默认保留子目录结构，例如 `photo.jpg_cropped.png`。 |
| `待复核/` | 有候选时保存预裁剪。可在工作台中检查候选或手动选四角。 |
| `拍摄失败/` | 保存人工标记失败的原照片副本。输入目录中的原图继续保留。 |
| `拍摄失败记录.csv`、`拍摄失败历史.csv` | 可在 Excel 打开。当前清单用于安排重拍，历史可追溯原因、原图 SHA-256 和「已重裁」状态。 |
| `batch_session.json`、`.screen-crop-journal/` | 保存批次设置、照片相对路径、SHA-256、状态和四角，供暂停续跑与恢复。 |
| `crop_report.csv`、`crop_labels.json` | 整批结果和兼容标签。只有人工确认的记录才标记为 `confirmed`。 |

「批次工具」可刷新、重新定位批次、更新报表、查看统计或导出 ZIP 备份。统计批次成功率时，保留输入总数，并分别报告自动通过、人工确认、待复核、拍摄失败和处理错误。

## 开发与构建

```powershell
dotnet build desktop/Crop.Desktop/Crop.Desktop.csproj -c Release
dotnet run --project desktop/Crop.Verify/Crop.Verify.csproj -c Release
dotnet publish desktop/Crop.Desktop/Crop.Desktop.csproj -c Release -r win-x64 --self-contained true -o desktop/artifacts/win-x64
```

原生版使用 C#、.NET 10、WPF 和 OpenCvSharp，在本机处理静态照片。代码组织见 [桌面开发说明](desktop/README.md)，源码与二进制打包见 [发布指南](docs/PUBLISHING.md)，项目许可见 [LICENSE](LICENSE)。

## 旧版 Python

使用 `启动旧版.cmd` 或 `安装旧版环境.cmd`。实验复现和命令行参数见 [使用指南中的旧版部分](docs/USAGE.md#旧版-python)，训练流程见 [训练说明](docs/TRAINING.md)。

## English

**ScreenCrop 1.2.5** is a native Windows x64 app for batch cropping photos of screens. When the complete target boundary remains visible despite camera shake, it can estimate four corners per photo and correct perspective. Clear proposals can be saved automatically. Uncertain captures go to review. The crop comes from the original photo and retains captured motion blur and dark detail.

### Quick start

1. Extract or clone the full repository, then double-click `启动裁剪.cmd` on Windows x64. The first build uses the .NET 10 SDK and NuGet. Run `安装环境.cmd` once after updating an existing checkout to rebuild it. To run an existing build, open `desktop/artifacts/win-x64/ScreenCrop.exe`.
2. Choose a source folder or select or drop photo files, then set a result folder. Enable **Square target** for a square target. Start with **Native crop size** and an inset of 0.
3. Click **Start batch**. Review **Needs review** and spot-check **Auto accepted**. Choose a page in the footer or enter a page number and press Enter.
4. Open a thumbnail to examine or adjust the four corners. If severe blur, glare, or missing content hides essential corners, mark the capture as failed and export the retake list.

Choose **简体中文** or **English** at the top of the app to switch the interface. ScreenCrop remembers the choice. Open **User guide** or press **F1** for in-app help. Copy the whole self-contained build, including its DLLs and licenses, to run it on another Windows x64 computer.

### How it handles motion blur

ScreenCrop proposes a separate frame for each photo using contours and line segments. It can search a sharpened copy for additional proposals, then checks border support and contrast on the detection image. Extended search offers proposals for light borders, close-ups, edge-touching targets, and tilted views. Review can refine frames whose outer boundaries remain visible. [Detector and evaluation notes](docs/MODEL_CARD.md) · [Validation record](desktop/VALIDATION.md)

### Results and batch tools

| File or folder | Purpose |
| --- | --- |
| `裁剪成功/` | Saved auto-accepted or manually confirmed crops, in PNG or JPEG. |
| `待复核/` | Provisional crops for candidates that need review. |
| `拍摄失败/` | Copies of originals flagged for a retake. |
| `拍摄失败记录.csv`, `拍摄失败历史.csv` | The Excel-readable retake list and history, including re-cropped entries. |
| `batch_session.json`, `.screen-crop-journal/` | Batch settings, relative paths, hashes, states, and corner coordinates for resume and recovery. |
| `crop_report.csv`, `crop_labels.json` | Full batch status and compatible labels. The `confirmed` field identifies manual confirmation. |

**Batch tools** can refresh or relocate a batch, update reports, show statistics, and export a backup ZIP. When reporting batch outcomes, use all input photos as the denominator and report each outcome count.

The native app uses C#, .NET 10, WPF, and OpenCvSharp. See [desktop build instructions](desktop/README.md) and the [publishing guide](docs/PUBLISHING.md). The [usage guide](docs/USAGE.md#english) covers the full workflow and the historical [Python tools](docs/USAGE.md#旧版-python). [Changelog](CHANGELOG.md) · [License](LICENSE)
