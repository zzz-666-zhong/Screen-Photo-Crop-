# 更新记录 / Changelog

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
