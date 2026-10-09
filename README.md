# Screen Photo Crop / 拍屏图片裁切工具

从拍摄的屏幕照片中提取屏幕内的完整图片，自动定位四角、校正透视并保留暗色内容。内置已训练模型，支持批量处理、逐张审核、手动裁剪和当前图片重新裁剪。

Extract complete pictures from photographed screens with automatic corner detection, perspective correction, and dark-content preservation. Includes a pretrained model, batch processing, review, manual cropping, and re-cropping the current image.

**Python 3.10+ · OpenCV 4.x · CPU · MIT · v0.1.0**

[使用指南 / Usage](docs/USAGE.md) · [模型与评估 / Model & evaluation](docs/MODEL_CARD.md) · [继续训练 / Training](docs/TRAINING.md) · [发布指南 / Publishing](docs/PUBLISHING.md)

## 功能 / Features

| 中文 | English |
|---|---|
| 定位屏幕内图片本身，支持横图、竖图与透视四边形。 | Locates the picture inside the screen, including landscape, portrait, and perspective-distorted images. |
| 240 棵树、24 个特征的随机森林选择候选区域，并细化四条边。 | A pretrained random forest with 240 trees and 24 features scores candidates, followed by edge refinement. |
| 针对拍摄倾斜、弱边缘及局部反光增强边界定位。 | More robust boundary localization for camera tilt, weak edges, and partial reflections. |
| 默认保留黑衣服、黑背景；需要时显式开启黑边清除。 | Preserves dark clothing and backgrounds by default; black-margin trimming is opt-in. |
| 自动批处理、逐张审核、手动选四角、失败补裁。 | Automatic batches, review, manual corners, and failure retries. |
| 预览结果后可点击“重新裁剪”，回到当前原图调整；确认保存后才进入下一张。 | Preview the result and click Re-crop to adjust the current original; advance only after saving or skipping. |
| 支持子目录、中文路径、EXIF 方向校正和常见图像格式。 | Supports subfolders, Unicode paths, EXIF orientation, and common image formats. |
| 输出 PNG、成功/失败分目录、CSV 记录和可选识别框预览。 | Produces PNG crops, separate success/failure folders, CSV reports, and optional overlays. |

图像处理在本地 CPU 上运行，无需显卡、账号或在线接口。安装依赖需要下载软件包；预训练模型随项目提供，无需重新训练。

Image processing runs locally on the CPU without a GPU, account, or online API. Installing dependencies downloads packages; the bundled model requires no retraining.

## 快速开始 / Quick start

下载并解压发布包，或克隆仓库，在项目根目录执行命令。主程序和两个模型文件应保持在一起，模型压缩文件无需解压。

Download and extract a release or clone the repository, then run commands from the project root. Keep the main script and both model files together; leave the model compressed.

### Windows

```powershell
python -m venv .crop-env
.\.crop-env\Scripts\python.exe -m pip install -r requirements.txt
.\.crop-env\Scripts\python.exe screen_crop.py
```

环境安装完成后，也可双击 **启动裁剪.cmd**，选择输入目录、输出目录及是否逐张审核。源照片不会被修改。

After setup, you can double-click **启动裁剪.cmd** to select source/output folders and review mode. Source photos are not modified.

### macOS / Linux

```bash
python3 -m venv .crop-env
.crop-env/bin/python -m pip install -r requirements.txt
.crop-env/bin/python screen_crop.py input output
```

input 目录需自行创建并放入照片。交互窗口需要 Tkinter、支持 GUI 的 OpenCV 和桌面环境。Windows 为主要桌面使用环境；macOS 桌面交互未纳入 CI。

Create input and add your photos. Interactive windows require Tkinter, GUI-enabled OpenCV, and a desktop session. Windows is the primary desktop environment; macOS desktop interaction is not covered by CI.

### 无需原图的演示 / Demo without external photos

以下命令生成原创合成屏幕场景，再使用随附模型自动裁剪。示例不下载真实照片。

Generate an original synthetic screen scene, then crop it with the bundled model. No real photos are downloaded.

```powershell
.\.crop-env\Scripts\python.exe examples/generate_demo.py
.\.crop-env\Scripts\python.exe screen_crop.py input output --debug
```

查看 output/裁剪成功/ 中的裁剪图和 output/_debug/ 中的边界预览。重复生成演示时请指定新的 --output 文件路径；已有演示图可直接重复裁剪。

Inspect crops in output/裁剪成功/ and overlays in output/_debug/. To generate another demo file, choose a new --output path; an existing demo can be cropped again directly.

## 审核、重新裁剪与批处理 / Review, re-crop, and batch processing

下面的 `python` 指安装了项目依赖的解释器，例如 Windows 下的 `.\.crop-env\Scripts\python.exe`。`input` 是原照片文件夹，`output` 是结果总文件夹，二者必须不同。下面以 `D:\拍屏照片` 和 `D:\裁剪结果` 为例，请替换成自己的路径；路径带空格或中文时建议保留双引号。各项示例独立使用，不必依次执行。

`python` means the interpreter containing the dependencies, such as `.\.crop-env\Scripts\python.exe` on Windows. `input` is the source-photo folder and `output` is the result root; they must differ. The examples use `D:\拍屏照片` and `D:\裁剪结果`; replace them with your own paths and keep the quotes. Each example is independent, not a step to execute in sequence.

### 1. 自动识别后逐张审核 / Review automatic crops

先自动识别每张照片的图片边界，再打开选点窗口供你确认或调整，适合首次处理一批新照片。按 Enter 查看裁剪预览后，可保存或重新裁剪。

Detect the picture boundary automatically, then review or adjust each proposal. Use this when processing a new collection. Press Enter to preview the crop, then save or re-crop.

```powershell
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --review
```

使用项目独立环境的完整命令 / Full command using the project environment:

```powershell
.\.crop-env\Scripts\python.exe screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --review
```

### 2. 全部手动选四角 / Manually crop every image

跳过自动识别，每张照片都由你依次点击左上、右上、右下、左下四角。适合反光严重、边缘不明显或自动识别不准确的图片。

Bypass automatic detection and select top-left, top-right, bottom-right, and bottom-left corners for every photo. Useful for strong reflections, unclear edges, or inaccurate detection.

```powershell
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --manual
```

### 3. 手动补裁失败图片 / Retry failed images manually

如果上一批结果的 `D:\裁剪结果\裁剪失败` 中还有照片，传入结果总目录即可继续手动处理。此命令只需要一个目录参数，不要把“裁剪失败”子目录直接作为参数。确认保存后，图片进入“裁剪成功”，对应失败副本被移除。

If `D:\裁剪结果\裁剪失败` still contains photos from a previous batch, pass the result root to retry them manually. Supply only one directory, not the failure subfolder itself. Saving places the crop in the success folder and removes its failure copy.

```powershell
python screen_crop.py "D:\裁剪结果" --retry-failed
```

### 4. 包含子目录并保存识别框 / Include subfolders and save overlays

递归处理所有子文件夹，保留相对目录结构；`--debug` 另外保存画有检测边界的原图预览，方便检查自动识别结果。

Process all subfolders while preserving their relative structure. `--debug` also saves source-image previews with detected outlines for inspection.

```powershell
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --recursive --debug
```

例如输入 `D:\拍屏照片\批次01\照片01.jpg`，成功时输出如下；这是自动批处理，不会弹出逐张审核窗口。

For input `D:\拍屏照片\批次01\照片01.jpg`, a successful run produces the following. This is automatic batch processing and does not open per-image review windows.

```text
D:\裁剪结果\裁剪成功\批次01\照片01.jpg_cropped.png
D:\裁剪结果\_debug\裁剪成功\批次01\照片01.jpg_cropped.png
```

### 5. 重新处理并覆盖旧结果 / Reprocess and replace existing crops

默认会跳过已有输出。更新模型或裁剪设置后，使用 `--overwrite` 重新处理，替换对应的裁剪 PNG；输入原照片不变。

Existing outputs are skipped by default. After updating the model or crop settings, use `--overwrite` to regenerate and replace the corresponding crop PNGs. Source photos remain unchanged.

```powershell
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --overwrite
```

如果想重新审核已有结果，再决定是否保存替换，可以组合参数：

To review existing results again and decide whether to save replacements, combine the options:

```powershell
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --review --overwrite
```

### 6. 查看全部参数 / Show all options

显示参数说明及默认值，不需要提供输入或输出目录，也不会处理图片。

Show option descriptions and defaults without supplying folders or processing images.

```powershell
python screen_crop.py --help
```

### 7. 查看程序版本 / Show the application version

显示程序版本，便于反馈问题或核对发布版本。它与模型元数据中的版本号是两个不同概念。

Show the application version for troubleshooting or checking a release. This is separate from the model metadata version.

```powershell
python screen_crop.py --version
```

当前版本输出示例 / Example output for the current version:

```text
screen_crop.py 0.1.0
```

### 窗口操作 / Window controls

1. 选点窗口按 Enter 预览绿色自动框，或依次点击左上、右上、右下、左下四角。右键撤销，点击 Re-crop 或按 R 清空选区。 / Press Enter to preview the green proposal, or click top-left, top-right, bottom-right, and bottom-left corners. Right-click undoes a point; Re-crop or R clears the selection.
2. 在结果预览窗口，点击 **重新裁剪 / Re-crop** 返回当前原图，重新手动选四角，可反复调整。 / In the result preview, click **Re-crop** to return to the current original and reselect corners as often as needed.
3. 点击 **保存并下一张 / Save & next** 才保存并继续。跳过、Esc 或关闭预览不会写入新结果。 / Click **Save & next** to save and continue. Skip, Esc, or closing the preview writes no new result.

审核、手动和失败补裁均支持该流程。自动批处理不弹出预览。已有输出默认跳过，重新审核已有结果时加 --overwrite。

Review, manual, and retry modes all support this workflow. Automatic batches do not open previews. Existing outputs are skipped by default; add --overwrite to review existing results again.

支持 JPG/JPEG、PNG、BMP、TIF/TIFF、WebP。输出示例：photo.jpg → output/裁剪成功/photo.jpg_cropped.png；失败或跳过的原图副本进入 output/裁剪失败/。详见 [完整参数与黑边设置](docs/USAGE.md)。

Supported inputs: JPG/JPEG, PNG, BMP, TIF/TIFF, and WebP. Example: photo.jpg → output/裁剪成功/photo.jpg_cropped.png. Failed/skipped source copies go to output/裁剪失败/. See [all options and black-margin settings](docs/USAGE.md).

## 历史评估 / Recorded evaluation

下表来自既有模型的历史同图对比，达标线为 IoU ≥ 85%，不是本次发布重新训练得到的结果。

These historical same-image comparisons use a pass threshold of IoU ≥ 85%. The release was not retrained to produce them.

| 样本 / Samples | 旧版达标 / Previous | 当前模型达标 / Current | 旧版平均 IoU / Previous mean | 当前平均 IoU / Current mean |
|---|---:|---:|---:|---:|
| 全部 / All | 5/13 | 13/13 | 54.6% | 96.3% |
| 验证子集 / Validation subset | 2/4 | 4/4 | 77.2% | 96.4% |

验证图未参与拟合，但与训练图共享部分场景/内容，且开发期间查看过验证结果，不能视为独立盲测或泛化准确率。详见 [模型说明](docs/MODEL_CARD.md) 与 [逐张指标](docs/evaluation.csv)。真实原图及历史裁剪图不随仓库分发。

Validation images were excluded from fitting but share some scenes/content with training, and their results were inspected during development. This is not an independent blind test or generalization accuracy estimate. See the [model card](docs/MODEL_CARD.md) and [per-image metrics](docs/evaluation.csv). Real source photos and historical crops are not distributed.

## 项目结构 / Project structure

```text
screen_crop.py                  Main application
train_screen_model.py           Training entry point
screen_crop_model.json          Model metadata
screen_crop_forest.xml.gz       Pretrained weights
requirements.txt               Runtime dependencies
启动裁剪.cmd                    Windows launcher
docs/                          Bilingual guides and model card
examples/                      Synthetic demo and label template
tests/                         Regression tests
scripts/build_release.py       Clean release packaging
release-files.txt              Explicit release file list
.github/                       CI and contribution templates
LICENSE                        MIT license
```

## 开发与发布 / Development and release

```bash
python -m unittest discover -s tests -v
python scripts/build_release.py
```

打包脚本只使用 release-files.txt 中列出的文件，生成发布 ZIP、校验文件和包内逐文件哈希清单。GitHub Actions 配置 Windows/Linux 与 Python 3.10/3.12 测试，通过后构建附件，不自动创建公开 Release。

The packager uses only files in release-files.txt, producing a ZIP, checksum, and internal file-hash manifest. GitHub Actions is configured for Windows/Linux with Python 3.10/3.12, then builds an artifact; it does not automatically publish a public release.

参见 [贡献指南](CONTRIBUTING.md)、[更新记录](CHANGELOG.md)、[继续训练](docs/TRAINING.md) 与 [GitHub 发布步骤](docs/PUBLISHING.md)。

See [contributing](CONTRIBUTING.md), the [changelog](CHANGELOG.md), [training](docs/TRAINING.md), and [GitHub publishing steps](docs/PUBLISHING.md).

## 使用边界 / Limitations

“抗抖动”改进指裁剪边界定位的鲁棒性，不包含视频防抖或模糊恢复。严重反光、极暗边缘、灰度内容和过小目标可能需要手动处理。程序不去除水印、摩尔纹或覆盖内容的标线，也不沿人物/物体轮廓抠图。保存成功不等于定位准确，新场景建议逐张审核。

Robustness improvements concern crop localization, not video stabilization or deblurring. Strong reflections, very dark edges, grayscale content, and tiny targets may require manual correction. The tool does not remove watermarks, moiré, or overlaid annotations, and does not create object cutouts. A saved crop is not necessarily correct; review new scenes.

## 许可证 / License

项目代码、文档、合成示例生成器及随附模型权重以 [MIT](LICENSE) 许可证发布。用户输入图片不属于本项目授权范围。

Project code, documentation, the synthetic example generator, and bundled model weights are distributed under the [MIT license](LICENSE). User-provided images are outside this license's scope.
