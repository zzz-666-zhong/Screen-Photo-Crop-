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

统一工作台和文件夹选择窗口需要 Tkinter 与桌面环境。请将主程序与三个模型文件（JSON 元数据和两份压缩权重）放在同一目录，模型 `.xml.gz` 无需解压。

The unified workspace and folder dialogs require Tkinter and a desktop session. Keep the main script and all three model files (JSON metadata and two compressed forests) together. Do not decompress the `.xml.gz` model.

在项目目录打开 PowerShell。首次安装，或迁移到新电脑后，创建独立环境：

Open PowerShell in the project directory. For a fresh installation or a new computer, create the dedicated environment:

```powershell
python -m venv .crop-env
.\.crop-env\Scripts\python.exe -m pip install -r requirements.txt
```

也可直接双击 `启动裁剪.cmd`，由启动器自动创建环境和安装依赖；双击 `安装环境.cmd` 可只准备环境。首次自动安装需要联网。本地已有可用 `.crop-env` 时会直接复用。虚拟环境含有本机路径，迁移到其他电脑后应重新建立环境。

You can also double-click `启动裁剪.cmd` to create the environment and install dependencies automatically, or `安装环境.cmd` to perform setup only. Initial setup needs internet access. A working `.crop-env` is reused. Environments contain machine-specific paths and should be recreated after moving to another computer.

双击 **`启动裁剪.cmd`**，或运行以下命令。直接运行 `screen_crop.py` 遇到缺少依赖或不兼容版本时，也会准备并切换到本项目环境；双击 `.py` 本身需要 Windows 已配置 Python 文件关联。

Double-click **`启动裁剪.cmd`**, or run the command below. Direct execution of `screen_crop.py` also prepares/switches to the project environment when dependencies are missing or incompatible. Double-clicking `.py` requires a configured Windows Python file association.

```powershell
.\.crop-env\Scripts\python.exe screen_crop.py
```

无参数启动进入设置页：填写原图和结果目录，选择自动审核、手动四角或失败补裁，并选择完整图片或正方形 1:1。失败补裁使用上次结果总目录。批次完成后留在同一页面，点击返回设置可开始下一批。

With no arguments, the startup page lets you choose folders, Review/Manual/Retry, and Full picture/Square 1:1. Retry uses the previous result root. Completion stays on the same page; Settings starts another batch.

## 放大、拖移与精确选四角 / Zoom, pan, and precise corners

审核、手动和失败补裁共用左侧原图的缩放控件。滚轮上/下围绕鼠标放大/缩小，`+` 和 `−` 按钮围绕视野中心缩放，范围为适应窗口的 1–16 倍。右侧始终显示完整裁剪结果。

Review, Manual, and Retry share the source-view controls. Wheel up/down zooms around the pointer; `+` and `−` zoom around the view center. The range is 1–16 times the fitted view. The right pane shows the complete crop.

1. 等待识别结束后，点击“选区 Focus”放大已有角点区域（至少两个点）；没有选点时先用滚轮或 `+`。 / After detection, click Focus to enlarge the selected region (at least two points); otherwise use the wheel or `+` first.
2. 按住空格并用左键拖动原图，或使用中键拖动，查看目标的其他边缘。平移不会重选四角。 / Hold Space and left-drag, or middle-drag, to inspect other edges; panning preserves corners.
3. 在放大原图上依次点击四角；已有完整框时，直接单击即可从该位置重选。按住已有角点拖动可微调，松开后更新预览。 / Click four corners in the enlarged view. A click on a completed selection starts over at that position. Drag handles to adjust; release to refresh the preview.
4. 点击“适应 Fit”恢复全图，检查右侧结果，按一次 Enter 保存并下一张。新照片自动恢复全图。 / Click Fit, inspect the preview, and press Enter once to save and advance; the next photo starts fitted.

缩放只改变显示，原始角点坐标、输出像素和清黑边设置不受缩放倍率影响。重新裁剪当前图片时保留倍率，方便重复选点。

Zoom changes only display: source corner coordinates, output pixels, and trim settings are independent of magnification. Re-cropping the same photo retains zoom for convenient reselection.

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

### 正方形模式 / Square mode

启动页选择“正方形 · 1:1”，或在命令中加 `--square`。它适用于目标原本是正方形的照片：保留四角内的完整内容并校正为 1:1，不从中间截取方形。普通横图/竖图应保持完整图片模式；选错形状可能造成拉伸。审核、手动、失败补裁和自动批处理均支持此参数。

Choose Square · 1:1 at startup, or add `--square`. This mode rectifies the complete four-corner region to 1:1 for originally square pictures, without taking a center crop. Use Full picture for landscape/portrait targets; choosing the wrong shape can stretch content. All processing modes support this option.

```powershell
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --review --square
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --manual --square
python screen_crop.py "D:\裁剪结果" --retry-failed --square
```

### 窗口操作 / Window controls

| 操作 / Action | 中文 | English |
|---|---|---|
| 四角 / Corners | 自动框直接生成右侧预览；手动点击四角后也自动预览。拖动角点调整。 | Automatic corners preview immediately; four manual points also preview automatically. Drag handles to adjust. |
| 点击左侧原图 / Click original | 已有四角时，单击直接清除旧框和预览，点击位置记为第一个新点；单击角点也可重选，按住拖动则微调。 | With four corners selected, click to clear the old selection/preview and use that position as the first new point. Clicking a handle also restarts; dragging adjusts it. |
| Enter | 检查预览后按一次，保存当前图并进入下一张；未选四角时不保存。 | Press once after inspection to save and advance; incomplete selections cannot save. |
| 重新裁剪 / Re-crop · R | 清空当前四角和预览，在同一张原图重新选点。 | Clear corners and preview, then reselect on the same original. |
| 撤销 / Undo · 右键 / Right click · Backspace | 撤销一个点；重新选四角前不能保存旧预览。 | Undo one point; stale previews cannot be saved. |
| 跳过 / Skip · Esc | 当前图片进入失败副本目录，继续下一张，不写入新裁剪。 | Copy the skipped source to failures and advance without writing a crop. |
| 上一张 / Previous | 返回上一张并载入已保存四角，再次保存后更新结果。 | Reopen the previous original with saved corners; save to update. |
| 暂停 / Pause · 继续 / Resume | 保存当前草稿及进度，恢复后继续选点。 | Retain the current draft and progress, then resume selection. |
| 结束 / Stop · 关闭窗口 / Close | 停止本批，保留已经保存的结果；当前及剩余图片不导出失败副本。 | Stop the batch and retain saved results; current/remaining photos are not exported as failures. |

审核、手动和失败补裁使用同一工作台。自动批处理不弹出预览。已有输出默认跳过，重新审核时加 `--overwrite`。

Review, manual, and retry modes use the same workspace. Automatic batches have no preview window. Existing outputs are skipped; add `--overwrite` to review them again.

## 批次管理与人工标签 / Batch management and reviewed labels

### 返回修改与缩略图 / Revisiting and thumbnails

底部“上一张修改 / Previous”返回上一张原照片，载入已保存四角。底部缩略图列表可横向滚动，单击任一图片可以跳转；已有结果显示裁剪缩略图，未完成图片显示原图，当前项以紫色边框突出。批次完成后仍可点击缩略图重新修改。

Previous reopens the previous original with saved corners. Scroll the bottom thumbnail strip horizontally and click any image to jump. Saved items show crop thumbnails, pending items show originals, and the current item has a purple border. Thumbnails remain editable after batch completion.

四角恢复适用于 v0.4.0 保存过标签的图片；旧版只有 PNG、没有四角记录时，重新审核会识别边界，手动模式需要重新选点。 / Corner restoration requires labels saved by v0.4.0; older PNG-only results need detection in Review or new points in Manual.

跳转会保留当前未保存选点为草稿；旧 PNG 和已确认标签只在再次按 Enter 或“保存并下一张”后更新。返回旧结果后选择“跳过”会放弃该次编辑并保留旧结果。保存后继续处理后面的未完成图片；提前跳到后面时，批末会回到遗漏的待处理图片。

Navigation retains unsaved points as drafts. Old PNGs and confirmed labels change only after Save & next or Enter. Skipping a revisited crop discards those edits while retaining its previous output. Saving continues through remaining work; jumping forward does not abandon earlier pending items.

### 记忆设置、暂停与恢复 / Remembered settings, pause, and resume

程序记住最近一次原图目录、结果目录、处理方式、图片形状及选项，下次启动自动填写。“暂停”保存当前草稿和进度，随后点击“继续”，或在重新启动的设置页点击“继续上次批次”。“结束”和关闭窗口也保存恢复记录。续裁使用记录中的目录和全部裁剪选项，包括 CLI 设置的内缩、清黑边阈值等。

The application remembers folders, workflow, shape, and options. Pause saves the current draft and progress. Click Resume, or restart and select Resume on the settings page. Stop and Close also retain a checkpoint. Resuming restores recorded folders and all crop options, including CLI inset and trimming thresholds.

窗口设置保存在项目目录 `.crop-settings.json`；普通批次进度在结果目录 `crop_session.json`，失败补裁使用 `manual_crop_session.json`。每次确认保存后立即更新进度与 CSV。新批次重建进度；续裁保留逐张记录并更新对应条目。运行同一结果目录时请使用一个工作台，原照片应保持原位置。

Preferences live in `.crop-settings.json` beside the application. Normal checkpoints are `crop_session.json` in the result folder; retry uses `manual_crop_session.json`. Saves immediately update progress and CSV. New batches rebuild progress, while Resume retains per-image records. Use one workspace per result directory and retain originals in their locations.

命令行续裁须使用相同目录和原选项，再加 `--resume`：

To resume from the CLI, retain the same folders and options and add `--resume`:

```powershell
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --review --square --resume
python screen_crop.py "D:\裁剪结果" --retry-failed --resume
```

### 将人工确认结果导出为训练标签 / Exporting reviewed training labels

每次确认保存，结果目录 `crop_labels.json` 记录原图路径及 SHA-256、EXIF 校正后的原图四角坐标、输出路径、是否人工修改、程序/模型版本及裁剪选项。审核中直接接受自动框也属于人工确认；手动选点和拖动角点标记为人工修改。无人值守自动结果标记为未确认，导出时排除。

Every confirmed save records source path/hash, source-pixel corners after EXIF correction, output path, manual-edit flag, application/model versions, and crop options in `crop_labels.json`. Accepting a reviewed automatic proposal counts as confirmation; manual selection/handle changes mark it edited. Unattended automatic results are unconfirmed and excluded from export.

点击设置页或工作台“导出确认标签 / Export labels”，选择独立 JSON 文件（默认 `reviewed_labels.json`）。也可在裁剪命令加 `--export-labels`，批次结束后导出已确认条目：

Click Export labels on either page and choose a separate JSON file (default `reviewed_labels.json`). Alternatively, add `--export-labels` to export confirmed entries after processing:

```powershell
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --review --export-labels "D:\裁剪结果\reviewed_labels.json"
```

同一原图按内容哈希去重，重新确认后更新最终标签；无人值守处理不会覆盖已确认标签。导出前核对原图哈希，原图丢失或改变时提示错误。失败补裁优先关联原照片；找不到原照片时，在结果目录 `label_sources/` 保留副本，供以后训练读取，再移除已补裁的失败副本。

Labels are deduplicated by source hash and updated after reconfirmation. Unattended processing cannot overwrite confirmed labels. Export verifies source hashes and reports missing/changed originals. Retry resolves the retained original when possible; otherwise, it keeps a copy under `label_sources/` for future training before removing the successful failure copy.

导出 JSON 可由 `train_screen_model.py` 读取，全部初始标为 `split: train`。训练前仍须检查标签，并将不同拍摄组划分为训练与留出验证；相同图片及其衍生图应属于同一组。导出不自动训练或替换现有模型。真实图片、标签、路径和批次记录仅保存在本地，不在发布文件清单中。详情见 [继续训练](TRAINING.md)。

The exported JSON is readable by `train_screen_model.py`, initially with every row set to `split: train`. Inspect labels and reserve distinct capture groups for holdout before fitting; related derivatives must share a group. Export does not fit or replace models. Photos, labels, paths, and checkpoints stay local and are excluded from the public file manifest. See [training](TRAINING.md).

## 浅色边缘图片 / Pictures with white or faint borders

v0.5.0 自动识别先检查浅色背景中的完整图片边界。无需新开关；原本为正方形的目标继续选择正方形模式，可帮助补全与背景接近的一边。白底文字会尝试按整组内容定位，不做 OCR。普通横图、竖图保持完整图片模式。

v0.5.0 first checks for whole-picture borders on light backgrounds. No new switch is needed. Use Square for originally square targets to help complete a faint side. White-page text is grouped for localization without OCR. Use Full picture for landscape/portrait targets.

若目标只有几个字、大片空白、表格，或白边与背景完全相同，自动框仍可能不完整。请检查预览，直接点击原图重选四角，使用滚轮、选区 Focus 和拖动角点调整。识别耗时变化不包括读图、模型首次加载、预览和写入；详细基准见 [模型说明](MODEL_CARD.md)。

Sparse characters, large blank regions, charts, and white margins indistinguishable from the background can still produce incomplete proposals. Inspect the preview, click the original to reselect corners, and use zoom/Focus/handle dragging. Detection benchmarks exclude image I/O, initial model loading, UI, and saving; see the [model card](MODEL_CARD.md).

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
| `--square` | 关闭 / Off | 将原本正方形的目标完整透视校正为 1:1；裁边后仍保持 1:1。 / Rectify the full originally square target to 1:1, retained after optional trimming. |
| `--recursive` | 关闭 / Off | 包含输入子目录并保留相对目录结构。 / Include input subfolders and preserve relative paths. |
| `--no-trim-black` | 开启 / On | 保留内部暗色内容。 / Preserve dark content inside the crop. |
| `--trim-black` | 关闭 / Off | 开启外围近黑行列清除。 / Enable near-black outer-row/column trimming. |
| `--black-threshold` | `45` | 近黑阈值，范围 `0–255`，仅清黑边时生效。 / Near-black threshold, `0–255`; used only when trimming. |
| `--max-trim` | `0.48` | 每边黑边清除比例上限，范围 `0–0.49`。 / Per-side black-trim limit, `0–0.49`. |
| `--inset` | `0` | 额外向内裁剪比例，范围 `0–0.1`，每侧分别应用。 / Extra inward crop fraction, `0–0.1`, applied to each side. |
| `--overwrite` | 关闭 / Off | 替换已有 PNG 输出。 / Replace existing PNG outputs. |
| `--resume` | 关闭 / Off | 按保存的进度和原选项续裁。 / Resume saved progress with matching options. |
| `--export-labels` | 未设置 / Unset | 批次结束后导出人工确认标签到 JSON。 / Export reviewed labels after processing. |
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
├── manual_crop_report.csv     # Created by --retry-failed
├── crop_session.json          # Progress + unsaved corners
├── manual_crop_session.json   # Retry progress
└── crop_labels.json           # Corners + confirmation metadata
```

输出文件名保留原扩展名，例如 `photo.jpg_cropped.png` 与 `photo.png_cropped.png`，避免同名不同格式冲突。读取原图后按 EXIF 方向校正，输出为 RGB PNG；不会修改输入文件。

Output names retain the original extension, such as `photo.jpg_cropped.png` and `photo.png_cropped.png`, preventing collisions between formats. Images are oriented using EXIF metadata and exported as RGB PNG without modifying input files.

CSV 使用带 BOM 的 UTF-8 编码，可在 Excel 中打开，包含 `input`、`output`、`status`、`detail` 四列。每次保存更新该图片对应的报告条目。新批次重建报告；`--resume` 保留已处理记录。

CSV reports use UTF-8 with BOM for Excel compatibility and contain `input`, `output`, `status`, and `detail`. Each save updates its per-image report row. New batches rebuild reports; `--resume` retains processed records.

| 状态 / Status | 含义 / Meaning |
|---|---|
| `ok` | 本次已保存，`detail` 通常为输出宽×高。 / Saved in this run; `detail` normally contains width × height. |
| `existing` | 输出已存在，本次跳过。 / Output already exists and was skipped. |
| `skipped` | 用户跳过。 / Skipped by the user. |
| `paused` | 已保存草稿和进度，等待续裁。 / Draft and progress retained for Resume. |
| `cancelled` | 用户停止批次，剩余图片不处理；当前图不导出失败副本。 / User stopped the batch; remaining photos are untouched and the current photo is not copied to failures. |
| `error` | 识别、读取或处理失败，原因记录在 `detail`。 / Detection, loading, or processing failed; see `detail`. |

退出码：`0` 表示没有处理错误，`1` 表示批次存在图片处理错误，`2` 表示参数、路径或初始化等错误；用户跳过或已有输出不计为处理错误。

Exit codes: `0` means no processing errors, `1` indicates image-processing errors in the batch, and `2` indicates argument, path, or initialization errors. User skips and existing outputs do not count as processing errors.

## 5. 使用边界与排查 / Limitations and troubleshooting

| 情况 / Situation | 说明与处理 / Explanation and action |
|---|---|
| `[WinError 5] 拒绝访问` / Access denied | 程序预先检查结果目录和成功/失败子目录的创建、写入、重命名及临时文件清理。失败后返回设置并选中结果路径；换一个可写目录后重新开始。若同一目录在资源管理器中可写，可能是当前启动进程受限，关闭旧窗口并双击 `启动裁剪.cmd`。不必为此修改系统目录权限。 / Output folders are checked using actual create/write/rename/cleanup operations. A failure returns to settings with the output path selected. Choose a writable folder and retry. If File Explorer can write there, the current process may be restricted; close it and double-click the launcher. Changing system folder permissions is unnecessary. |
| OpenCV 缺少 `ml.RTrees_create` | 当前解释器的 OpenCV 不兼容。使用启动器自动准备 OpenCV 4.x 独立环境；直接运行脚本也会检测并切换环境。 / The active OpenCV build is incompatible. The launcher prepares an isolated OpenCV 4.x environment; direct execution also detects the issue and switches environments. |
| 初次下载的目录没有 `.crop-env` / Fresh download has no `.crop-env` | 这是正常情况，双击 `启动裁剪.cmd` 即可创建并安装；只安装可用 `安装环境.cmd`。 / This is expected; the launcher creates/installs it, or use the setup-only entry point. |
| 双击 `.py` 打开编辑器或选择程序 / Double-clicking `.py` opens an editor or app picker | Windows 尚未将 Python 文件关联到解释器。使用 `启动裁剪.cmd`，或在终端运行 `python screen_crop.py`。 / Windows has no interpreter association for Python files. Use the `.cmd` launcher or run `python screen_crop.py` in a terminal. |
| 缺少模型或特征版本不一致 / Missing or mismatched model | 自动识别需要与代码匹配的三个模型文件（JSON 元数据和两份压缩权重）；将同一版本的代码与模型放在一起。 / Automatic detection needs all three model files (JSON metadata and two compressed forests) matching the code; keep files from the same version together. |
| 原有结果没有变化 / Existing crops do not change | 已有输出默认跳过，重新处理时使用 `--overwrite`。 / Existing outputs are skipped; use `--overwrite` to regenerate them. |
| 深黑边缘、严重反光或目标太小 / Very dark edges, strong reflections, or tiny targets | 候选生成或边缘定位可能失败，使用 `--review`、`--manual` 或失败补裁。 / Proposal generation or edge localization may fail; review, select corners manually, or retry failures. |
| 灰度图片或几乎无彩色内容 / Grayscale or nearly colorless pictures | 已增加四边边缘和纹理证据，仍可能在真实复杂背景下失败；可手动裁剪。 / Four-border and texture evidence is supported, but complex real backgrounds may still fail; use manual cropping. |
| 输出仍有模糊、反光、摩尔纹或标线 / Blur, glare, moiré, or marks remain | 本项目负责定位、裁剪和透视校正，不恢复被遮挡内容或原始屏幕像素，也不做去模糊、去水印或内容修复。 / The tool locates, crops, and rectifies pictures; it does not recover obscured content or original screen pixels, deblur, remove watermarks, or restore image content. |
| 需要沿人物或物体轮廓抠图 / Need object cutouts | 当前处理完整矩形图片，不输出按物体轮廓分割的透明背景。 / The tool extracts full rectangular pictures, not object silhouettes with transparent backgrounds. |
| 显示 `ok` 但裁错 / A crop is saved but incorrect | `ok` 只表示成功保存，不保证选中了目标区域；检查预览并人工调整。 / `ok` means the file was saved, not that the target was correct; inspect the result and adjust manually. |

项目总览见 [使用说明.md](../README.md)。

For the project overview, see [使用说明.md](../README.md).
