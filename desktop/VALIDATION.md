# 原生版验证记录 / Native desktop validation

## 1.2.5 回归 / Regression

Windows x64 上使用 .NET SDK 10.0.404，从干净源码构建了自包含程序并确认版本号为 1.2.5。

- **18 项核心检查**通过，包含合成运动拖影、透视校正、16 位 PNG、批次恢复和失败表导出。
- 英文界面下重跑了 **9 项复核工作流**和 **4 项分页检查**，验证保存、失败表导出、复核续接及页码跳转。
- **22 项本地双语界面检查**通过，涵盖主窗口即时切换、筛选选中项、语言偏好保存、动态提示、设置和确认弹窗、F1、帮助窗口同步，以及两个语言下的六个主题。

A clean Windows x64 self-contained build with .NET SDK 10.0.404 reported version 1.2.5.

- **18 core checks** passed, covering synthetic motion blur, perspective correction, 16-bit PNG, recovery, and capture-failure exports.
- **9 review workflow checks** and **4 pagination checks** passed in English, covering save and next, failure CSV export, resuming review, and page jumps.
- **22 local bilingual UI checks** passed, covering immediate switching, selected filter labels, saved preference, dynamic messages, advanced settings, confirmation dialogs, F1, synchronized help, and all six topics in both languages.

合成回归和离屏界面检查用于检验软件行为。真实照片的评估范围见 [模型说明](../docs/MODEL_CARD.md)。 / Synthetic regressions and offscreen UI runs verify the tested behavior. See the [model card](../docs/MODEL_CARD.md) for the scope of real-photo evidence.

## 1.2.4 回归 / Regression

在 Windows x64 上使用 .NET SDK 10.0.404，从干净的源码副本发布自包含版本并确认应用版本为 1.2.4。

- **18 项核心检查通过。** 覆盖合成拖影、浅边与贴边候选、透视校正、EXIF 旋转、16 位 PNG、暂停续跑、批次并发保护、SHA-256 校验、写入中断恢复、拍摄失败归档与回看、空表、搬家和备份。
- **9 项 WPF 工作流检查通过。** 覆盖缩略图方向、筛选与文件名搜索、四角预览、撤销重做、保存下一张、拍摄失败归档及导表、复核位置恢复。
- **4 项 WPF 分页检查通过。** 用 29 张合成照片组成 3 页，验证下拉选页及末页、输入跳转、Enter、越界输入和筛选后的页码状态。

使用 9 × 9 对角运动核的样例自动通过，使用 19 × 19 对角运动核的样例保留四角并进入复核。逐项 IoU 和扩展检测说明见 [模型说明](../docs/MODEL_CARD.md)。这些是合成回归与应用行为检查。真实场景仍受边界可见程度、拍摄装置和背景影响。

从源码根目录运行 `dotnet run --project desktop/Crop.Verify/Crop.Verify.csproj -c Release` 可复现核心检查。WPF 测试使用应用的离屏截图入口，配合 `--verify-ui` 及独立的 `--verify-pagination` 运行；前者需要未被界面测试修改的合成批次，后者需要至少 25 张照片的批次。测试使用独立临时目录。

### English summary of the 1.2.4 regression

A clean Windows x64 self-contained publish used .NET SDK 10.0.404 and produced version 1.2.4. The 18 core checks exercised detection, geometry, bit depth, batch integrity, and recovery. Nine WPF workflow checks covered the review editor, search, capture-failure exports, and review bookmarks. Four pagination checks used a 29-photo fixture with three pages. The 9 × 9 motion-kernel case passed automatically, while the 19 × 19 case retained its corners for review. The [model card](../docs/MODEL_CARD.md) reports individual IoU values.

Run `dotnet run --project desktop/Crop.Verify/Crop.Verify.csproj -c Release` for the core checks. The app's offscreen capture runner can exercise `--verify-ui` on a fresh synthetic fixture and `--verify-pagination` on a batch with at least 25 photos. Use separate temporary directories.

## 1.0.0 历史记录 / Historical validation

2026-11-22，Windows x64，.NET 10.0.103，OpenCvSharp 4.13.0.20261107。新程序不加载学习模型，不调用 Python，不操作手机或云台。旧实验原片和裁剪结果仅被读取。

### 开发诊断 / Development diagnostic

从 PIMoG 的 slight / extreme 历史人工确认记录中，选取全部人工修改项及按固定间隔选取的普通项，共 44 张，逐张核验原片 SHA-256。该集合在开发中被查看和用于改进，不能作为独立验证。

同一正方形定位条件下，旧 `detect_black_border` 对照有 23/44 达到 IoU ≥ 0.85；新检测器为 38/44。新规则将 16/44 自动通过、28/44 留待复核；自动通过的 16 张均达到 IoU ≥ 0.90。该集合刻意包含困难样例，不能据此估计普通批次通过率。不同算法框的重叠并不能单独证明解码质量改善。

### 另一个拍摄会话 / Separate capture session

开发规则固定后，使用 STSR `20261026_180920_298_extreme` 的全部 500 张 COCO 原片。清单来自已有评估 `geometry.json`，所有原片 SHA-256 与记录一致。它属于不同拍摄会话，但共享装置与相近环境，且多数参考四角来自历史自动框及复核流程，**不是 500 张独立人工精标真值**，也不是跨设备泛化测试。

- 491/500 与参考框的 IoU ≥ 0.85；490/500 ≥ 0.90；484/500 ≥ 0.95。
- 306 张自动通过，194 张进入复核。
- 自动通过中 1 张低于 IoU 0.85，2 张低于 IoU 0.90（后者包含前者）。这些差异未用于本轮再调检测阈值。
- 检测循环含文件读取、记录的总时间约 120.5 秒；逐图检测平均约 198 ms。此处不是整批 PNG 导出速度，不能等同为真实交互吞吐。

当前分流减少了必须逐张确认的数量，但仍会放过部分错误或有分歧的边界，也会让正确框进入复核。应抽查自动通过结果；没有证明零误裁或提升了水印解码准确率。严重模糊、浅色留白边界与内部强轮廓仍是重点困难情况。

### 软件与界面验证 / Software and UI checks

`Crop.Verify` 用真实 OpenCV 运算验证：乱序/无效角点、透视与暗色内容保留、清晰与合成拖影定位、空白面板分流、损坏图片后继续、自动结果不冒充人工标签、人工补裁与排除归档、暂停续跑、重开不覆盖已保存输出、源图改变与路径越界拦截。测试只创建独立临时文件。

WPF 窗口已实际加载批次、打开四角编辑器，并离屏渲染检查中文、按钮对比度、缩略图卡片、角点和裁剪预览。离屏截图检查不能替代用户鼠标操作和长期使用验证。

### 复现 / Reproduction

```powershell
dotnet run --project desktop/Crop.Verify/Crop.Verify.csproj -c Release
```

真实数据对照接口：`Crop.Verify.exe --evaluate cases.json results.json`。JSON 为数组，每项包含 `image`、原图像素四角 `quad`（四行两列）、`square`、`split` 和可选 `baselineIou`。程序输出每张候选、分流原因、边界证据和耗时。正式使用前应冻结名单、原图哈希和指标口径；查看过的样本只能作为后续开发数据。

私人原片路径、逐图验证数据、截图与构建产物保存在本地被 Git 忽略的 `desktop/validation` 和 `desktop/artifacts`，不纳入源码发布。

### English notes on the historical data

The 1.0.0 evaluation ran on Windows x64 with .NET 10.0.103 and OpenCvSharp 4.13.0.20261107. The native detector used local geometry. Existing experiment photos and results were read for comparison.

The 44-image PIMoG diagnostic included all manually edited entries and a systematic sample of ordinary entries from historical slight and extreme captures. Original SHA-256 values were checked. Under identical square-target settings, the older `detect_black_border` reached IoU ≥ 0.85 on 23/44, and the new detector on 38/44. Of the 16 auto-accepted photos, all reached IoU ≥ 0.90. These difficult samples informed development.

After the rules were fixed, a separate STSR capture session supplied 500 COCO originals from an existing `geometry.json` manifest. The original hashes matched. In this session, 491/500 reached IoU ≥ 0.85, 490/500 reached 0.90, and 484/500 reached 0.95 against the historical reference frames. The detector auto-accepted 306 and sent 194 to review. Of the automatically accepted cases, one fell below 0.85 and two fell below 0.90 in total. Detection averaged about 198 ms per image. The evaluation loop including reads and recording took about 120.5 seconds. The device and environment were similar to development, and most references came from previous automated crops and review. The results describe this session and its reference frames.

For reproduction, run `Crop.Verify.exe --evaluate cases.json results.json` with a JSON array of `image`, four original-pixel corner pairs in `quad`, `square`, `split`, and optional `baselineIou`. The output records proposals, review reasons, edge evidence, and timings. Freeze the list, hashes, and metric before looking at results for a new validation set. Keep private originals and image-level records local.

Eleven real-OpenCV behavioral checks pass, including EXIF orientation, checkpoint interruption recovery, concurrent-writer protection and conflicting-output preservation. The actual WPF window also passed five scripted checks: EXIF thumbnail orientation, review filtering, corner/preview loading, confirm-and-next, and filename search. Border overlap measures geometry. Watermark-decoding performance and cross-device behavior require separate evaluation.
