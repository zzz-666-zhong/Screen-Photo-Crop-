# 模型说明与历史评估 / Model card and historical evaluation

## 用途 / Intended use

定位拍摄屏幕中显示的完整彩色图片，产生四角用于裁剪和透视校正。模型为候选四边形评分，不是语义分割或去模糊模型。

Locate complete color pictures displayed in photographed screens and provide corners for cropping and perspective correction. The model scores candidate quadrilaterals; it is not a semantic segmenter or deblurring model.

| 项目 / Item | 值 / Value |
|---|---|
| 元数据版本 / Metadata version | `2` |
| 算法 / Algorithm | OpenCV RTrees, random-forest IoU regression |
| 特征数 / Features | 24 |
| 树数 / Trees | 240 |
| 随机种子 / Random seed | `20261008` |
| 权重 / Weights | `screen_crop_forest.xml.gz` (37,695,773 bytes) |
| 权重 SHA-256 / Weights SHA-256 | `60db1a4ad51f553f602a10d8d92e0ebcfefa643842cd0bfbb5b6c63ff9cbaa85` |
| 运行 / Runtime | CPU, OpenCV 4.x |
| 授权 / License | [MIT](../LICENSE) |

模型直接读取压缩权重，特征名及顺序由 `screen_crop.py` 与 `screen_crop_model.json` 共同定义。发布整理未修改或重新训练该权重。

Weights are loaded directly from the compressed file. Feature names/order are defined jointly by `screen_crop.py` and `screen_crop_model.json`. Release preparation did not modify or retrain the weights.

## 检测流程 / Detection pipeline

1. 处理 EXIF 方向，缩放检测副本到最长边不超过 1400 像素，并抑制部分稀疏黄色标线。 / Correct EXIF orientation, resize the detection copy to a maximum dimension of 1400 pixels, and suppress some sparse yellow annotation components.
2. 结合颜色、CLAHE 对比度增强、Canny、多阈值及纹理检测生成四边形；部分候选通过单边延伸补全。 / Combine color, CLAHE, Canny, multiple thresholds, and texture to generate quadrilaterals, with single-side extensions for selected proposals.
3. 提取几何、内外颜色、亮度差、纹理、边缘覆盖与暗色比例等 24 个特征，通过随机森林预测 IoU 评分。 / Extract 24 geometry, color, brightness, texture, edge coverage, and darkness features; predict IoU scores with the forest.
4. 最高分低于 `0.4` 或无候选时拒绝；否则细化四条边、校正透视并输出。评分不是概率。 / Reject when no candidates exist or the best score is below `0.4`; otherwise refine edges and rectify. Scores are not probabilities.

自动边界细化向内调整约 0.5–2 个检测像素以减轻插值残边，默认不按黑色行列裁去内部暗色内容。标线抑制只用于检测，输出仍取自原图。

Automatic refinement includes an inward adjustment of about 0.5–2 detection pixels to reduce interpolation fringes. Dark rows/columns inside the picture are preserved by default. Annotation suppression affects detection only; exported pixels come from the source image.

## 训练来源 / Training provenance

原项目随附训练记录描述了 27 个训练输入：13 张唯一截图中的 9 张、此前 4 张暗色人物照片、6 个仅来自训练图片的亮度/尺寸/宽高比增强样本、8 个合成场景。另 4 张截图留作验证，不参与模型拟合。

The original training record describes 27 inputs: 9 of 13 unique screenshots, 4 earlier dark portraits, 6 brightness/size/aspect-ratio augmentations from training images only, and 8 synthetic scenes. Four other screenshots were reserved for validation and excluded from fitting.

黄色标线用于读取四角标签；报告中的训练和定量评估使用去标线副本。标注坐标不作为候选生成或评分的输入。原图、完整增强/合成输入及其生成脚本未公开随附，不能仅靠此仓库完整复现原始训练。

Yellow outlines were used to read corner labels; the reported fitting and quantitative evaluation used annotation-cleaned copies. Labels were not inputs to proposal generation/scoring. Original photos and complete augmentation/synthetic inputs and generators are not distributed, so the original training cannot be fully reproduced from this repository alone.

## 历史对比 / Historical comparison

IoU 为预测区域与标注区域的交并比，达标线为 IoU ≥ 0.85。数据来自原始逐张对比表，公开版仅保留样本 ID、分组和指标，见 [evaluation.csv](evaluation.csv)。

IoU measures intersection-over-union between predicted and labeled regions; passing means IoU ≥ 0.85. Values come from the original per-image comparison. The public [evaluation.csv](evaluation.csv) retains sample IDs, splits, and metrics only.

| 数据 / Dataset | 旧版达标 / Previous passes | 当前达标 / Current passes | 旧版平均 IoU / Previous mean | 当前平均 IoU / Current mean |
|---|---:|---:|---:|---:|
| 全部 / All | 5/13 | 13/13 | 54.6% | 96.3% |
| 训练子集 / Training subset | 3/9 | 9/9 | 44.5% | 96.3% |
| 验证子集 / Validation subset | 2/4 | 4/4 | 77.2% | 96.4% |

验证图与训练图共享部分场景和内容，开发中也检查过验证结果，因此不是独立盲测。样本量小，标签存在像素误差，不能将这些结果当作任意新图片的准确率。发布版本的合成测试是程序回归检查，不是新增真实场景准确率评估。

Training and validation share some scenes/content, and validation results were inspected during development, so this is not an independent blind test. The sample is small and corner labels contain pixel-level uncertainty; these figures do not estimate accuracy on arbitrary new images. Synthetic tests are software regression checks, not a new real-world accuracy evaluation.

## 限制 / Limitations

- 纯灰度或几乎无彩色内容的候选可能被过滤。 / Grayscale or nearly colorless candidates may be filtered out.
- 目标极小、靠近图像边缘、严重反光或边界不可区分时可能失败。 / Tiny targets, targets near image edges, glare, and indistinguishable borders can cause failure.
- 没有单独量化抖动强度、相机型号或屏幕类型的效果。 / No separate measurements by shake level, camera, or screen type are available.
- 不恢复失焦、运动模糊、反光、摩尔纹或原屏幕像素。 / Does not restore defocus, motion blur, glare, moiré, or original screen pixels.
- 评分通过仍可能选错区域；新场景建议使用 `--review`。 / A passing score can still select the wrong region; use `--review` on new scenes.

继续训练见 [TRAINING.md](TRAINING.md)。 / See [TRAINING.md](TRAINING.md) for further training.
