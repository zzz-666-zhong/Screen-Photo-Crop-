# ScreenCrop · 抖动拍屏照片批量裁剪

**手持拍屏有拖影，只要目标外边界仍能辨认，ScreenCrop 就可以尝试逐张定位四角，裁出完整画面并校正透视。** 同一批照片可以有不同的位移、倾斜和透视。边界证据充分时程序自动保存，证据较弱时把照片和可用候选交给人工复核。输出从原照片采样，保留拍摄时的拖影、暗色内容和纹理。

当前默认入口是 **Windows x64 原生桌面版**，使用 C#、.NET 10、WPF 和 OpenCvSharp，在本机处理静态照片。旧版 Python 随机森林与权重保留用于复现实验。

[使用指南](docs/USAGE.md) · [检测与模型说明](docs/MODEL_CARD.md) · [原生版验证记录](desktop/VALIDATION.md) · [更新记录](CHANGELOG.md)

## 快速开始

1. 完整解压或克隆仓库，在 Windows 上双击 **`启动裁剪.cmd`**。首次从源码构建需安装 .NET 10 SDK，并联网还原 NuGet 依赖。已有构建可直接启动 `desktop/artifacts/win-x64/ScreenCrop.exe`。
2. 选择原照片目录和一个新的结果目录。目标本身是正方形时勾选「目标图片为正方形」。首轮建议保留原生裁剪分辨率，四边内切保持 `0`。
3. 点击「开始整批处理」。批量完成后先处理「待复核」，再抽查「自动通过」，重点检查拖影方向上的角点、细边和容易被误选的内部轮廓。
4. 打开缩略图可放大、拖动或重选四角。检查右侧预览后点「确认保存并下一张」。若强拖影、反光或缺边使目标无法辨认，可标记为拍摄失败。

自包含构建可在 Windows x64 电脑上直接运行。迁移时请复制整个发布目录，包含本机 DLL 和许可证。

## 抖动画面如何裁切

- **每张独立定位。** 轮廓与线段生成四边形候选，必要时在增强后的检测图上补找候选。分离或断裂的边缘也可提供定位线索。
- **用未增强的像素核对外边界。** 检查四边支持率、边缘对比、外侧背景、细框和候选歧义。大图还会尝试在两种尺度定位，并核对两组有效四角是否一致。
- **分流后再导出。** 拖影较重但轮廓可辨的照片可以手动校正四角再保存。四角不可辨、目标出框或被大片反光遮挡时，建议重拍。
- **保留采集痕迹。** 透视校正会重新采样像素，输出仍保留运动模糊。对抖动边界的适应性以具体样本为准。合成拖影检查与真实会话验证见 [检测与模型说明](docs/MODEL_CARD.md) 和 [原生版验证记录](desktop/VALIDATION.md)。

## 批次与输出

| 项目 | 内容 |
| --- | --- |
| `裁剪成功/` | 自动通过和人工确认的 PNG。沿用原相对目录，文件名如 `photo.jpg_cropped.png`。 |
| `待复核/` | 有可用候选时保存预裁剪，便于检查。无候选的照片仍可在工作台手动选四角。 |
| `已排除/` | 已有裁剪在人工标记拍摄失败后移入此处，原照片留在输入目录。 |
| `batch_session.json` | 恢复批次所需的设置、相对路径、状态、四角和源图及输出 SHA-256。 |
| `crop_report.csv` | 整批状态及原因，采用带 BOM 的 UTF-8，可用 Excel 打开。 |
| `crop_session.json`、`crop_labels.json` | 供现有科研脚本读取的兼容记录。`confirmed` 仅在人工确认时为真。 |

暂停或退出后，打开含 `batch_session.json` 的结果目录即可继续批次。统计时建议保留全批分母，并分别报告自动通过、人工确认、待复核、拍摄失败和处理失败。

## 开发与复现

```powershell
dotnet build desktop/Crop.Desktop/Crop.Desktop.csproj -c Release
dotnet run --project desktop/Crop.Verify/Crop.Verify.csproj -c Release
dotnet publish desktop/Crop.Desktop/Crop.Desktop.csproj -c Release -r win-x64 --self-contained true -o desktop/artifacts/win-x64
```

`Crop.Core` 负责检测、透视和批次记录，`Crop.Desktop` 提供桌面工作台，`Crop.Verify` 运行 OpenCV 几何与批次回归。当前原生版固定 OpenCvSharp `4.13.0.20261107`，发布目录随附第三方许可。项目许可见 [LICENSE](LICENSE)。

## 旧版 Python

使用 `启动旧版.cmd`，或先运行 `安装旧版环境.cmd`。旧版命令行、数据与训练入口见 [使用指南中的旧版部分](docs/USAGE.md#旧版-python) 和 [训练说明](docs/TRAINING.md)。

## English summary

ScreenCrop batch-crops images from photographed screens, including captures with **handheld camera shake and visible motion blur**. When the outer frame remains distinguishable, it estimates each photo’s corners independently and rectifies perspective. Uncertain boundaries go to manual review. Crops are sampled from the original photo and retain captured blur. The default Windows x64 app uses local OpenCV geometry. The legacy Python models and their evaluation are documented in the [model card](docs/MODEL_CARD.md).
