# Screen Photo Crop / 拍屏图片裁切工具

从拍摄的屏幕照片中提取屏幕内的完整图片，自动定位四角、校正透视并保留暗色内容。内置已训练模型，支持同页预览、逐张回车确认、手动重新裁剪及正方形模式。

Extract complete pictures from photographed screens with automatic corner detection, perspective correction, and dark-content preservation. Includes a pretrained model, a single-page preview, Enter-to-save review, manual re-cropping, and square mode.

**Python 3.10+ · OpenCV 4.x · CPU · MIT · v0.8.0**

[使用指南 / Usage](docs/USAGE.md) · [模型与评估 / Model & evaluation](docs/MODEL_CARD.md) · [继续训练 / Training](docs/TRAINING.md) · [发布指南 / Publishing](docs/PUBLISHING.md)

## 功能 / Features

| 中文 | English |
|---|---|
| 定位屏幕内图片本身，支持横图、竖图与透视四边形。 | Locates the picture inside the screen, including landscape, portrait, and perspective-distorted images. |
| 通用森林与反光小目标森林分别包含 240 棵树、24 个特征，选择候选区域并检查边界。 | Base and reflection forests each use 240 trees and 24 features to score candidates and check borders. |
| 新增未标线原照片训练，使用局部反光、运动模糊和透视扰动增强小目标定位。 | Additional training on unmarked photos with glare, motion blur, and perspective augmentations improves small-target localization. |
| 浅色背景先检测完整图片边界，支持白色边缘和有可辨边界的文字图片；普通场景继续使用森林评分。 | A light-background path finds whole-picture boundaries, including white edges and bounded text images; other scenes retain forest scoring. |
| 默认保留黑衣服、黑背景；需要时显式开启黑边清除。 | Preserves dark clothing and backgrounds by default; black-margin trimming is opt-in. |
| 自动批处理、逐张审核、手动选四角、失败补裁。 | Automatic batches, review, manual corners, and failure retries. |
| 黑边识别确认：定位中间目标图片的细黑框，预览、放大或调整四角后，按 Enter 逐张确认保存。 | Black-border review: locate the target picture's thin dark frame, preview/zoom/adjust corners, then press Enter to confirm each crop. |
| 右侧图片状态面板显示已裁、未裁、草稿、跳过、失败和处理进度，可筛选未裁剪图片并双击跳转。 | The image-status panel shows cropped, uncropped, drafts, skipped, errors, and progress; filter uncropped photos and double-click to navigate. |
| 固定坐标：首张确认四角，后续按同一组原图坐标批量导出，无需重复识别或逐张审核；支持暂停续跑。 | Fixed coordinates: confirm corners once, then export remaining photos at the same source-pixel coordinates without detection or review; pause/resume supported. |
| 原图、四角调整与裁剪结果在同一页面；四角有效后自动预览，按一次 Enter 保存并下一张。 | Original, corner editing, and crop preview share one page; valid corners preview immediately, and one Enter saves and advances. |
| 预览就绪后直接点击左侧原图重选四角，点击位置作为第一个点；按住角点拖动仍可微调。 | Click the left original to reselect four corners, using that click as the first point; dragging a handle still adjusts it. |
| 滚轮或 +/− 缩放原图，空格+左键/中键拖移，选区 Focus 放大角点，适应 Fit 恢复全图。 | Zoom with the wheel or +/−, pan with Space+left drag or middle drag, focus corners, and fit the full image. |
| 开始时可选择正方形模式，按完整四角透视校正为 1:1。 | Select square mode at startup to rectify the complete four-corner region to 1:1. |
| 灰度与低对比度候选增加四边和纹理证据，保留原彩色识别路径。 | Add four-border and texture evidence for grayscale/low-contrast candidates while retaining the original color path. |
| 保存原图标识和最终四角，记录人工修改及版本信息，导出人工确认标签用于后续训练。 | Record source identity, final corners, edit flags, and versions; export reviewed labels for later training. |
| 上一张修改、可点击缩略图、记忆目录/模式、暂停后恢复草稿和批次进度。 | Previous-image editing, clickable thumbnails, remembered settings, and resumable drafts/progress. |
| 支持子目录、中文路径、EXIF 方向校正和常见图像格式。 | Supports subfolders, Unicode paths, EXIF orientation, and common image formats. |
| 输出 PNG、成功/失败分目录、CSV 记录和可选识别框预览。 | Produces PNG crops, separate success/failure folders, CSV reports, and optional overlays. |

图像处理在本地 CPU 上运行，无需显卡、账号或在线接口。安装依赖需要下载软件包；预训练模型随项目提供，无需重新训练。

Image processing runs locally on the CPU without a GPU, account, or online API. Installing dependencies downloads packages; the bundled model requires no retraining.

## 快速开始 / Quick start

下载并解压发布包，或克隆仓库，在项目根目录执行命令。主程序和三个模型文件（JSON 元数据和两份压缩权重）应保持在一起，模型压缩文件无需解压。

Download and extract a release or clone the repository, then run commands from the project root. Keep the main script and all three model files (JSON metadata and two compressed forests) together; leave the model compressed.

### 准备照片与项目文件 / Prepare the photos and project

1. 下载仓库 ZIP 或发布包并**完整解压**。打开包含 `启动裁剪.cmd`、`screen_crop.py` 和 `crop_ui.py` 的文件夹；不要只复制一个脚本，也不要直接在 ZIP 中运行。 / Download the repository ZIP or release archive and **extract everything**. Open the folder containing `启动裁剪.cmd`, `screen_crop.py`, and `crop_ui.py`; do not copy only one script or run inside the ZIP.
2. 安装 Python 3.10 或更新版本。Windows 的 `.cmd` 启动器需要能找到可用的 Python；安装后在终端运行 `python --version` 可检查是否可用。 / Install Python 3.10 or later. The Windows `.cmd` launcher needs a discoverable Python installation; check it with `python --version` in a terminal.
3. 创建原照片文件夹，例如 `D:\拍屏照片`，把要处理的 JPG、PNG 等照片放进去。项目不会自动生成你的照片目录，也不附带真实训练原图。 / Create a source folder such as `D:\拍屏照片` and put your JPG/PNG photos there. Your source folder is not created automatically, and real training photos are not bundled.
4. 为结果选择另一个目录，例如 `D:\裁剪结果`。新批次的输入、输出必须不同；命令行可自动创建结果目录，窗口“选择 / Browse”通常需要先建立要选择的文件夹，也可直接在结果栏填写新路径。 / Choose a separate result folder, such as `D:\裁剪结果`. Input and output must differ. The CLI can create a result folder; the Browse dialog normally selects an existing folder, so create it first or type a new path into the Results field.

建议的目录结构 / Suggested folder layout:

```text
Screen-Photo-Crop-/              # 解压后的项目 / Extracted project
├── 启动裁剪.cmd
├── 安装环境.cmd
├── launch_crop.py
├── screen_crop.py
├── crop_ui.py
├── screen_crop_model.json
├── screen_crop_forest.xml.gz     # 保持压缩状态 / Keep compressed
└── ...                         # 其余项目文件 / Other project files

D:\拍屏照片\                    # 自己的原照片 / Your source photos
├── 照片01.jpg
└── 照片02.png

D:\裁剪结果\                    # 结果总目录 / Result root
```

### Windows

安装 Python 3.10 或更新版本后，直接双击 **启动裁剪.cmd**。首次启动会在本目录创建 `.crop-env` 并下载依赖，完成后自动打开裁剪工具；后续启动直接复用环境。也可以在终端运行：

Install Python 3.10 or later, then double-click **启动裁剪.cmd**. The first launch creates `.crop-env` here and downloads dependencies before opening the tool. Later launches reuse the environment. You can also run:

```powershell
.\启动裁剪.cmd
```

如果只想提前安装环境、不打开裁剪窗口，可双击 **安装环境.cmd**。首次安装需要联网；项目不会携带其他电脑的虚拟环境。

To prepare the environment without opening the cropper, double-click **安装环境.cmd**. Initial setup needs internet access; the project does not ship another computer's virtual environment.

如果电脑已有 `uv`，启动器会使用它安装依赖；否则使用 Python 自带的 `pip`，不需要额外安装 `uv`。

The launcher uses `uv` if already available, otherwise Python's bundled `pip`. Installing `uv` is optional.

手动安装方式仍可使用 / Manual setup is also available:

```powershell
python -m venv .crop-env
.\.crop-env\Scripts\python.exe -m pip install -r requirements.txt
.\.crop-env\Scripts\python.exe screen_crop.py
```

启动设置页选择输入目录、输出目录、处理方式和图片形状；正方形图片请选择“正方形 · 1:1”。源照片不会被修改。直接运行 `screen_crop.py` 时，缺少依赖或 OpenCV 版本不兼容会自动切换到项目环境；双击 `.py` 文件还依赖 Windows 的 Python 文件关联，推荐使用 `.cmd` 入口。

Choose source/output folders, workflow, and picture shape on the startup page. Select Square · 1:1 for originally square pictures. Source photos are not modified. Direct execution of `screen_crop.py` detects missing/incompatible dependencies and switches to the project environment. Double-clicking `.py` additionally requires a Windows Python file association, so the `.cmd` launcher is recommended.

### 第一次使用：从设置到保存 / First use: settings to saved crops

**以自动审核一批照片为例 / Example: review a new batch**

1. 双击 `启动裁剪.cmd`。首次启动等待终端完成依赖安装，再进入“开始一批裁剪”设置页；已安装好环境时会直接复用。 / Double-click `启动裁剪.cmd`. On first launch, wait for dependency setup to finish and the startup page to open; a ready environment is reused.
2. 在“原照片 / Photos”选择或填写 `D:\拍屏照片`，在“结果目录 / Results”填写 `D:\裁剪结果`。 / Choose or enter `D:\拍屏照片` in Photos and `D:\裁剪结果` in Results.
3. 处理方式选择“自动识别 · 逐张确认 / Review”。普通横图、竖图选择“完整图片 / Full picture”；目标本来是正方形时选择“正方形 · 1:1 / Square”。 / Select Review. Use Full picture for landscape/portrait targets, or Square · 1:1 for originally square targets.
4. 首次处理通常保持“覆盖旧结果”和“清除黑边”关闭。有多层照片目录时勾选“包含子目录”，需要检查识别边界时勾选“保存识别框”。然后点击“开始裁剪”。 / Usually leave Overwrite and Trim black off for the first run. Enable Recursive for subfolders and Debug for saved boundary overlays, then click Start cropping.
5. 等待当前照片识别完成。左侧显示原照片与四个角点，右侧显示最终裁剪预览；上方显示当前文件名和批次序号，右下显示输出像素尺寸及是否已保存。 / Wait for detection. The original and four handles appear on the left; the final crop appears on the right. The filename/counter is above, and the output size/save state is below the preview.
6. 检查右侧是否保留完整目标、是否仍有屏幕边框。结果正确时**按一次 Enter**，或点击“保存并下一张”；结果不正确时直接点击左侧原图，从这次点击开始重选四角，也可拖动角点微调。 / Check that the whole target is included and unwanted screen borders are excluded. **Press Enter once** or click Save & next to accept; otherwise click the left original to start a new four-point selection, or drag handles to adjust.
7. 每张照片分别确认。生成预览不会写入裁剪文件，也不会自动进入下一张。最后一张完成后，无参数启动的工作台会保留批次结果页；点击“返回设置”可开始下一批。 / Confirm each photo separately. Generating a preview neither saves a crop nor advances automatically. When launched without arguments, the workspace stays on the result page after the last photo; Settings starts another batch.
8. 打开 `D:\裁剪结果\裁剪成功` 查看 PNG。如果有跳过或处理失败的照片，到设置页选择“失败图片补裁”，继续手动处理。 / Open `D:\裁剪结果\裁剪成功` to inspect the PNG files. Use Retry failures on the startup page to manually handle skipped or failed photos.

**如何选择处理方式 / Choosing a workflow**

| 需求 / Need | 设置页 / Startup choice | 命令行 / CLI | 运行行为 / Behavior |
|---|---|---|---|
| 首次处理，逐张检查 / Inspect a new collection | 自动识别 · 逐张确认 / Review | `--review` | 自动选四角，同页检查，Enter 保存下一张。 / Automatic corners; inspect and press Enter to save and advance. |
| 自己决定每张图片边界 / Select every boundary yourself | 手动四角 · 逐张确认 / Manual | `--manual` | 不进行自动识别，手动选四角后预览并保存。 / No automatic detection; choose four corners, preview, and save. |
| 中间图片周围有细黑框 / A thin dark frame around the target | 黑边识别 · 逐张确认 / Black-border review | `--black-review` | 定位四边后预览，手动确认每一张；无可信边界时手动选点。 / Propose four borders and confirm every crop; select points manually if no reliable frame is found. |
| 相机和目标位置固定 / Fixed camera and target position | 固定坐标 · 首张确认后批量导出 / Fixed coordinates | `--fixed` | 仅首张确认，后续相同尺寸照片直接复用四角。 / Confirm once; reuse corners for same-size source photos. |
| 继续处理失败或跳过的照片 / Handle failed/skipped photos | 失败图片补裁 / Retry failures | `RESULT_ROOT --retry-failed` | 使用上次结果总目录，递归手动处理其中的失败副本。 / Use the previous result root and manually process its failure copies recursively. |
| 已确认场景，直接自动批处理 / Run an automatic batch | 使用命令行 / Use CLI | 不加模式参数 / Omit workflow flags | 不显示逐张窗口，识别成功后直接保存。 / No per-photo window; detected crops are saved immediately. |

### 黑边识别后逐张确认 / Review thin black borders before saving

当目标照片或文字图片周围有细黑框时，在设置页选择 **“黑边识别 · 逐张确认”**。程序定位中间图片的四条边，左侧显示四角，右侧显示裁剪预览。检查是否保留完整人物或文字，可滚轮放大、拖动角点，或直接点击原图重选四角。确认正确后按 **Enter** 或“确认保存并下一张”；每一张都需要确认，生成预览不会自动保存。

Select **Black-border review** when a photo or text picture has a thin dark outline. The application proposes the central picture's four borders and shows the crop preview. Check that the whole subject/text is retained; zoom, drag handles, or click the original to reselect corners. Press **Enter** or Confirm & next to save. Every image requires confirmation; previewing alone never saves a crop.

```powershell
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --black-review
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --black-review --square
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --black-review --square --resume
```

别名为 `--black-border-review`。适合浅色屏幕背景上的细黑框，照片和文字图片均可；不以最外侧整块显示屏为目标。默认保留照片内部的暗色内容，无需开启“清除黑边”。未检测到可信四边时，可手动选择四点后确认。支持暂停恢复、上一张修改、失败补裁和人工确认标签。原本为正方形的目标请选择 Square，可帮助区分完整外框和内部表格线；边界明显不完整时会有条件地尝试现有通用模型，模型权重不变。

`--black-border-review` is an alias. This mode suits thin dark outlines on a lighter screen background, including photographic and text content; it targets the inner picture. Dark content inside the picture is retained by default, so Trim black is unnecessary. Select four points manually if detection is uncertain. Pause/Resume, Previous, failure retries, and reviewed labels remain available. Select Square for an originally square target to help distinguish the full frame from interior table lines; visibly incomplete proposals can conditionally use the existing general model. Forest weights are unchanged.

### 图片状态和裁剪进度 / Image status and crop progress

开始或继续批次后，右侧显示当前文件夹的图片列表及 **已裁、未裁、草稿、跳过、失败、已处理** 数量。下拉框可筛选“未裁剪”，其中包括尚未处理、跳过或失败且没有成功输出的图片；双击条目可跳转到该图片。点击“刷新”重新检查结果目录中的文件。底部进度条表示已有裁剪结果的比例。

After starting or resuming a batch, the right panel lists the folder's images and counts **cropped, uncropped, drafts, skipped, errors, and processed**. Filter No crop to find images without a successful output, including pending, skipped, and failed photos; double-click a row to navigate. Refresh rescans output files. The bottom progress bar shows the proportion with cropped results.

“已裁”按 `裁剪成功` 中实际存在的输出文件统计；“已处理”按本批次记录统计，包含跳过和失败，因此两者可能不同。已有结果但正在重新调整的图片会标记为“已裁·草稿”；记录显示成功但文件已被移走时，显示“结果缺失”。固定坐标模式仍需开始新批次才能更改统一坐标。

Cropped counts actual files in `裁剪成功`; Processed uses batch records and includes skipped/errors, so the totals can differ. An existing crop with an unfinished edit is marked Saved·Draft; a successful record with a missing file is marked Missing. Fixed-coordinate batches still require a new batch to change their shared corners.

### 固定坐标：确认一次，批量导出 / Fixed coordinates: confirm once, export a batch

适用于相机、屏幕和目标位置不变的一批照片。设置页选择 **“固定坐标 · 首张确认后批量导出”**，选择完整图片或正方形，然后开始裁剪。首张待处理照片会给出自动四角；可直接点击原图重选四点，滚轮放大或拖动角点，检查右侧预览后按 **Enter** 或“确认坐标并批量导出”。后续图片不再识别、不再等待回车，直接按这四个原图像素坐标校正并保存到 `裁剪成功`。

Use this for photos with an unchanged camera, screen, and target position. Select **Fixed coordinates** and Full picture or Square on the startup page. Check the first pending photo's proposed corners, click to reselect, zoom, or drag handles as needed. Press **Enter** or Confirm & export. Remaining photos reuse those four source-pixel coordinates and save directly to `裁剪成功`, without detection or further confirmation.

```powershell
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --fixed
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --fixed --square
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --fixed --square --resume
```

坐标基于 EXIF 方向校正后的原图，所有照片尺寸必须一致；不同尺寸会记为失败并保留副本，程序继续处理其余照片。即使尺寸相同，相机移动或目标位置变化也会导致裁错，此时应使用逐张审核。固定模式支持暂停、结束、关闭后续跑；坐标保存在 `crop_session.json`，续跑无需再次确认。默认跳过已有结果，替换时加 `--overwrite`。修改固定坐标需返回设置开始新批次；首张有效、未跳过的待处理照片作为参考。只有实际确认的参考照片属于人工审核标签，后续复用坐标的结果不会自动加入人工确认训练集。

Coordinates refer to the original after EXIF orientation. Source dimensions must match; mismatches enter the failure report/folder while other photos continue. Camera or target movement can still cause wrong crops at the same resolution; use Review for those collections. Pause, Stop, Close, and Resume retain corners in `crop_session.json`; resuming needs no further confirmation. Existing results are skipped unless `--overwrite` is supplied. Start a new batch to change corners; the first valid, unskipped pending photo becomes the reference. Only that explicitly confirmed reference is a reviewed training label; coordinate reuse does not mark later photos as human-reviewed.

**设置页的可选项 / Optional startup settings**

| 选项 / Option | 何时开启 / When to enable |
|---|---|
| 包含子目录 / Recursive | 原照片分放在批次等子文件夹中；结果保留相对目录结构。 / Photos are organized in subfolders; relative paths are retained. |
| 覆盖旧结果 / Overwrite | 已有对应裁剪文件，想重新审核或替换它。保存新结果才会替换；跳过或结束不覆盖。 / You want to review/replace an existing crop. Replacement occurs only when a new crop is saved; skipping/stopping leaves it unchanged. |
| 保存识别框 / Debug | 额外保存带四角轮廓的原照片，便于排查裁错的位置。 / Save extra original-image overlays to inspect the chosen corners. |
| 清除黑边 / Trim black | 四角校正后目标内部仍有不需要的黑色留边。默认关闭，以免裁掉黑衣服、黑背景等真实内容。 / Remove unwanted black padding inside the rectified target. Off by default to preserve dark clothing/backgrounds. |

**失败补裁的设置 / Setting up failure retries**

在设置页选择“失败图片补裁”，把**结果目录栏**填写为上次结果总目录 `D:\裁剪结果`；原照片栏此时不用于新批次。若结果栏留空，程序会使用原照片栏中的路径作为结果总目录。不要填写 `D:\裁剪结果\裁剪失败`，也不要填写最初的原照片目录。补裁仍可选择正方形模式，并使用同页预览和 Enter 确认。

Select Retry failures and enter the previous result root, `D:\裁剪结果`, in the **Results field**. The Photos field is not used as a new source in this mode; if Results is empty, the Photos path is treated as the result root. Do not select `D:\裁剪结果\裁剪失败` or the original source folder. Square mode, the same-page preview, and Enter confirmation remain available.

保存补裁结果后，只移除对应的失败副本，最初的原照片仍保留。跳过或结束时失败副本会保留，便于下一次继续处理。若对应成功文件已存在，需勾选“覆盖旧结果”才能重新处理。

Saving a retry removes only its corresponding failure copy; the initial source remains. Skipping/stopping retains the failure copy for another retry. Enable Overwrite if the corresponding successful crop already exists.

### macOS / Linux

```bash
python3 -m venv .crop-env
.crop-env/bin/python -m pip install -r requirements.txt
.crop-env/bin/python screen_crop.py input output
```

input 目录需自行创建并放入照片。交互窗口需要 Tkinter 和桌面环境。Windows 为主要桌面使用环境；macOS 桌面交互未纳入 CI。

Create input and add your photos. Interactive windows require Tkinter and a desktop session. Windows is the primary desktop environment; macOS desktop interaction is not covered by CI.

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

相对路径从终端当前目录解释。例如在项目目录执行 `python screen_crop.py input output --review`，会读取项目内的 `input` 文件夹并写入 `output`。找不到 `input` 时，先创建并放入照片，或改用下面的绝对路径示例。也可用 `启动裁剪.cmd` 传入相同参数，让启动器选择项目独立环境：

Relative paths are interpreted from the terminal's working directory. Running `python screen_crop.py input output --review` in the project folder reads its `input` folder and writes to `output`. Create/populate `input` first or use the absolute paths below. The Windows launcher can forward the same arguments while selecting the project environment:

```powershell
.\启动裁剪.cmd "D:\拍屏照片" "D:\裁剪结果" --review
.\启动裁剪.cmd "D:\拍屏照片" "D:\裁剪结果" --manual --square
```

`启动裁剪.cmd` 会先进入它所在的项目目录，所以向它传相对路径时，以该项目目录为基准。

`启动裁剪.cmd` first changes to its own project folder, so relative paths passed to it are relative to that folder.

### 1. 自动识别后逐张审核 / Review automatic crops

自动识别后，左侧显示原图和四角，右侧直接显示裁剪预览。需要重新裁剪时，直接点击左侧原图的第一个新角点，接着选择其余三个点，无需先点击“重新裁剪”；也可拖动角点微调。检查结果后按一次 Enter 保存并进入下一张，适合首次处理一批新照片。

Automatic detection shows the original and corners on the left and the crop preview on the right. Click the first new corner on the left original, then select the other three; no Re-crop button is needed. You can also drag handles to adjust. Press Enter once to save and advance. Use this when processing a new collection.

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
screen_crop.py 0.2.1
```

### 正方形模式 / Square mode

启动页选择“正方形 · 1:1”，或在命令中加 `--square`。它适用于目标原本是正方形的照片：保留四角内的完整内容并校正为 1:1，不从中间截取方形。普通横图/竖图应保持完整图片模式；选错形状可能造成拉伸。审核、手动、失败补裁和自动批处理均支持此参数。

Choose Square · 1:1 at startup, or add `--square`. This mode rectifies the complete four-corner region to 1:1 for originally square pictures, without taking a center crop. Use Full picture for landscape/portrait targets; choosing the wrong shape can stretch content. All processing modes support this option.

这里判断的是**屏幕内目标图片的形状**，不是相机拍下整张照片的形状。即使整张手机照片是长方形，只要其中的目标原本是正方形，就可使用正方形模式。该设置应用于整批图片；混合横图、竖图和正方形目标时，建议分批处理。

This refers to the **picture displayed inside the screen**, not the shape of the entire camera photo. A rectangular camera photo can still contain an originally square target. The setting applies to the whole batch; process square targets separately from landscape/portrait targets in mixed collections.

```powershell
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --review --square
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --manual --square
python screen_crop.py "D:\裁剪结果" --retry-failed --square
```

### 窗口操作 / Window controls

| 操作 / Action | 中文 | English |
|---|---|---|
| 四角 / Corners | 自动框直接生成右侧预览；手动点击四角后也自动预览。拖动角点调整。 | Automatic corners preview immediately; four manual points also preview automatically. Drag handles to adjust. |
| 点击左侧原图 / Click original | 已有四角时，单击直接重选并记为第一个点，旧预览清除；角点上单击也可重选，按住拖动则微调。 | With four corners selected, a click restarts at that first point and clears the old preview. Clicking a handle also restarts; dragging adjusts it. |
| Enter | 检查预览后按一次，保存当前图并进入下一张；未选四角时不保存。 | Press once after inspection to save and advance; incomplete selections cannot save. |
| 重新裁剪 / Re-crop · R | 清空当前四角和预览，在同一张原图重新选点。 | Clear corners and preview, then reselect on the same original. |
| 撤销 / Undo · 右键 / Right click · Backspace | 撤销一个点；重新选四角前不能保存旧预览。 | Undo one point; stale previews cannot be saved. |
| 跳过 / Skip · Esc | 当前图片进入失败副本目录，继续下一张，不写入新裁剪。 | Copy the skipped source to failures and advance without writing a crop. |
| 结束 / Stop · 关闭窗口 / Close | 停止本批，保留已经保存的结果；当前及剩余图片不导出失败副本。 | Stop the batch and retain saved results; current/remaining photos are not exported as failures. |

审核、手动和失败补裁使用同一工作台。自动批处理不弹出预览。已有输出默认跳过，重新审核时加 `--overwrite`。

Review, manual, and retry modes use the same workspace. Automatic batches have no preview window. Existing outputs are skipped; add `--overwrite` to review them again.

### 手动选四角与拖动调整 / Selecting and adjusting corners

1. 审核时先等待识别结束。如果自动框不正确，直接在左侧原图点击第一个新角点，即可清除旧框和预览、开始重选；手动模式和失败补裁一开始就等待你选点。 / In Review, wait for detection to finish. If the proposal is wrong, click the first new corner on the left original to clear the old selection/preview and start over. Manual and Retry start by waiting for your points.
2. 在**左侧原图**依次点击目标图片本身的左上、右上、右下、左下角。选择屏幕内要提取的图片边界，不要选择手机照片四角、显示器外框或工具栏。 / On the **left original**, click the target picture's top-left, top-right, bottom-right, and bottom-left corners. Select the picture inside the screen, rather than the camera-photo corners, monitor bezel, or toolbar.
3. 选四个有效角点后，右侧自动显示透视校正结果。不到四点、点重复或选区过小时，保存按钮不会启用；此时按 Enter 也不会保存。 / Four valid points automatically produce the rectified preview. Fewer than four points, duplicates, or a very small region cannot enable saving; Enter does not save an invalid selection.
4. 点错时点击“撤销”、按 Backspace 或右键撤销一个点；四角都已选好后，可按住某个角点拖到正确位置。**松开鼠标后**重新计算预览，拖动过程中不能保存。需要从头重选时直接单击左侧原图；“重新裁剪”按钮和 R 快捷键仍可清空选点。 / Undo a wrong point with the Undo button, Backspace, or right-click. With four points selected, drag a handle to the correct location. The preview updates **after releasing the mouse**; saving is disabled during a drag. Click the left original to start over; Re-crop and R remain available to clear the selection.
5. 查看右侧最终结果和尺寸。确认后按一次 Enter，或点击“保存并下一张”。重新裁剪和撤销不会保存之前的预览；每次保存的都是当前有效四角对应的结果。 / Inspect the final preview and dimensions, then press Enter once or click Save & next. Re-crop and Undo cannot save a stale preview; saving always uses the current valid corners.

### 放大后精确裁剪 / Precise cropping with zoom

审核、手动裁剪和失败补裁均可放大**左侧原图**。滚轮向上放大、向下缩小，围绕鼠标位置缩放；也可点击 `+` / `−`，范围为适应窗口的 1–16 倍。右侧预览保持完整裁剪结果。

Zoom the **left original** in Review, Manual, and Retry. Wheel up/down zooms around the pointer; `+` / `−` also work. Zoom ranges from 1× fit to 16×. The right preview continues to show the complete crop.

| 操作 / Action | 方法 / How |
|---|---|
| 放大自动框 / Enlarge the detected region | 点击“选区 Focus”，至少已有两个点时可用。 / Click Focus after selecting at least two points. |
| 查看放大后的其他区域 / Pan | 在原图上按住空格并用左键拖动，或按住鼠标中键拖动。 / Hold Space and drag with the left button, or drag with the middle button. |
| 重选四角 / Reselect | 放大后直接单击原图第一个新角点，再依次选择其余三点。 / Click the first new corner in the zoomed original, then choose the other three. |
| 微调边界 / Adjust | 按住角点拖动，松开后更新预览。 / Drag a handle; release to update the preview. |
| 恢复全图 / Fit | 点击“适应 Fit”，查看所有角点。 / Click Fit to view all corners. |
| 保存并下一张 / Save and advance | 确认右侧结果后按一次 Enter；下一张自动恢复全图。 / Check the preview and press Enter once; the next photo starts fitted. |

缩放、拖移只改变显示视野，角点和输出始终使用原图坐标；放大不会增加原照片的细节。为避免误重选，移动视野时请使用空格或中键拖动。

Zoom/pan changes the view while corners and output remain in source coordinates. Zoom cannot add missing image detail. Use Space or the middle button when moving the view to avoid starting a new selection.

识别过程中，“保存”“重新裁剪”和“撤销”暂不可用；你可以等待，或使用“跳过”“结束”。若识别没有找到目标或提示不可用，工作台会允许手动选四角。终端命令启动的审核/手动窗口会在该批结束后关闭；无参数启动则保留完成页面供查看。

During detection, Save, Re-crop, and Undo are temporarily unavailable; wait, Skip, or Stop. If detection finds no target or is unavailable, you can select corners manually. Review/Manual windows launched with CLI arguments close when their batch ends; launching without arguments retains the completion page.

支持 JPG/JPEG、PNG、BMP、TIF/TIFF、WebP。输出示例：photo.jpg → output/裁剪成功/photo.jpg_cropped.png；失败或跳过的原图副本进入 output/裁剪失败/。详见 [完整参数与黑边设置](docs/USAGE.md)。

Supported inputs: JPG/JPEG, PNG, BMP, TIF/TIFF, and WebP. Example: photo.jpg → output/裁剪成功/photo.jpg_cropped.png. Failed/skipped source copies go to output/裁剪失败/. See [all options and black-margin settings](docs/USAGE.md).

## 查看结果、黑边设置与继续处理 / Results, black margins, and resuming

### 保存位置和报告 / Saved files and reports

```text
D:\裁剪结果\
├── 裁剪成功\
│   ├── 照片01.jpg_cropped.png
│   └── 批次01\照片02.png_cropped.png   # 使用 --recursive / With --recursive
├── 裁剪失败\
│   └── 照片03.jpg                     # 失败或跳过的原图副本 / Failed/skipped original copy
├── _debug\                           # 仅使用 --debug 时 / Only with --debug
│   └── 裁剪成功\照片01.jpg_cropped.png
├── crop_report.csv                    # 新批次 / Normal batch
└── manual_crop_report.csv             # 失败补裁 / Failure retry
```

成功结果是 PNG，文件名保留原扩展名，再追加 `_cropped.png`，因此 `照片.jpg` 与 `照片.png` 不会互相覆盖。`_debug` 内的是带边界的原照片，真正的裁剪结果位于“裁剪成功”。输出按 EXIF 方向读取原图，最初的输入照片保持不变。

Successful crops are PNGs named with the original extension plus `_cropped.png`, so `photo.jpg` and `photo.png` cannot collide. `_debug` contains originals with corner overlays; actual crops are in `裁剪成功`. Source orientation follows EXIF metadata, and initial source files are unchanged.

CSV 可用文本编辑器或 Excel 打开，包含 `input`（相对原文件路径）、`output`（相对结果路径）、`status`（状态）、`detail`（尺寸或原因）。每次保存更新对应条目；续裁保留已处理记录，新批次重建报告。若需历史快照，请先复制报告。

Open CSV reports in a text editor or Excel. Their columns are `input` (relative source path), `output` (relative result path), `status`, and `detail` (dimensions or explanation). Each save updates its row; Resume retains processed records and a new batch rebuilds the report. Copy reports for historical snapshots.

| 状态 / Status | 含义与下一步 / Meaning and next step |
|---|---|
| `ok` | 已保存本次裁剪。它只表示保存成功，仍应检查目标是否准确。 / Crop saved in this run; inspect whether the target was correctly localized. |
| `existing` | 对应成功文件已经存在，未重新处理。需要重做时开启覆盖。 / A successful output already exists and was skipped; enable Overwrite to redo it. |
| `skipped` | 用户主动跳过，失败副本保留用于补裁。 / User skipped the photo; the failure copy remains for retry. |
| `error` | 读取、识别或处理失败，详情见 `detail`；可尝试手动补裁。 / Loading, detection, or processing failed; see `detail` and try manual retry. |
| `paused` | 当前草稿及进度已保留，点击继续恢复。 / Current draft/progress retained for Resume. |
| `cancelled` | 用户停止本批；当前及剩余图片没有因此导出到失败目录。 / User stopped the batch; this does not copy current/remaining photos into failures. |

### 黑边与内缩 / Black margins and inset

默认根据四角移除目标周围的屏幕区域，**不会继续按黑色行列裁去图片内部暗色内容**。人物穿黑衣、黑背景等照片通常保持“清除黑边”关闭。若校正后确有不需要的纯黑留边，才勾选该项或使用 `--trim-black`；预览显示的是包含当前清黑边/内缩设置的最终结果。

By default, the corners remove the surrounding screen area while **dark rows/columns inside the picture remain**. Usually leave Trim black off for dark clothing/backgrounds. Enable it or add `--trim-black` only for unwanted black padding. The preview includes the current trimming/inset settings.

下面是额外参数的示例。`--black-threshold 45` 认定三个通道均不超过 45 的像素为近黑；`--max-trim 0.10` 把每边清黑边的上限设为对应尺寸的 10%；`--inset 0.005` 在每一侧额外向内裁约 0.5%。清黑边只移除外围连续、近黑像素占比至少 90% 的行列。

For the extra options below, `--black-threshold 45` treats a pixel as near-black when all channels are at most 45; `--max-trim 0.10` limits black trimming on each side to 10% of its dimension; `--inset 0.005` additionally crops inward by about 0.5% on each side. Black trimming removes only consecutive outer rows/columns with at least 90% near-black pixels.

```powershell
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --review --trim-black --black-threshold 45 --max-trim 0.10
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --review --inset 0.005
```

自动识别的边缘细化本身会向内微调约 0.5–2 个检测图像像素，以减轻插值残边；它独立于 `--inset`，手动选四角不执行该自动细化。正方形模式启用清黑边/内缩后，最终结果仍调整为 1:1。完整参数范围见 [使用指南](docs/USAGE.md)。

Automatic edge refinement itself adds an inward adjustment of about 0.5–2 detection-image pixels to reduce interpolation fringes. This is separate from `--inset`; manual corners bypass automatic refinement. Square mode keeps the final output at 1:1 after trimming/inset. See the [usage guide](docs/USAGE.md) for parameter ranges.

### 批次管理与人工标签 / Batch management and reviewed labels

#### 返回修改与缩略图 / Revisiting and thumbnails

底部“上一张修改 / Previous”返回上一张原照片，载入已保存四角。底部缩略图列表可横向滚动，单击任一图片可以跳转；已有结果显示裁剪缩略图，未完成图片显示原图，当前项以紫色边框突出。批次完成后仍可点击缩略图重新修改。

Previous reopens the previous original with saved corners. Scroll the bottom thumbnail strip horizontally and click any image to jump. Saved items show crop thumbnails, pending items show originals, and the current item has a purple border. Thumbnails remain editable after batch completion.

四角恢复适用于 v0.4.0 保存过标签的图片；旧版只有 PNG、没有四角记录时，重新审核会识别边界，手动模式需要重新选点。 / Corner restoration requires labels saved by v0.4.0; older PNG-only results need detection in Review or new points in Manual.

跳转会保留当前未保存选点为草稿；旧 PNG 和已确认标签只在再次按 Enter 或“保存并下一张”后更新。返回旧结果后选择“跳过”会放弃该次编辑并保留旧结果。保存后继续处理后面的未完成图片；提前跳到后面时，批末会回到遗漏的待处理图片。

Navigation retains unsaved points as drafts. Old PNGs and confirmed labels change only after Save & next or Enter. Skipping a revisited crop discards those edits while retaining its previous output. Saving continues through remaining work; jumping forward does not abandon earlier pending items.

#### 记忆设置、暂停与恢复 / Remembered settings, pause, and resume

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

#### 将人工确认结果导出为训练标签 / Exporting reviewed training labels

每次确认保存，结果目录 `crop_labels.json` 记录原图路径及 SHA-256、EXIF 校正后的原图四角坐标、输出路径、是否人工修改、程序/模型版本及裁剪选项。审核中直接接受自动框也属于人工确认；手动选点和拖动角点标记为人工修改。无人值守自动结果标记为未确认，导出时排除。

Every confirmed save records source path/hash, source-pixel corners after EXIF correction, output path, manual-edit flag, application/model versions, and crop options in `crop_labels.json`. Accepting a reviewed automatic proposal counts as confirmation; manual selection/handle changes mark it edited. Unattended automatic results are unconfirmed and excluded from export.

点击设置页或工作台“导出确认标签 / Export labels”，选择独立 JSON 文件（默认 `reviewed_labels.json`）。也可在裁剪命令加 `--export-labels`，批次结束后导出已确认条目：

Click Export labels on either page and choose a separate JSON file (default `reviewed_labels.json`). Alternatively, add `--export-labels` to export confirmed entries after processing:

```powershell
python screen_crop.py "D:\拍屏照片" "D:\裁剪结果" --review --export-labels "D:\裁剪结果\reviewed_labels.json"
```

同一原图按内容哈希去重，重新确认后更新最终标签；无人值守处理不会覆盖已确认标签。导出前核对原图哈希，原图丢失或改变时提示错误。失败补裁优先关联原照片；找不到原照片时，在结果目录 `label_sources/` 保留副本，供以后训练读取，再移除已补裁的失败副本。

Labels are deduplicated by source hash and updated after reconfirmation. Unattended processing cannot overwrite confirmed labels. Export verifies source hashes and reports missing/changed originals. Retry resolves the retained original when possible; otherwise, it keeps a copy under `label_sources/` for future training before removing the successful failure copy.

导出 JSON 可由 `train_screen_model.py` 读取，全部初始标为 `split: train`。训练前仍须检查标签，并将不同拍摄组划分为训练与留出验证；相同图片及其衍生图应属于同一组。导出不自动训练或替换现有模型。真实图片、标签、路径和批次记录仅保存在本地，不在发布文件清单中。详情见 [继续训练](docs/TRAINING.md)。

The exported JSON is readable by `train_screen_model.py`, initially with every row set to `split: train`. Inspect labels and reserve distinct capture groups for holdout before fitting; related derivatives must share a group. Export does not fit or replace models. Photos, labels, paths, and checkpoints stay local and are excluded from the public file manifest. See [training](docs/TRAINING.md).

## 常见问题 / Troubleshooting

| 现象 / Symptom | 处理方法 / Action |
|---|---|
| `[WinError 5] 拒绝访问` / Access denied | 新版在开始前预检结果目录写入能力。选择可写目录重试；如果从受限终端或自动化工具启动，关闭旧窗口，从资源管理器双击 `启动裁剪.cmd`。失败时会显示具体路径并返回设置，原照片和已有批次记录保留。 / Output writes are checked before processing. Choose a writable folder, or relaunch the launcher from File Explorer if the current process is restricted. The error identifies the path and returns to settings, retaining originals/checkpoints. |
| 双击 `.py` 打开编辑器 / A `.py` file opens an editor | 改用 `启动裁剪.cmd`，或使用项目解释器运行 `screen_crop.py`。 / Use `启动裁剪.cmd` or run `screen_crop.py` with the project interpreter. |
| 提示未找到 Python / Python not found | 安装 Python 3.10+，重新打开终端，检查 `python --version`，再启动。 / Install Python 3.10+, open a new terminal, check `python --version`, then relaunch. |
| 首次安装失败或没有弹出工作台 / Setup fails or no workspace opens | 查看终端报错和联网状态；可运行 `安装环境.cmd` 单独安装，或采用上面的手动安装命令。 / Inspect terminal errors/connectivity; try the setup-only launcher or manual setup above. |
| 没有 `.crop-env` / No `.crop-env` folder | 新下载的项目本来不带本机环境，首次启动会创建；不需要复制别人电脑的环境。 / Fresh downloads have no machine-specific environment; first launch creates it, so do not copy another computer's environment. |
| 提示找不到目录或没有图片 / Missing folder or no supported images | 检查路径、是否已放入照片；子目录中的照片需要 Recursive。`input`、`output` 是示例名字。 / Check paths and add photos; enable Recursive for subfolders. `input` and `output` are example names. |
| 输入输出目录相同 / Same input/output folder | 为结果指定另一个目录，例如 `D:\裁剪结果`。 / Choose a separate result folder, such as `D:\裁剪结果`. |
| 模型缺失或特征版本不一致 / Missing/mismatched model | 完整解压同一版本，保持三个模型文件（JSON 元数据和两份压缩权重）与主程序同目录，不解压 `.xml.gz`。 / Extract the same version fully, keep all three model files (JSON metadata and two compressed forests) beside the script, and leave `.xml.gz` compressed. |
| OpenCV 缺少 `ml.RTrees_create` / Missing `ml.RTrees_create` | 使用 `.cmd` 启动器或 `.\.crop-env\Scripts\python.exe`；项目需要 OpenCV 4.x。 / Use the `.cmd` launcher or project interpreter; OpenCV 4.x is required. |
| 保存按钮灰色、Enter 没反应 / Save disabled or Enter does nothing | 等待识别，确保有四个有效角点，并松开正在拖动的鼠标；查看底部提示。 / Wait for detection, select four valid corners, release a drag, and read the status line. |
| 旧裁剪没有变化 / Existing crops do not change | 默认跳过成功文件，重新审核或替换时加 `--overwrite`，或勾选覆盖。 / Successful outputs are skipped by default; enable Overwrite or add `--overwrite`. |
| 正方形模式让普通照片变形 / Square mode stretches a normal picture | 只对原本正方形的目标开启，普通横图/竖图用完整图片模式。 / Use Square only for originally square targets; Full picture for landscape/portrait. |
| 显示 `ok` 但裁错 / `ok` with an incorrect crop | `ok` 仅表示已保存；用 `--review --overwrite` 查看并重新选四角。 / `ok` means saved; use `--review --overwrite` to inspect and reselect corners. |
| 失败补裁没有待处理图片 / No pending failures | 检查传入的是否为结果总目录；被“结束”留下的未处理照片应从原目录继续批次。 / Check that you passed the result root; resume stopped/unprocessed photos from the source folder. |

反馈问题时，请提供程序版本、启动方式或完整命令、终端错误文字，以及是否开启正方形/清黑边。可用 `python screen_crop.py --version` 查看版本。更多排查见 [docs/USAGE.md](docs/USAGE.md)。

When reporting a problem, include the version, launcher or complete command, terminal error text, and whether Square/Trim black was enabled. Check the version with `python screen_crop.py --version`. More troubleshooting is in [docs/USAGE.md](docs/USAGE.md).

## v0.5.0 白色边缘与识别效率 / White edges and detection speed

新增浅色屏幕背景处理：估计并扣除缓慢变化的背景光照，组合多组差异掩膜寻找完整四边形。文字图片按整组内容生成边界；正方形模式可用已辨认的边补全较弱的一边。检测到合格的完整图片后，直接使用该区域，减少反光小目标森林误选内部小块的情况。界面和命令用法不变。

A new light-background path estimates smooth illumination, combines residual masks, and proposes complete quadrilaterals. Text content is grouped, and Square mode can complete a weak side using visible sides. Qualified whole-picture regions bypass the small-target forest, reducing selection of interior fragments. Existing UI and CLI usage remain the same.

| 本地同图对比 / Local same-image comparison | v0.4.1 | v0.5.0 |
|---|---:|---:|
| 用户提供的 5 张困难示例达标 / Five supplied examples, IoU ≥ 0.85 | 0/5 | 5/5 |
| 上述示例平均 IoU / Mean IoU | 3.28% | 95.79% |
| 上述示例识别耗时中位数 / Median detection time | 1.412 s | 0.058 s |
| 另取的 12 张人工修正照片达标 / Twelve additional corrected captures | 0/12 | 8/12 |
| 原有反光照片达标 / Existing reflection captures | 11/11 | 11/11 |
| 原有反光照片识别耗时中位数 / Median reflection detection time | 2.337 s | 1.556 s |

计时为每张照片每个版本连续 3 次的中位数，再取该组中位数；使用相同 CPU、原分辨率输入，模型预加载，不含读图、界面和保存。一般检测路径还将四边采样合并计算，并复用灰度、纹理和梯度，原森林权重和 24 特征顺序不变。速度取决于硬件和图片，不能保证所有输入均有同等提速。

For each photo/version, time is the median of three calls, then the median across that group. Both versions use the same CPU and native-resolution inputs with preloaded models; I/O, UI, and saving are excluded. The general path batches four-side sampling and reuses grayscale, texture, and gradient maps, retaining forest weights and feature order. Speed varies with hardware and inputs.

这 5 张属于开发示例，另 12 张与其共享拍摄环境，均不能代表任意新场景准确率。4 张额外照片仍未达标，涉及少量字符、大块留白、表格和文字标题，建议继续人工审核。旧 16 个合成回归保持全部通过；新增白边、浅边、文字页和竖图测试也通过。参数、匿名逐张指标与复评命令见 [模型说明](docs/MODEL_CARD.md)。

The five examples were used during development; the twelve additional captures share the environment. Neither estimates accuracy on arbitrary scenes. Four additional captures remain below threshold, including sparse characters, large blank areas, a chart, and a text heading; review them manually. All 16 earlier synthetic checks pass, alongside new white-frame, faint-side, text-page, and portrait tests. See the [model card](docs/MODEL_CARD.md) for parameters, anonymous records, and reproduction commands.

## v0.3.0 反光与抖动训练 / Glare and motion-blur training

根据使用者确认的 12 张边界截图，匹配到 11 张唯一未标线原照片：8 张用于训练、3 张预先留出。新增补充森林，使用局部反光、运动模糊及透视扰动增强，同时保留通用森林。小目标评分达标时启用补充模型；边界细化也检查评分，减少误裁到内部反射或纹理。

Twelve user-confirmed boundary screenshots map to 11 unique unmarked originals: eight for training and three reserved beforehand. A new specialist uses glare, motion blur, and perspective augmentation while retaining the base forest. Qualified small targets use the specialist, with score checks on refinement to reduce snapping to interior reflections/texture.

| 原照片边界评估 / Original-photo border evaluation | v0.2.1 | v0.3.0 |
|---|---:|---:|
| 训练原图达标（IoU ≥ 0.85）/ Training passes | 0/8 | 8/8 |
| 留出原图达标 / Holdout passes | 0/3 | 3/3 |
| 留出原图平均 IoU / Holdout mean IoU | 46.43% | 88.90% |

留出照片与训练共享拍摄环境，仅 3 张；不能视为任意新场景的准确率。33 个额外反光/模糊/组合压力衍生样例中，当前 30 个达标，仍有 3 个训练组衍生样例存在边界偏差。原有合成回归 16/16 通过。完整分组、参数、权重指纹与匿名指标见 [模型说明](docs/MODEL_CARD.md)。

The three holdout photos share the capture environment with training, so results do not estimate accuracy on arbitrary new scenes. Of 33 additional glare/blur/combined stress derivatives, 30 pass; three training derivatives retain border errors. All 16 existing synthetic checks pass. See the [model card](docs/MODEL_CARD.md) for splits, parameters, weight fingerprints, and anonymous metrics.

## v0.2.0 识别回归 / Recognition regression in v0.2.0

保留原预训练权重，改进灰度候选筛选与评分；正方形模式增加柔性形状参考。对比脚本使用相同权重和原创合成场景，指标见 [逐张结果](docs/recognition-v020.csv)，复现方法见 [模型说明](docs/MODEL_CARD.md)。这是合成场景回归，不代表真实照片准确率，也不是重新训练的模型。

The pretrained weights are retained while grayscale proposal filtering/ranking is improved; square mode adds a soft shape prior. Both versions use identical weights and original synthetic scenes. See [per-scene results](docs/recognition-v020.csv) and reproduction instructions in the [model card](docs/MODEL_CARD.md). This is synthetic regression, not a real-photo accuracy estimate or a retrained model.

| 合成验证 / Synthetic verification | v0.1.1 | v0.2.0 |
|---|---:|---:|
| IoU ≥ 0.85 | 10/16 | 16/16 |
| 平均 IoU / Mean IoU | 61.0% | 97.7% |

验证种子为 41、67，未用于阈值开发（11、29）；仍与开发样例共享生成方式，不能视为独立真实场景测试。彩色、暗色、模糊与小目标的 10 个样例结果与旧版一致。

Verification seeds 41 and 67 were excluded from threshold development (11 and 29), but share the generator; this is not independent real-scene testing. The 10 color, dark, blur, and small-target results match v0.1.1.

## 历史评估 / Recorded evaluation

下表来自既有模型的历史同图对比，达标线为 IoU ≥ 85%，属于早期通用模型记录。v0.3.0 的新增训练结果单独列出。

These historical same-image comparisons use a pass threshold of IoU ≥ 85%. They describe the earlier base model; v0.3.0 training is reported separately.

| 样本 / Samples | 旧版达标 / Previous | 当前模型达标 / Current | 旧版平均 IoU / Previous mean | 当前平均 IoU / Current mean |
|---|---:|---:|---:|---:|
| 全部 / All | 5/13 | 13/13 | 54.6% | 96.3% |
| 验证子集 / Validation subset | 2/4 | 4/4 | 77.2% | 96.4% |

验证图未参与拟合，但与训练图共享部分场景/内容，且开发期间查看过验证结果，不能视为独立盲测或泛化准确率。详见 [模型说明](docs/MODEL_CARD.md) 与 [逐张指标](docs/evaluation.csv)。真实原图及历史裁剪图不随仓库分发。

Validation images were excluded from fitting but share some scenes/content with training, and their results were inspected during development. This is not an independent blind test or generalization accuracy estimate. See the [model card](docs/MODEL_CARD.md) and [per-image metrics](docs/evaluation.csv). Real source photos and historical crops are not distributed.

## 项目结构 / Project structure

```text
screen_crop.py                  Detection, correction, batch processing
white_border.py                 Whole-picture detection on light backgrounds
crop_ui.py                      Single-page desktop workspace
batch_state.py                  Checkpoints and reviewed training labels
launch_crop.py                  Isolated environment setup and launcher
train_screen_model.py           Training entry point
screen_crop_model.json          Model metadata
screen_crop_forest.xml.gz       Base forest weights
screen_crop_reflection.xml.gz   Reflection specialist weights
requirements.txt               Runtime dependencies
启动裁剪.cmd                    Windows launcher
安装环境.cmd                    Windows setup-only entry point
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
