# 模型说明与历史评估 / Model card and historical evaluation

## 用途 / Intended use

定位拍摄屏幕中显示的完整图片，产生四角用于裁剪和透视校正。原森林主要用于彩色内容，v0.2.0 对灰度和低对比度候选补充四边/纹理证据。模型为候选四边形评分，不是语义分割或去模糊模型。

Locate complete pictures displayed in photographed screens and provide corners for cropping and perspective correction. The original forest primarily handles colorful content; v0.2.0 adds four-border/texture evidence for grayscale and low-contrast proposals. The model scores quadrilaterals; it is not a semantic segmenter or deblurring model.

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

模型直接读取压缩权重，特征名及顺序由 `screen_crop.py` 与 `screen_crop_model.json` 共同定义。该通用森林在 v0.3.0 中保持原权重；新增反光森林见下文。

Weights are loaded directly from the compressed file. Feature names/order are defined jointly by `screen_crop.py` and `screen_crop_model.json`. The base forest retains these weights in v0.3.0; the new reflection forest is described below.

## 检测流程 / Detection pipeline

1. 处理 EXIF 方向，缩放检测副本到最长边不超过 1400 像素，并抑制部分稀疏黄色标线。 / Correct EXIF orientation, resize the detection copy to a maximum dimension of 1400 pixels, and suppress some sparse yellow annotation components.
2. 结合颜色、CLAHE 对比度增强、Canny、多阈值及纹理检测生成四边形；部分候选通过单边延伸补全。 / Combine color, CLAHE, Canny, multiple thresholds, and texture to generate quadrilaterals, with single-side extensions for selected proposals.
3. 提取几何、内外颜色、亮度差、纹理、边缘覆盖与暗色比例等 24 个特征，通过随机森林预测 IoU 评分。 / Extract 24 geometry, color, brightness, texture, edge coverage, and darkness features; predict IoU scores with the forest.
4. 彩色候选仍采用 `0.4` 阈值。无达标彩色候选时，灰度候选先通过四边覆盖、边缘差异、内部动态范围和纹理隔离筛选，再采用森林 `0.24` 阈值及边缘/纹理排序；无合格候选则拒绝。评分不是概率。 / Color proposals retain the `0.4` threshold. If none qualifies, monochrome proposals must pass four-border coverage, contrast, dynamic-range, and texture-isolation gates, then use a forest threshold of `0.24` with edge/texture ranking. Reject if none qualifies. Scores are not probabilities.
5. `--square` 对候选宽高比例应用柔性参考，不硬性排除透视后的长方形；随后用完整四角输出 1:1。 / `--square` applies a soft aspect prior without rejecting perspective-distorted rectangles, then rectifies all four corners to 1:1.

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

## v0.2.0 合成回归 / Synthetic regression

使用 [场景生成器](../examples/recognition_scenes.py) 与相同权重比较 v0.1.1 和 v0.2.0。8 类场景包括彩色、正方形、灰度、灰度正方形、暗色、模糊、小目标、低对比度。阈值开发使用种子 11、29，验证使用 41、67。验证组 IoU ≥ 0.85 达标数从 10/16 提升到 16/16，平均 IoU 从 61.0% 提升到 97.7%。逐张记录见 [recognition-v020.csv](recognition-v020.csv)。

Compare v0.1.1 and v0.2.0 with the [scene generator](../examples/recognition_scenes.py) and identical weights. Eight categories cover color, square, grayscale, grayscale square, dark, blur, small targets, and low contrast. Seeds 11/29 were used during threshold development; 41/67 for verification. Verification passes at IoU ≥ 0.85 improve from 10/16 to 16/16; mean IoU improves from 61.0% to 97.7%. See [per-scene metrics](recognition-v020.csv).

复现当前版本，或将旧版 `screen_crop.py` 导出到临时文件后使用 `--baseline` 对比。输出路径必须尚不存在：

Reproduce current metrics, or export the old script to a temporary file and add `--baseline` for comparison. The output path must not exist:

```powershell
python scripts/evaluate_recognition.py --output recognition_metrics.csv
python scripts/evaluate_recognition.py --baseline "D:\temporary\v011_screen_crop.py" --output comparison.csv
```

v0.2.0 未重新训练权重。验证与开发共享场景生成方式，样本少；没有新增独立真实照片测试，历史 13 张原图当前不在可复评输入中，所以未重算历史表。上述合成结果仅证明这些场景的回归行为，不能宣传为真实识别准确率。

Weights were not retrained for v0.2.0. Development and verification share the scene generator and the sample is small. No new independent real-photo test was performed; the 13 historical originals are unavailable for reevaluation, so the historical table was not recomputed. These results verify behavior on synthetic scenes and must not be advertised as real-world accuracy.

## v0.3.0 反光小目标训练 / Reflection specialist training

针对反光屏幕中占比很小的图片，新增独立森林 `screen_crop_reflection.xml.gz`，通用森林保持原样。两份森林各 240 棵树、24 个特征。补充模型只接管面积 ≤ 3.5%、预测 IoU ≥ 0.72 的候选；其余沿用通用选择。该门槛是回归分数，非成功概率。若细化后的可计算特征让补充模型评分下降超过 0.005，则保留细化前四角，减轻内部纹理/反射强边缘导致的误内缩。

A separate `screen_crop_reflection.xml.gz` forest targets small pictures on reflective screens while retaining the base forest. Each has 240 trees and 24 features. The specialist handles proposals with area ≤ 3.5% and predicted IoU ≥ 0.72; other cases use base selection. This is a regression threshold, not a success probability. When measurable refined features lower the specialist score by more than 0.005, retain the original proposal to reduce inward snapping to interior/reflected edges.

| 项目 / Item | 值 / Value |
|---|---|
| 补充元数据版本 / Specialist metadata version | `3` (nested under `reflection` in base metadata) |
| 真实照片 / Real captures | 11 unique: 8 train, 3 holdout |
| 合成训练 / Synthetic training | 16 scenes, 8 kinds × seeds 11/29 |
| 拟合输入 / Fitted inputs | 48: 8 originals + 24 augmented real copies + 16 synthetic scenes |
| 跳过增强 / Skipped variants | 0 |
| 最大深度 / Maximum depth | 16 |
| 训练种子 / Training seed | `20261011` |
| 压力评估种子 / Stress evaluation seed | `20261012` |
| 补充权重大小 / Specialist weight size | 26,610,487 bytes |
| 补充权重 SHA-256 / Specialist SHA-256 | `3a481b428e417cd64b7db8a65c5b20fb91b62a3f3b5fe4a057baf32acd3d8070` |

12 张青色标注截图由使用者确认边界；对应 11 张唯一原照片，其中两张截图来自同一照片。截图通过特征匹配映射到未标线原图，并核对目标内容与位置。训练和评估像素只取未标线原照片，标注仅用于计算目标 IoU，不参与运行时定位。分组在拟合前固定，留出照片及其衍生图不参与训练，也未用于调阈值；开发检查仅采用训练组。

The user confirmed corners in 12 cyan-annotated screenshots corresponding to 11 unique originals; two screenshots show the same capture. Feature alignment mapped labels to unmarked originals, with target content and position checked. Fitting and evaluation use only unmarked photo pixels; labels determine target IoU and never drive runtime localization. Splits were fixed before fitting. Holdout photos and derivatives were excluded from training and threshold tuning; development checks used training groups.

局部反光为椭圆渐变，强度 0.22–0.46；运动模糊核为 5/7/9 像素、随机方向；组合增强叠加约 ±0.8% 图像尺寸的透视扰动，并同步变换四角。增强在最长边 1400 像素副本上生成，保持原文件。公开 [增强与训练代码](../train_screen_model.py)，私人照片及坐标不发布。

Glare uses an elliptical gradient with strength 0.22–0.46. Motion blur uses randomly oriented 5/7/9-pixel kernels. Combined variants add perspective perturbations of approximately ±0.8% of image dimensions and transform labels accordingly. Variants use copies up to 1400 pixels without altering originals. [Augmentation/training code](../train_screen_model.py) is public; private photos and coordinates are excluded.

## v0.3.0 对比结果 / Comparison results

比较 v0.2.1 与 v0.3.0，检测输入最长边 1400 像素；这些目标原本为正方形，均启用正方形候选参考。采用双精度凸多边形 IoU，达标线 IoU ≥ 0.85。逐张匿名数据见 [reflection-v030.csv](reflection-v030.csv)。原照片与增强分别统计，不能将 33 个衍生样例算作新照片。

Compare v0.2.1 and v0.3.0 on detection inputs up to 1400 pixels. The targets are originally square, so both versions use square candidate ranking. Metrics use double-precision convex polygon IoU, passing at IoU ≥ 0.85. See [anonymized per-sample records](reflection-v030.csv). Originals and augmentations are reported separately; 33 derivatives are not additional photos.

| 数据 / Dataset | v0.2.1 达标 / Passes | v0.3.0 达标 / Passes | v0.2.1 平均 IoU / Mean | v0.3.0 平均 IoU / Mean |
|---|---:|---:|---:|---:|
| 训练原照片 / Training originals | 0/8 | 8/8 | 35.64% | 91.84% |
| 留出原照片 / Holdout originals | 0/3 | 3/3 | 46.43% | 88.90% |
| 全部原照片 / All originals | 0/11 | 11/11 | 38.58% | 91.03% |
| 训练组衍生压力样例 / Training stress derivatives | 2/24 | 21/24 | 41.47% | 88.81% |
| 留出组衍生压力样例 / Holdout stress derivatives | 3/9 | 9/9 | 61.26% | 88.95% |

仍有 3 个训练组压力衍生样例低于达标线：`reflection_05` 的组合增强及 `reflection_10` 的反光、组合增强。它们仍定位到目标附近，但边界偏差较大。留出组只有 3 张照片，和训练组共享屏幕、拍摄环境与相似视角，标注从截图映射也存在像素误差；结果不代表任意屏幕或强反光情况下的识别准确率。

Three training stress derivatives remain below threshold: the combined variant of `reflection_05`, and glare/combined variants of `reflection_10`. Their regions remain near the target but borders differ substantially. Only three originals are held out, sharing the screen, environment, and similar viewpoints with training. Screenshot-to-original labels also have pixel uncertainty; results do not estimate accuracy across arbitrary screens or strong glare.

原有 8 类合成场景、验证种子 41/67 的 16 个样例全部达标；14 个结果与 v0.2.1 相同，两个小目标 IoU 略有提高。逐张记录见 [recognition-v030.csv](recognition-v030.csv)。这些种子未参与本次拟合，但场景生成方式相同，仅用于功能回归。

All 16 existing synthetic checks across eight categories and seeds 41/67 pass. Fourteen results match v0.2.1; two small targets improve slightly. See [recognition-v030.csv](recognition-v030.csv). These seeds were excluded from this fitting, but share the generator; they verify software regression.

复评方法见 [TRAINING.md](TRAINING.md)。检测增强、训练与匿名结果可复查；私人原照片缺席意味着无法仅从公开仓库完整复现真实照片部分。抗反光和抗抖动改进指边界定位，不恢复被反光或模糊遮盖的图像细节。

See [TRAINING.md](TRAINING.md) for evaluation commands. Augmentation, fitting, and anonymous metrics are inspectable; absent private originals prevent full reproduction of the real-photo portion from public files alone. Robustness improvements concern localization and do not restore details obscured by glare or blur.

## v0.5.0 浅色背景完整边界 / Whole-picture borders on light backgrounds

本次改进检测与评分流程，两个随机森林权重保持原 SHA-256，没有新增拟合权重。新增 [white_border.py](../white_border.py) 在最长边 700 像素副本上估计每个颜色通道的二次光照曲面，迭代保留残差较小的 65% 网格点拟合背景；亮度覆盖与背景残差不满足条件时直接走通用检测。

This update changes detection/routing while retaining both forest hashes; no new weights were fitted. [white_border.py](../white_border.py) estimates a quadratic illumination surface per color channel on a copy up to 700 pixels, iteratively fitting the lowest-residual 65% of grid samples. Images without sufficient bright coverage or a smooth residual background use the general detector.

多组背景差异阈值和闭运算生成边界候选，去掉连接到整张照片外围的干扰；白底文字按一组字符包围框生成候选。仅当开启正方形模式时，使用可见边长生成弱边补全候选。候选面积限制在原照片 3.5%–60%，按外围背景残差、边界内外对比、内部变化及形状参考评分，过滤平坦面板，并将分数接近但空间分离的多张图片交回通用检测。该规则分数不表示概率。

Residual thresholds and morphological closing generate proposals, removing components connected to the image perimeter. White-page text gets grouped content envelopes. Only Square mode uses visible side lengths to complete weak sides. Proposals occupy 3.5%–60% of the photo and are scored using exterior residual, border contrast, interior variation, and shape. Flat panels are rejected; separate similarly scored pictures fall back to general detection. Rule scores are not probabilities.

合格的完整区域优先于森林小目标候选，避免选择整张建筑内部的时钟、招牌或局部纹理。四边均有较强证据时才细化，并检查细化后的结构评分；浅色/弱边直接保留完整候选，减轻内缩。输出仍取自原照片。未通过浅底判断的照片继续使用原有通用/反光模型。

Qualified whole-picture regions precede small-target proposals, avoiding clock/sign/texture fragments inside a larger picture. Refinement requires strong evidence on all four sides and a structural score check. Weak/light sides retain the full proposal. Exported pixels still come from originals; other photos keep the base/reflection model path.

通用路径将四边的像素、梯度和纹理采样批量化，将每个候选多次分位数计算合并，并在生成候选、细化、复评分之间复用图像证据。24 特征顺序保持不变；数值差异约为浮点舍入量，原 11 张反光照片的逐张 IoU 保持一致。

The general path batches four-side pixel/gradient/texture samples, combines repeated percentile work, and reuses evidence across proposal generation, refinement, and rescoring. Feature order is unchanged; differences are floating-point rounding scale. Per-photo IoU on the eleven reflection originals is unchanged.

### 评估范围 / Evaluation scope

用户确认了 5 张截图的目标边界：第一张小框是误检，应提取整张建筑；其余四张为完整图片边界。通过特征匹配映射到未标线原照片，目标相关系数为 0.952–0.998，并人工查看映射图。截图只用于标签，识别输入均为原照片。5 张都用于开发，不能作为独立验证。

The user confirmed the intended borders in five screenshots: the first small box was an error and should enclose the building picture; the other four show complete borders. Feature alignment maps them to unmarked originals, with target correlations 0.952–0.998 and visual inspection. Screenshots supply labels only; detection reads originals. All five were development examples, not independent validation.

从既有人工修改记录中，排除这 5 张后按固定间隔另取 12 张，先固定名单与检查标签，再查看新版本成绩；未按这 12 张的结果调阈值。其后补充的平坦面板否定测试只调整内部变化检查。它们与开发图共享设备、环境和相近角度，属于同场景检查。旧反光集 11 张用于回归保留检查，其中 8 张曾训练过反光模型。

Twelve other manually corrected captures were selected at fixed intervals after excluding those five, with the list/labels fixed before inspecting new results. Their scores did not tune thresholds; a later synthetic flat-panel negative only tightened interior variation checking. They share devices/environment/viewpoints and are same-session checks. The eleven earlier reflection captures verify retention; eight previously trained the reflection forest.

| 分组 / Group | v0.4.1 达标 / Passes | v0.5.0 达标 / Passes | 旧平均 IoU / Old mean | 新平均 IoU / New mean | 旧识别中位数 / Old time | 新识别中位数 / New time |
|---|---:|---:|---:|---:|---:|---:|
| 提供的困难示例 / Supplied examples | 0/5 | 5/5 | 3.28% | 95.79% | 1.412 s | 0.058 s |
| 另取人工修正照片 / Additional corrected captures | 0/12 | 8/12 | 17.80% | 76.95% | 1.262 s | 0.070 s |
| 反光原图回归 / Reflection retention | 11/11 | 11/11 | 91.03% | 91.03% | 2.337 s | 1.556 s |

达标线为 IoU ≥ 0.85。识别时间为每图每版 3 次调用中位数，再取组中位数；预加载森林，排除读图、首次模型加载、预览和保存，两个版本逐图交替执行顺序。运行环境：Windows 11、Intel Core i7-14650HX、Python 3.12.14、OpenCV 4.14.0、NumPy 2.5.3，CPU 本地运行。时间不代表其他硬件或端到端批次速度。

Passing means IoU ≥ 0.85. Times are per-photo medians of three calls, then group medians. Forests are preloaded; image I/O, initial model loading, UI, and saving are excluded. Backend order alternates by photo. Environment: Windows 11, Intel Core i7-14650HX, Python 3.12.14, OpenCV 4.14.0, NumPy 2.5.3, local CPU. These are not other-hardware or end-to-end batch timings.

逐张匿名指标见 [white-border-v050.csv](white-border-v050.csv)。额外检查的 `white_check_06`、`07`、`09`、`12` 仍未达标，分别涉及数字/代码、大留白标题、图表及文字标题。未声明已解决所有白底边界；无可见边缘时可能无法推断原图的精确留白，应人工选四角。旧 16 个合成回归全部通过，逐张见 [recognition-v050.csv](recognition-v050.csv)。新增合成测试覆盖白边、单侧弱边、文字页、竖图、平坦面板和多目标歧义。

See [anonymous per-photo metrics](white-border-v050.csv). Additional cases `white_check_06`, `07`, `09`, and `12` remain below threshold: numbers/code, a sparse heading, a chart, and a text heading. Exact blank margins may be impossible to infer without a visible border; select corners manually. All sixteen earlier synthetic checks pass; see [recognition-v050.csv](recognition-v050.csv). New synthetic tests cover white frames, a faint side, text pages, portraits, flat panels, and ambiguous multiple targets.

### 复评与计时 / Reproduction and timing

使用 [训练文档](TRAINING.md) 的标签格式，将旧脚本和匹配模型放在独立目录。以下命令默认每图重复 3 次，输出路径必须尚不存在：

Use the label format in [TRAINING.md](TRAINING.md), retaining the old script and matching models in a separate folder. The command repeats each photo three times; the output must not already exist:

```powershell
python scripts/benchmark_detection.py "dataset.json" --baseline "previous_version" --output "border_comparison.csv" --repeats 3
python -m unittest discover -s tests -p test_white_border.py -v
```

私人原图及坐标不随公开仓库发布，完整真实图复评需要自行持有相同原图。公开合成生成器 [white_border_scenes.py](../examples/white_border_scenes.py) 不使用私人图像。

Private originals and coordinates are excluded; full real-photo reproduction requires those files. The public [synthetic generator](../examples/white_border_scenes.py) uses no private images.

## 限制 / Limitations

- 灰度检测需要可辨认四边及内部纹理；平坦内容、文本面板或复杂背景可能漏检或误检。 / Grayscale detection needs distinguishable borders and interior texture; flat content, text panels, or complex backgrounds may be missed or misidentified.
- 目标极小、靠近图像边缘、严重反光或边界不可区分时可能失败。 / Tiny targets, targets near image edges, glare, and indistinguishable borders can cause failure.
- 增强覆盖固定检测分辨率下的 5/7/9 像素运动核，但未按真实相机抖动、相机型号或屏幕类型评估泛化。 / Augmentation uses 5/7/9-pixel motion kernels at the detection resolution; generalization by actual camera shake, camera model, or screen type is unmeasured.
- 不恢复失焦、运动模糊、反光、摩尔纹或原屏幕像素。 / Does not restore defocus, motion blur, glare, moiré, or original screen pixels.
- 评分通过仍可能选错区域；新场景建议使用 `--review`。 / A passing score can still select the wrong region; use `--review` on new scenes.

继续训练见 [TRAINING.md](TRAINING.md)。 / See [TRAINING.md](TRAINING.md) for further training.
