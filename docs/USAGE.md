# 使用指南 / Usage guide

命令均从项目根目录运行。示例中的原图目录需自行创建并放入照片；发布包不附带真实原图。Windows 使用下列命令，macOS/Linux 将解释器路径替换为 `.crop-env/bin/python`；图形窗口还需要 Tkinter 和桌面环境。

Run commands from the project root. Create and populate the example input folder yourself; real source photos are not bundled. Use the following interpreter paths on Windows, or `.crop-env/bin/python` on macOS/Linux. Graphical windows also require Tkinter and a desktop session.

## 1. 环境与启动 / Setup and launch

建议使用 Python 3.10 或更新版本。依赖范围来自项目的 `requirements.txt`：

Use Python 3.10 or later. The dependency ranges in `requirements.txt` are:

```text
numpy>=1.24,<3
opencv-python>=4.8,<5
Pillow>=10,<13
```

文件夹选择窗口需要 Tkinter，手动选四角窗口需要支持桌面窗口的 OpenCV。请将主程序与两个模型文件放在同一目录，模型 `.xml.gz` 无需解压。

Folder dialogs require Tkinter, and manual corner selection requires an OpenCV build with desktop-window support. Keep the main script and both model files together. Do not decompress the `.xml.gz` model.

在项目目录打开 PowerShell。首次安装，或迁移到新电脑后，创建独立环境：

Open PowerShell in the project directory. For a fresh installation or a new computer, create the dedicated environment:

```powershell
python -m venv .crop-env
.\.crop-env\Scripts\python.exe -m pip install -r requirements.txt
```

本地已有可用 `.crop-env` 时可直接启动，无需重复安装。虚拟环境含有本机路径，复制整个文件夹到其他电脑后应重新建立环境。

If `.crop-env` already works on this computer, launch directly. Virtual environments contain machine-specific paths and should be recreated after moving the project to another computer.

双击 **`启动裁剪.cmd`**，或运行：

Double-click **`启动裁剪.cmd`**, or run:

```powershell
.\.crop-env\Scripts\python.exe screen_crop.py
```

无参数启动时，先选择是否补裁已有失败图片；开始新批次时，再选择原图文件夹、结果文件夹，以及是否逐张确认。自动处理结束后，如有失败图片，会询问是否立即手动补裁。

With no arguments, the app first asks whether to retry an existing failure folder. For a new batch, select the source folder, result folder, and whether to review each image. After automatic processing, it offers manual correction if failures remain.

## 2. 常用命令 / Common commands

以下命令均在项目目录执行，`结果示例` 是示例输出目录；输入、输出目录必须不同。首次处理一批新照片时，建议使用 `--review` 检查定位结果。

Run these commands from the project directory. `结果示例` is an example output folder; input and output must differ. Use `--review` to inspect localization when processing a new collection for the first time.

**自动批量裁剪 / Automatic batch crop**

```powershell
.\.crop-env\Scripts\python.exe screen_crop.py "原图" "结果示例"
```

**逐张确认自动识别框 / Review proposed crops**

```powershell
.\.crop-env\Scripts\python.exe screen_crop.py "原图" "结果示例" --review
```

**每张图片手动选择四角 / Select corners manually for every image**

```powershell
.\.crop-env\Scripts\python.exe screen_crop.py "原图" "结果示例" --manual
```

**手动补裁失败图片 / Manually retry failed images**

```powershell
.\.crop-env\Scripts\python.exe screen_crop.py "结果示例" --retry-failed
```

补裁命令传入的是包含“裁剪成功”和“裁剪失败”的结果总目录，不是失败子目录。补裁时也会显示结果预览，支持“重新裁剪”；确认保存后才移除对应失败副本，原始输入目录不受影响。

Pass the result root containing `裁剪成功` and `裁剪失败`, not the failure subfolder itself. Retries also show a result preview with Re-crop. Only saving removes the failure copy; the original input folder is unaffected.

**递归处理并保存识别框预览 / Process subfolders and save overlays**

```powershell
.\.crop-env\Scripts\python.exe screen_crop.py "原图" "结果示例" --recursive --debug
```

**覆盖已有裁剪结果 / Replace existing crops**

```powershell
.\.crop-env\Scripts\python.exe screen_crop.py "原图" "结果示例" --overwrite
```

默认跳过已存在的输出。若要重新检查或替换已有结果，应加 `--overwrite`，包括使用 `--review` 或 `--retry-failed` 时。

Existing outputs are skipped by default. Add `--overwrite` when reviewing or replacing them, including with `--review` or `--retry-failed`.

### 手动窗口操作 / Manual window controls

| 操作 / Action | 中文说明 | English description |
|---|---|---|
| 绿色框 / Green outline | 自动识别区域。未手动选点时按 Enter 进入裁剪预览。 | Proposed crop. Press Enter without selecting points to preview it. |
| 左键 / Left click | 依次选择图片本身的左上、右上、右下、左下角。 | Select the picture's top-left, top-right, bottom-right, and bottom-left corners in order. |
| Enter（选点窗口 / Corner window） | 确认四角并进入结果预览。 | Confirm four corners and open the result preview. |
| 右键 / Right click | 撤销上一个点。 | Undo the last point. |
| `R` 或 Re-crop（选点窗口 / Corner window） | 清空当前自动框与选点，重新手动选四角。 | Clear the proposal and selection to choose four corners manually. |
| Esc 或关闭窗口 / Esc or close window | 跳过当前图片。 | Skip the current image. |

审核、手动裁剪和失败补裁均先显示最终裁剪预览（含当前黑边/内缩设置），再由你决定保存。在预览中点击 **“重新裁剪 / Re-crop”** 或按 R，返回当前原图重新选四角，可反复操作；点击 **“保存并下一张 / Save & next”** 或按 Enter，才保存结果并进入下一张。点击跳过、按 Esc 或关闭预览均不会写入新结果，也不会覆盖已有输出。

Review, manual, and retry modes show the final crop, including current trimming/inset settings, before saving. Click **Re-crop** or press R to return to the current original and reselect corners as often as needed. Click **Save & next** or press Enter to save and advance. Skip, Esc, or closing the preview writes no new crop and leaves any existing output unchanged.

## 3. 黑边处理与参数 / Black margins and options

默认流程依据图片外边界去除屏幕背景，**不自动删除图片内部的近黑色行列**。这样可以保留黑衣服和暗色背景。自动边缘细化会额外向内微调约 0.5～2 个检测图像像素，以减轻透视插值残边；这个调整独立于默认值为 0 的 `--inset`，手动模式不执行自动边缘细化。

By default, the picture boundary removes the surrounding screen area, while **near-black rows and columns inside the picture are preserved**. This protects dark clothing and backgrounds. Automatic edge refinement adds an inward adjustment of about 0.5–2 detection-image pixels to reduce interpolation fringes. This is separate from `--inset`, which defaults to 0; manual mode bypasses automatic edge refinement.

如果确认图片内部仍有需要去除的纯黑留边，可显式开启：

If the cropped picture still contains unwanted black padding, explicitly enable trimming:

```powershell
.\.crop-env\Scripts\python.exe screen_crop.py "原图" "结果示例" --trim-black --black-threshold 45 --max-trim 0.48 --overwrite
```

开启后，仅从外围连续裁除近黑像素比例至少为 90% 的行列；近黑像素指三个颜色通道均不超过阈值。默认每边最多裁去对应原尺寸的 48%。此规则可能裁掉真实暗色内容，黑衣人物等照片通常应保持默认设置。

When enabled, trimming removes consecutive outer rows/columns with at least 90% near-black pixels. A pixel is near-black when all three channels are at or below the threshold. Each side is limited to 48% of the corresponding original dimension by default. This rule can remove genuine dark content, so retain the default for images such as dark-clothed portraits.

| 参数 / Option | 默认 / Default | 作用 / Behavior |
|---|---|---|
| `--manual` | 关闭 / Off | 全部手动选四角。 / Manually select corners for every image. |
| `--review` | 关闭 / Off | 逐张确认或修改自动框。 / Review or replace automatic corners. |
| `--retry-failed` | 关闭 / Off | 递归手动处理结果目录下的失败副本。 / Recursively retry failure copies manually. |
| `--recursive` | 关闭 / Off | 包含输入子目录并保留相对目录结构。 / Include input subfolders and preserve relative paths. |
| `--no-trim-black` | 开启 / On | 保留内部暗色内容。 / Preserve dark content inside the crop. |
| `--trim-black` | 关闭 / Off | 开启外围近黑行列清除。 / Enable near-black outer-row/column trimming. |
| `--black-threshold` | `45` | 近黑阈值，范围 `0–255`，仅清黑边时生效。 / Near-black threshold, `0–255`; used only when trimming. |
| `--max-trim` | `0.48` | 每边黑边清除比例上限，范围 `0–0.49`。 / Per-side black-trim limit, `0–0.49`. |
| `--inset` | `0` | 额外向内裁剪比例，范围 `0–0.1`，每侧分别应用。 / Extra inward crop fraction, `0–0.1`, applied to each side. |
| `--overwrite` | 关闭 / Off | 替换已有 PNG 输出。 / Replace existing PNG outputs. |
| `--debug` | 关闭 / Off | 保存带四角轮廓的原图预览。 / Save source-image previews with corner outlines. |

`--manual`、`--review`、`--retry-failed` 三者互斥；`--trim-black` 与 `--no-trim-black` 互斥。

`--manual`, `--review`, and `--retry-failed` are mutually exclusive. `--trim-black` and `--no-trim-black` are also mutually exclusive.

## 4. 输出与报告 / Outputs and reports

```text
结果示例/
├── 裁剪成功/                  # Successful crops
│   └── photo.jpg_cropped.png
├── 裁剪失败/                  # Failed or skipped source copies
│   └── another_photo.jpg
├── _debug/                    # Optional: --debug
│   └── 裁剪成功/
│       └── photo.jpg_cropped.png
├── crop_report.csv            # Normal batch report
└── manual_crop_report.csv     # Created by --retry-failed
```

输出文件名保留原扩展名，例如 `photo.jpg_cropped.png` 与 `photo.png_cropped.png`，避免同名不同格式冲突。读取原图后按 EXIF 方向校正，输出为 RGB PNG；不会修改输入文件。

Output names retain the original extension, such as `photo.jpg_cropped.png` and `photo.png_cropped.png`, preventing collisions between formats. Images are oriented using EXIF metadata and exported as RGB PNG without modifying input files.

CSV 使用带 BOM 的 UTF-8 编码，可在 Excel 中打开，包含 `input`、`output`、`status`、`detail` 四列。每次运行会重写对应报告，不是追加历史记录。

CSV reports use UTF-8 with BOM for Excel compatibility and contain `input`, `output`, `status`, and `detail`. Each run replaces its corresponding report rather than appending a history.

| 状态 / Status | 含义 / Meaning |
|---|---|
| `ok` | 本次已保存，`detail` 通常为输出宽×高。 / Saved in this run; `detail` normally contains width × height. |
| `existing` | 输出已存在，本次跳过。 / Output already exists and was skipped. |
| `skipped` | 用户跳过。 / Skipped by the user. |
| `error` | 识别、读取或处理失败，原因记录在 `detail`。 / Detection, loading, or processing failed; see `detail`. |

退出码：`0` 表示没有处理错误，`1` 表示批次存在图片处理错误，`2` 表示参数、路径或初始化等错误；用户跳过或已有输出不计为处理错误。

Exit codes: `0` means no processing errors, `1` indicates image-processing errors in the batch, and `2` indicates argument, path, or initialization errors. User skips and existing outputs do not count as processing errors.

## 5. 使用边界与排查 / Limitations and troubleshooting

| 情况 / Situation | 说明与处理 / Explanation and action |
|---|---|
| OpenCV 缺少 `ml.RTrees_create` | 当前解释器的 OpenCV 不兼容。使用 `启动裁剪.cmd` 或 `.crop-env`，按依赖文件安装 OpenCV 4.x；自动批处理会提前检查该能力。 / The active OpenCV build is incompatible. Use the launcher or `.crop-env` and install the required OpenCV 4.x build; automatic batches check this capability before processing. |
| 缺少模型或特征版本不一致 / Missing or mismatched model | 自动识别需要与代码匹配的两个模型文件；将同一版本的代码与模型放在一起。 / Automatic detection needs both model files matching the code; keep files from the same version together. |
| 原有结果没有变化 / Existing crops do not change | 已有输出默认跳过，重新处理时使用 `--overwrite`。 / Existing outputs are skipped; use `--overwrite` to regenerate them. |
| 深黑边缘、严重反光或目标太小 / Very dark edges, strong reflections, or tiny targets | 候选生成或边缘定位可能失败，使用 `--review`、`--manual` 或失败补裁。 / Proposal generation or edge localization may fail; review, select corners manually, or retry failures. |
| 灰度图片或几乎无彩色内容 / Grayscale or nearly colorless pictures | 当前候选过滤包含彩色像素比例要求，此类图片可能被排除；可手动裁剪。 / Candidate filtering requires some colored content, so these pictures may be rejected; use manual cropping. |
| 输出仍有模糊、反光、摩尔纹或标线 / Blur, glare, moiré, or marks remain | 本项目负责定位、裁剪和透视校正，不恢复被遮挡内容或原始屏幕像素，也不做去模糊、去水印或内容修复。 / The tool locates, crops, and rectifies pictures; it does not recover obscured content or original screen pixels, deblur, remove watermarks, or restore image content. |
| 需要沿人物或物体轮廓抠图 / Need object cutouts | 当前处理完整矩形图片，不输出按物体轮廓分割的透明背景。 / The tool extracts full rectangular pictures, not object silhouettes with transparent backgrounds. |
| 显示 `ok` 但裁错 / A crop is saved but incorrect | `ok` 只表示成功保存，不保证选中了目标区域；检查预览并人工调整。 / `ok` means the file was saved, not that the target was correct; inspect the result and adjust manually. |

项目总览见 [使用说明.md](../README.md)。

For the project overview, see [使用说明.md](../README.md).
