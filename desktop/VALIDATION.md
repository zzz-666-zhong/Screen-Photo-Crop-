# 原生版验证记录

2026-11-22，Windows x64，.NET 10.0.103，OpenCvSharp 4.13.0.20261107。新程序不加载学习模型，不调用 Python，不操作手机或云台。旧实验原片和裁剪结果仅被读取。

## 开发诊断

从 PIMoG 的 slight / extreme 历史人工确认记录中，选取全部人工修改项及按固定间隔选取的普通项，共 44 张，逐张核验原片 SHA-256。该集合在开发中被查看和用于改进，不能作为独立验证。

同一正方形定位条件下，旧 `detect_black_border` 对照有 23/44 达到 IoU ≥ 0.85；新检测器为 38/44。新规则将 16/44 自动通过、28/44 留待复核；自动通过的 16 张均达到 IoU ≥ 0.90。该集合刻意包含困难样例，不能据此估计普通批次通过率。不同算法框的重叠并不能单独证明解码质量改善。

## 另一个拍摄会话

开发规则固定后，使用 STSR `20261026_180920_298_extreme` 的全部 500 张 COCO 原片。清单来自已有评估 `geometry.json`，所有原片 SHA-256 与记录一致。它属于不同拍摄会话，但共享装置与相近环境，且多数参考四角来自历史自动框及复核流程，**不是 500 张独立人工精标真值**，也不是跨设备泛化测试。

- 491/500 与参考框的 IoU ≥ 0.85；490/500 ≥ 0.90；484/500 ≥ 0.95。
- 306 张自动通过，194 张进入复核。
- 自动通过中 1 张低于 IoU 0.85，2 张低于 IoU 0.90（后者包含前者）。这些差异未用于本轮再调检测阈值。
- 检测循环含文件读取、记录的总时间约 120.5 秒；逐图检测平均约 198 ms。此处不是整批 PNG 导出速度，不能等同为真实交互吞吐。

当前分流减少了必须逐张确认的数量，但仍会放过部分错误或有分歧的边界，也会让正确框进入复核。应抽查自动通过结果；没有证明零误裁或提升了水印解码准确率。严重模糊、浅色留白边界与内部强轮廓仍是重点困难情况。

## 软件与界面验证

`Crop.Verify` 用真实 OpenCV 运算验证：乱序/无效角点、透视与暗色内容保留、清晰与合成拖影定位、空白面板分流、损坏图片后继续、自动结果不冒充人工标签、人工补裁与排除归档、暂停续跑、重开不覆盖已保存输出、源图改变与路径越界拦截。测试只创建独立临时文件。

WPF 窗口已实际加载批次、打开四角编辑器，并离屏渲染检查中文、按钮对比度、缩略图卡片、角点和裁剪预览。离屏截图检查不能替代用户鼠标操作和长期使用验证。

## 复现

```powershell
dotnet run --project desktop/Crop.Verify/Crop.Verify.csproj -c Release
```

真实数据对照接口：`Crop.Verify.exe --evaluate cases.json results.json`。JSON 为数组，每项包含 `image`、原图像素四角 `quad`（四行两列）、`square`、`split` 和可选 `baselineIou`。程序输出每张候选、分流原因、边界证据和耗时。正式使用前应冻结名单、原图哈希和指标口径；查看过的样本只能作为后续开发数据。

私人原片路径、逐图验证数据、截图与构建产物保存在本地被 Git 忽略的 `desktop/validation` 和 `desktop/artifacts`，不纳入源码发布。

English summary: Eleven real-OpenCV behavioral checks pass, including EXIF orientation, checkpoint interruption recovery, concurrent-writer protection and conflicting-output preservation. The actual WPF window also passed five scripted checks: EXIF thumbnail orientation, review filtering, corner/preview loading, confirm-and-next, and filename search. In the 44-image development diagnostic, IoU ≥ 0.85 improved from 23/44 with the old detector to 38/44; this set was used during development. On a separate, fixed 500-image capture session, 306 were accepted automatically and 194 deferred; 491/500 overlap the recorded references by IoU ≥ 0.85. Two automatically accepted results fall below IoU 0.90. Most references came from previous automatic crops and review rather than independent human ground truth. The session shares hardware/environment with development; these numbers do not establish generalization, zero errors, or improved watermark decoding. Approx. 120.5 seconds measures the evaluation loop, not full PNG export throughput.
