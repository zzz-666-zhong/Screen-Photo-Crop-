# 继续训练 / Further training

日常裁剪直接使用现有模型即可。若需要适配新的屏幕、背景或图片类型，可使用 `train_screen_model.py`，准备未标线原照片及 JSON 标签数组。以下仅示意单条记录，坐标须替换为对应图片的真实四角；实际至少需要 **3 张训练图片**，并另留验证图片。

Use the bundled model for ordinary cropping. To adapt to new screens, backgrounds, or picture types, provide unmarked photographs and a JSON label array to `train_screen_model.py`. The example below illustrates one record only; replace the coordinates with actual image corners. Training requires **at least 3 training images**, with additional images reserved for validation.

```json
[
  {
    "id": "train_001",
    "image": "images/photo_001.jpg",
    "quad": [[120, 180], [820, 165], [845, 710], [105, 725]],
    "split": "train"
  }
]
```

`image` 可为绝对路径，或相对于标签 JSON 所在目录的路径；`quad` 为原图经 EXIF 方向校正后的像素坐标，建议按左上、右上、右下、左下顺序记录；`split` 必须为 `train` 或 `holdout`。

`image` may be absolute or relative to the JSON file's directory. `quad` uses pixel coordinates after EXIF orientation correction, preferably ordered top-left, top-right, bottom-right, bottom-left. `split` must be `train` or `holdout`.

```powershell
.\.crop-env\Scripts\python.exe train_screen_model.py "dataset.json" --output "trained_model"
```

训练脚本按候选框与标签的 IoU 构造回归目标，对 IoU > 0.85 的候选增加采样权重；无候选或最佳候选 IoU < 0.65 时停止，提示先改善候选生成。模型最大深度为 18，目标树数为 240。

The script uses candidate-to-label IoU as the regression target and duplicates candidates with IoU > 0.85 to increase their sampling weight. It stops if no candidates exist or the best candidate has IoU < 0.65, indicating that proposal generation needs improvement. Maximum tree depth is 18, with a target of 240 trees.

脚本检查相同文件内容的 SHA-256，防止完全相同的图片跨越训练和验证分组。相同拍摄的缩放、调亮、裁剪等衍生图仍需人工归入同一组。`holdout` 不参与拟合，脚本不会自动计算验证成绩或生成报告。

SHA-256 checks reject identical file contents assigned to both training and validation. Resized, brightened, cropped, or otherwise derived versions of the same capture must still be grouped together manually. `holdout` images are excluded from fitting; the script does not automatically calculate validation metrics or generate a report.

输出为 `trained_model/screen_crop_model.json` 和 `trained_model/screen_crop_forest.xml.gz`。在未参与拟合的照片上检查结果后，再备份并替换主程序旁边的两个模型文件。

Training writes `trained_model/screen_crop_model.json` and `trained_model/screen_crop_forest.xml.gz`. Inspect performance on images excluded from fitting, then back up and replace both model files beside the application.

## 数据模板与复现范围 / Dataset template and reproducibility

参见 [标签模板](../examples/dataset.example.json)。其中的图片路径和坐标均为示例，必须替换；模板没有附带训练图片。当前仓库不提供原训练图片、完整增强/合成数据及其生成脚本，也不提供训练记录中的原始图片标签。现有模型的来源与历史指标见 [模型说明](MODEL_CARD.md)。训练脚本不会自动生成增强样本。

See the [label template](../examples/dataset.example.json). Paths and coordinates are illustrative and must be replaced; training images are not included. The repository does not distribute the original training photos, complete augmented/synthetic inputs or their generators, or the original image labels from the training record. See the [model card](MODEL_CARD.md) for provenance and historical metrics. The training script does not generate augmentations automatically.
