# 更新记录 / Changelog

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
