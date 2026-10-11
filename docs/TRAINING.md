# 继续训练 / Further training

日常裁剪使用随附的两个森林即可。需要适配新场景时，准备**未标线原照片**和 JSON 四角标签，先按拍摄分组划分训练与留出验证，再训练。至少需要 3 个训练拍摄组；同一次拍摄的缩放、调亮、裁剪等衍生图须属于同一组。

Use the two bundled forests for ordinary cropping. For new scenes, prepare **unmarked original photos** and JSON corner labels. Split by capture group before training, reserving photos for validation. At least three training capture groups are required; all resized, brightened, or cropped derivatives of one capture must share a group.

## 标签格式 / Labels

以下仅示意一条记录；请替换图片路径和真实坐标，并增加训练及验证记录。

This illustrates one record; replace its path and coordinates and add training and holdout records.

```json
[
  {
    "id": "train_001",
    "group": "capture_001",
    "image": "images/photo_001.jpg",
    "quad": [[120, 180], [820, 165], [845, 710], [105, 725]],
    "split": "train",
    "square": false
  }
]
```

`image` 为绝对路径或相对于标签 JSON 的路径；`quad` 是经 EXIF 方向校正后的原图像素坐标，按左上、右上、右下、左下记录。`split` 为 `train` 或 `holdout`。`group` 省略时采用 `id`；训练前应明确填写真实拍摄组。`square` 只影响评估的输出形状，训练仍使用真实透视四角。可选 `augment` 覆盖该记录的增强数量，例如合成图片使用 `0`。

`image` may be absolute or relative to the JSON file. `quad` uses original pixel coordinates after EXIF correction, ordered top-left, top-right, bottom-right, bottom-left. `split` is `train` or `holdout`. `group` defaults to `id`; supply explicit capture groups before training. `square` affects evaluation output shape, while fitting uses the real perspective quadrilateral. Optional `augment` overrides the augmentation count for a record, for example `0` for synthetic images.

脚本同时检查组名与文件 SHA-256，拒绝相同拍摄组或完全相同文件跨越训练、验证。它无法自动判断不同文件是否来自同一次拍摄。

The script rejects capture groups or identical file hashes shared across train and holdout. It cannot automatically identify related captures stored as different files.

## 训练与增强 / Training and augmentation

```powershell
# 通用模型 / Base forest
python train_screen_model.py "dataset.json" --output "trained_model" --augment 3

# 小目标反光场景的补充模型 / Additional forest for small pictures on reflective screens
python train_screen_model.py "dataset.json" --output "trained_reflection" --role reflection --augment 3 --seed 20261011
```

Windows 也可将 `python` 替换为 `.\.crop-env\Scripts\python.exe`。输出目录中的模型文件已存在时，脚本要求换一个目录。

On Windows, `python` can be replaced with `.\.crop-env\Scripts\python.exe`. Existing output model files are protected; choose a new output directory.

`--augment 0–12` 默认 `0`，依次循环生成局部椭圆反光、5/7/9 像素运动模糊、透视扰动叠加反光和模糊。增强仅作用于训练组，四角随透视变换同步更新，原照片不改写。固定 `--seed` 可重现增强。检测和训练副本最长边为 1400 像素，标签按相同比例缩放。

`--augment 0–12` defaults to `0`. Variants cycle through local elliptical glare, 5/7/9-pixel motion blur, and perspective perturbations combined with glare and blur. Only training groups are augmented; perspective transforms update corners too, and source files remain unchanged. A fixed `--seed` reproduces augmentations. Detection/training copies have a maximum dimension of 1400 pixels, with labels scaled accordingly.

森林回归候选与标签的 IoU，IoU > 0.80 的候选重复采样三次；240 棵树，最大深度 16，最小样本数 3。采用双精度凸多边形裁切计算 IoU，避免近共线边界的数值异常。原图最佳候选 IoU < 0.65 时停止；增强图遇到此情况跳过并记录，不把不可检测目标当作可学习样本。`holdout` 不参与拟合。

The forest regresses candidate-to-label IoU. Candidates above IoU 0.80 are sampled three times; the forest has 240 trees, depth 16, and minimum sample count 3. Double-precision convex clipping avoids numerical anomalies near collinear edges. Training stops when an original has no proposal reaching IoU 0.65; such augmented variants are skipped and recorded. Holdout photos are excluded from fitting.

输出包含元数据 `screen_crop_model.json`、权重及 `training_report.json`，报告列出采用/跳过的增强和最佳候选 IoU。通用权重名为 `screen_crop_forest.xml.gz`，反光模型名为 `screen_crop_reflection.xml.gz`。

Outputs include metadata, weights, and `training_report.json`, listing fitted/skipped variants and their best proposal IoU. Base weights are named `screen_crop_forest.xml.gz`; reflection weights are `screen_crop_reflection.xml.gz`.

## 评估及启用 / Evaluation and adoption

先备份当前程序与模型。通用模型需同时替换主程序旁的元数据及通用权重；反光模型需保留原通用模型，将训练输出元数据放进主元数据的 `reflection` 字段，并添加以下路由设置，然后复制反光权重。可参考仓库现有 [screen_crop_model.json](../screen_crop_model.json)。

Back up the application and models first. For a base model, replace both the base weights and metadata beside the script. For a reflection model, retain the base model, place the training metadata under its `reflection` field, add the routing settings below, and copy the reflection weights. See the bundled [metadata](../screen_crop_model.json).

```json
{
  "file": "screen_crop_reflection.xml.gz",
  "minimum_score": 0.72,
  "max_area_fraction": 0.035
}
```

以上是 `reflection` 字段中的附加属性，不是完整元数据。0.72 是预测 IoU 的门槛，非置信概率；0.035 限定候选面积占整张照片不超过 3.5%。无合格补充候选时使用通用模型。新训练任务应在训练/开发组上确定门槛，再一次性检查留出组。

These are additional properties inside `reflection`, not complete metadata. The 0.72 threshold is predicted IoU, not a probability; 0.035 limits candidate area to 3.5% of the photo. The base forest handles cases without a qualifying specialist candidate. Choose thresholds on training/development groups before inspecting holdout results.

保存旧版本 `screen_crop.py` 和匹配的模型到单独文件夹，启用待评估模型后执行：

Save the old script and matching models in a separate directory, install the candidate model, then run:

```powershell
python scripts/evaluate_dataset.py "dataset.json" --baseline "previous_version" --output "holdout_metrics.csv" --split holdout --stress 3 --seed 20261012
python scripts/evaluate_recognition.py --output "synthetic_metrics.csv"
```

输出路径必须尚不存在。真实图评估采用固定的 1400 像素检测副本，IoU ≥ 0.85 为达标；`--stress` 使用独立随机种子生成额外压力样例，衍生样例不算独立照片。逐张检查保存的边界和裁剪内容，记录失败，并在未参与训练的新场景上继续验证。

Output paths must not exist. Real-photo evaluation uses fixed detection copies up to 1400 pixels; passing means IoU ≥ 0.85. `--stress` adds variants from a separate seed; derivatives are not independent photos. Inspect borders and crop contents, record failures, and validate on additional scenes excluded from fitting.

## 复现范围 / Reproducibility

标签模板见 [dataset.example.json](../examples/dataset.example.json)。仓库提供增强算法、合成场景生成器、模型权重和匿名逐张指标。私人原照片、其坐标和本机路径不随仓库分发，因此不能仅靠公开仓库完整重训真实照片部分；数据来源和评估限制见 [MODEL_CARD.md](MODEL_CARD.md)。

See the [label template](../examples/dataset.example.json). Augmentation code, synthetic generators, weights, and anonymized per-sample metrics are public. Private originals, their coordinates, and local paths are excluded, so the real-photo portion cannot be fully retrained from the repository alone. See the [model card](MODEL_CARD.md) for provenance and evaluation limits.
