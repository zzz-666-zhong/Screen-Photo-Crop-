# 切屏 · 批量裁剪工作台

Windows 原生桌面版：**C# / .NET 10 / WPF / OpenCvSharp**。面向真实抖动拍屏照片，逐图检测边界、透视校正，整批运行后集中复核疑难项。运行不依赖 Python、CNN、随机森林、在线接口或模型权重。

## 启动

双击 `启动裁剪.cmd`。本机已构建的程序位于 `desktop/artifacts/win-x64/ScreenCrop.exe`，可直接打开。首次从源码构建需要 .NET 10 SDK 和联网还原 NuGet 依赖；生成的 Windows x64 自包含目录可整体复制到其他电脑，保留全部 DLL 和许可证。

1. 选择原照片和一个新的结果目录。目录不能相同；已有旧版实验结果不会被自动覆盖。
2. 设置目标形状、是否包含子目录、输出尺寸与内切像素。默认保留原生裁剪分辨率、内切 0，保留真实拖影与暗色内容。
3. 点击“开始整批处理”。可靠结果自动保存，可疑边界暂存，损坏图片记录后继续。
4. 结束后筛选“待复核”，点击缩略图调整四角；检查过的有效候选也可勾选后“确认所选”。
5. 支持完成当前照片后暂停、关闭，以及打开批次继续未处理部分。

## 定位与分流

多阈值轮廓、断裂线段合并和四边组合产生候选，在原始像素上检查边界连续性、对比度、外侧背景、细框恢复与候选歧义。大照片使用两个检测尺度核对边界一致性。所有评分都是启发式证据，不是正确率概率。

自动规则不能保证零误裁。可在总览抽查“自动通过”；不满足规则的结果不会直接放入成功目录。传统检测主要适合亮背景屏幕内有可辨边界的单张图片，严重模糊、边界与背景近似或图片未拍完整时仍需人工处理。没有去模糊、锐化输出或按解码结果选择裁剪框。

## 结果与科研记录

- `裁剪成功/`：自动通过和人工确认的 PNG，保留原相对路径，命名为 `原文件名含扩展名_cropped.png`。
- `待复核/`：有有效候选但需检查的预裁剪；没有候选的照片仅记录在队列中。
- `已排除/`：人工标记拍摄失败后的已有裁剪归档，移出成功目录；原照片保留。
- `batch_session.json`：新桌面版恢复记录，包含每张原图/输出 SHA-256、四角、状态、分流证据和统一处理参数。
- `crop_session.json`、`crop_labels.json`：兼容现有科研配对脚本的身份和四角记录。**自动通过不标为人工确认标签。**
- `crop_report.csv`：全批状态与原因，包含未通过和失败样本，UTF-8 BOM 编码。

透视矫正使用双线性插值；选择固定输出边长时再使用面积缩小。内切发生在全分辨率校正图上。参数在批次创建后锁定，导出时需区分自动通过、人工确认、待复核和拍摄失败，不能只用成功目录的数量代表端到端成功率。

## 开发

```powershell
dotnet build desktop/Crop.Desktop/Crop.Desktop.csproj -c Release
dotnet run --project desktop/Crop.Verify/Crop.Verify.csproj -c Release
dotnet publish desktop/Crop.Desktop/Crop.Desktop.csproj -c Release -r win-x64 --self-contained true -o desktop/artifacts/win-x64
```

核心、界面和验证程序分离：`Crop.Core` 负责传统视觉和存档；`Crop.Desktop` 负责批次浏览、四角交互和后台操作；`Crop.Verify` 执行实际 OpenCV 图像处理及批次回归。验证照片、构建产物和个人目录配置不会进入源码发布包。

技术来源：[WPF 官方文档](https://learn.microsoft.com/dotnet/desktop/wpf/)；[OpenCvSharp](https://github.com/shimat/opencvsharp)。依赖固定为 OpenCvSharp 4.13.0.20261107，发布目录附带第三方许可。

## 旧版

原 Python 实现和权重保留用于结果追溯；入口为 `启动旧版.cmd`，环境准备为 `安装旧版环境.cmd`。旧版操作与训练说明见 [README.legacy.md](README.legacy.md)。新版默认入口完整使用 C# 后端。

---

Native Windows batch cropper built with C#, WPF and traditional OpenCV geometry. Run an entire folder unattended, then inspect a separate review queue. No Python runtime, trained detector, network service or image restoration is used by the new desktop app. Automatic rules are heuristic and do not guarantee correctness. Source files remain intact; crops, hashes, corners, decisions and preprocessing settings are recorded. The legacy Python application remains available through `启动旧版.cmd` for reproducibility.
