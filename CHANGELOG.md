# 更新记录 / Changelog

## 0.6.0 — 2026-10-26

- 新增固定坐标模式：首张确认四角，后续按原图像素坐标批量导出，跳过重复识别与逐张审核。 / Add fixed-coordinate mode: confirm corners once, then export remaining photos at the same source-pixel coordinates without repeated detection or review.
- 支持设置页与 `--fixed` / `--fixed-coordinates`，可组合正方形、递归、覆盖和调试选项。 / Support the startup page and CLI flags, combined with Square, Recursive, Overwrite, and Debug.
- 保存固定四角及参考尺寸，暂停/关闭后续跑无需重新确认；尺寸不同的照片进入失败记录。 / Persist corners/reference size for resume without reconfirmation; report dimension mismatches as failures.
- 自动复用坐标的图片不标为人工审核训练标签，兼容旧批次恢复记录。 / Keep reused-coordinate photos unreviewed for training and retain compatibility with earlier checkpoints.
- 增加固定坐标导出、暂停恢复、尺寸校验和设置页测试，补充双语使用说明。 / Add export, resume, size-validation, and settings tests with bilingual usage documentation.

## 0.5.0 — 2026-10-26

- 新增浅色背景完整边界检测、文字分组候选与正方形弱边补全，减少内部小框误选。 / Add light-background whole-picture detection, grouped text proposals, and square-prior weak-side completion to reduce interior-fragment selections.
- 对弱边保留完整候选，对平坦面板和多目标歧义增加筛选。 / Preserve weak-side proposals and filter flat panels/ambiguous multiple targets.
- 四边特征批量计算、合并分位数计算、复用检测证据；森林权重与 24 特征契约保持不变。 / Batch four-side feature work, combine percentiles, and reuse evidence while retaining forest weights and feature order.
- 记录 5 张开发示例、12 张同场景检查及 11 张反光回归的边界与 3 次重复计时，公开匿名指标和基准脚本。 / Report localization and three-repeat timings for five development examples, twelve same-session checks, and eleven reflection captures with anonymous metrics and a benchmark script.
- 更新双语使用、模型限制和合成回归测试。 / Update bilingual usage/limitations and synthetic regression checks.

## 0.4.1 — 2026-10-24

- 开始裁剪前，对结果目录及成功/失败子目录执行真实创建、写入、重命名和删除预检，权限不足时保留已有批次记录。 / Before cropping, probe directory creation, writing, renaming, and cleanup in output folders; preserve existing checkpoints if access fails.
- 无法写入或存在同名文件时显示可操作的双语错误，返回设置并聚焦结果路径，便于更换目录或从桌面重新启动。 / Show actionable bilingual output-access errors, return to settings, and focus the output path for recovery.
- 进度、标签与目录预检采用独占创建的唯一临时文件，避免 Windows 在权限检查失真时长时间重复尝试临时文件名。 / Use exclusive unique temporary files for checkpoints, labels, and output probes, avoiding prolonged Windows retries when permission checks disagree with actual access.

## 0.4.0 — 2026-10-12

- 保存最终四角、原图 SHA-256、人工修改标记与程序/模型版本，导出人工确认训练标签，保护既有确认记录。 / Store final corners, source hashes, edit flags, and versions; export reviewed training labels and protect prior confirmations.
- 新增上一张修改及可点击、滚动的结果缩略图；重新确认后更新结果，跳过编辑保留旧裁剪。 / Add Previous and clickable scrolling thumbnails; reconfirm to replace a crop, or skip to retain the prior result.
- 记忆目录、模式和选项；暂停、关闭或结束后保存草稿，支持窗口和 `--resume` 续裁。 / Remember folders/modes/options and retain drafts for UI/CLI Resume after Pause, Stop, or Close.
- 每次保存即写入进度和 CSV；失败补裁保留可用于训练的原照片来源。 / Persist progress/CSV after each save and retain usable source images for retry labels.
- 扩展双语使用、标签导出及训练说明与跨批次回归测试。 / Expand bilingual usage/export/training guides and cross-run regression tests.

## 0.3.0 — 2026-10-11

- 原图增加鼠标定位缩放、1–16 倍视野、空格/中键拖移、适应与选区聚焦；放大后选四角仍保存原图坐标，下一张恢复全图。 / Add pointer-anchored 1–16× zoom, Space/middle-button panning, Fit and Focus; corners remain in source coordinates and the next photo starts fitted.
- 在未标线真实照片上训练反光小目标补充森林，结合局部反光、运动模糊及透视扰动增强；保留通用森林，新增边界细化评分检查。 / Train a reflection specialist on unmarked real photos with glare, motion blur, and perspective augmentation; retain the base forest and guard refinement with learned scores.
- 训练按拍摄组隔离留出照片，增强仅作用于训练组；新增确定性压力评估及匿名指标。 / Separate holdout captures by group, augment only training inputs, and add deterministic stress evaluation with anonymized metrics.
- 改用双精度多边形 IoU，修正近共线边界的异常交面积；支持中文路径下的模型序列化。 / Use double-precision polygon IoU to fix invalid intersections near collinear edges and serialize models in Unicode paths.
- 补充双语缩放操作、训练、评估与模型来源说明。 / Expand bilingual zoom, training, evaluation, and provenance documentation.

## 0.2.1 — 2026-10-10

- 自动识别预览后直接点击左侧原图重选四角，点击位置作为第一个新点，无需先按“重新裁剪”。手动和失败补裁也支持此操作。 / Click the left original after detection to start a new four-point selection at that position, without pressing Re-crop. Manual and retry workflows support the same interaction.
- 区分角点单击与拖动：单击重选，按住拖动继续微调；重选清除旧预览，四点有效后才允许 Enter 保存。 / Distinguish handle clicks from drags: click to reselect, drag to adjust. Reselection clears stale previews and Enter saves only after four valid points.
- 更新双语操作说明和交互回归测试。 / Update bilingual instructions and interaction regression tests.

## 0.2.0 — 2026-10-10

- 原图、四角编辑、裁剪结果和批次状态统一在一个 Tk 工作台。 / Unify original, corner editing, crop preview, and batch status in one Tk workspace.
- 自动/手动四角有效后直接预览，按一次 Enter 保存并下一张；重新裁剪清空旧预览，拖动角点可调整。 / Valid automatic/manual corners preview immediately; one Enter saves and advances. Re-crop clears stale previews and corner handles can be dragged.
- 启动页可选择正方形模式，CLI 支持 `--square`，完整四角区域透视校正为 1:1。 / Select Square at startup or use `--square` to rectify the complete corner region to 1:1.
- 灰度/低对比度候选补充四边和纹理证据；原权重保持不变，提供可复现合成回归。 / Add four-border/texture evidence for grayscale/low-contrast candidates, retain weights, and provide reproducible synthetic regression.
- 后台检测避免阻塞编辑器；统一颜色、版式和 Windows DPI 适配。 / Run detection in a worker and improve colors, layout, and Windows DPI support.
- 结束批次不再将当前及剩余图片当作失败导出。 / Stopping no longer exports the current/remaining photos as failures.

## 0.1.1 — 2026-10-09

- 修复精简目录没有 `.crop-env` 时启动脚本直接退出的问题。 / Fix the launcher exiting when a clean download has no `.crop-env`.
- 首次启动自动建立项目独立环境并安装依赖，后续启动复用该环境。 / Automatically create the isolated environment and install dependencies on first launch; reuse it afterward.
- 直接运行裁剪或训练脚本时，遇到缺少依赖或不兼容的 OpenCV 会切换到项目环境。 / Direct crop/training launches detect missing or incompatible dependencies and switch to the project environment.
- 新增 `安装环境.cmd`，用于单独准备环境。 / Add a dedicated Windows environment-setup entry point.

## 0.1.0 — 2026-10-09

首次整理为可公开发布的项目；本次版本号表示软件发布版本，模型元数据版本仍为 2。

First repository release. This is the application release version; the model metadata version remains 2.

- 完整图片检测、边缘细化、透视校正和保留暗色内容的默认裁剪流程。 / Full-picture detection, edge refinement, perspective correction, and dark-content preservation by default.
- 包含已有的 240 棵树、24 个特征的预训练随机森林及继续训练脚本。 / Bundled existing pretrained forest with 240 trees and 24 features, plus a training script.
- 自动批处理、逐张确认、手动选四角、失败补裁、CSV 报告和调试预览。 / Automatic batches, review, manual corners, failure retries, CSV reports, and debug previews.
- 审核、手动和失败补裁增加结果预览与“重新裁剪”按钮；确认保存前可回到当前原图反复选四角。 / Review, manual, and retry modes include a result preview and Re-crop button to reselect corners on the current original before saving.
- 双语说明、MIT 许可证、合成演示数据、回归测试和 GitHub Actions。 / Bilingual documentation, MIT license, synthetic demo data, regression tests, and GitHub Actions.
- 基于明确文件清单的发布打包脚本；本地原图、历史结果和虚拟环境不进入发布包。 / An explicit release file manifest excludes local photos, historical outputs, and virtual environments.

本次发布整理沿用既有模型，不代表重新训练或新增独立准确率评估。

Release preparation reuses the existing model; it does not represent retraining or a new independent accuracy evaluation.
