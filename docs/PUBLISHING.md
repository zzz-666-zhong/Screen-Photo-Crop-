# GitHub 发布指南 / Publishing to GitHub

项目作为包含源代码和预训练模型的仓库发布，不需要先制作安装程序或上传 PyPI。

Publish this as a source-code repository with a pretrained model; an installer or PyPI package is not required.

## 干净的项目目录 / Clean project directory

`github-release/` 是从工作目录整理出来的精简发布副本。进入该目录后，根目录应直接包含 `screen_crop.py`、README、LICENSE 和两个模型文件。不要把上一级的原图、历史结果或虚拟环境一起上传。

`github-release/` is the clean release copy prepared from the working directory. Inside it, the root directly contains `screen_crop.py`, README, LICENSE, and both model files. Do not upload the parent folder's photos, historical results, or virtual environments.

## 创建仓库并推送 / Create a repository and push

在 GitHub 上创建空仓库，例如 `screen-photo-crop`，不要额外初始化 README 或许可证。然后在精简项目根目录执行：

Create an empty GitHub repository, for example `screen-photo-crop`, without adding a separate README or license. Then run from the clean project root:

```powershell
git init -b main
git add .
git status --short
git commit -m "Initial release: screen photo crop v0.1.0"
```

将下面的 `<YOUR_REPOSITORY_URL>` 替换为新仓库的 HTTPS 或 SSH 地址：

Replace `<YOUR_REPOSITORY_URL>` with the HTTPS or SSH URL of your new repository:

```powershell
git remote add origin "<YOUR_REPOSITORY_URL>"
git push -u origin main
```

使用你自己的 Git 用户名、邮箱及 GitHub 登录凭据。项目不包含作者账号或凭据。参见 [GitHub 导入本地代码指南](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)。

Use your own Git name/email and GitHub credentials. No account or credentials are embedded in the project. See [GitHub's local-code import guide](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).

权重约 36 MiB，超过网页上传的单文件 25 MiB 上限，但低于普通 Git 的 100 MiB 限制。请用 Git 推送；当前模型无需 Git LFS。依据 [GitHub 官方限制](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。

The model is about 36 MiB, exceeding the 25 MiB browser-upload limit but below the 100 MiB regular Git limit. Push using Git; this model does not require Git LFS. See [GitHub's official limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).

## 测试与打包 / Test and package

按 README 安装环境后，在项目根目录执行：

After setting up the environment as described in the README, run:

```powershell
.\.crop-env\Scripts\python.exe -m unittest discover -s tests -v
.\.crop-env\Scripts\python.exe scripts/build_release.py
```

macOS/Linux 使用 `.crop-env/bin/python`。打包脚本本身仅需 Python 标准库，也可单独使用 `python scripts/build_release.py`。同版本文件已存在时，加 `--overwrite`。

Use `.crop-env/bin/python` on macOS/Linux. The packager itself uses only the standard library, so it can also run with `python scripts/build_release.py`. Add `--overwrite` to replace an existing release of the same version.

输出 `dist/screen-photo-crop-v0.1.0.zip` 及 `.zip.sha256`。ZIP 内附逐文件 SHA-256 清单。发布内容由 [release-files.txt](../release-files.txt) 明确列出，原图、虚拟环境、历史结果及临时文件不会进入包中。

This produces `dist/screen-photo-crop-v0.1.0.zip` and `.zip.sha256`, with a per-file SHA-256 manifest inside the ZIP. [release-files.txt](../release-files.txt) explicitly lists public files; source photos, environments, historical results, and temporary files are excluded.

## Actions 与 Release / Actions and release

推送后查看 Actions 中的 `Test and package`。工作流配置了 Windows/Linux 与 Python 3.10/3.12 测试，通过后构建下载附件。配置需要在自己的仓库实际运行；本地测试通过不等于 GitHub 托管测试已通过。

After pushing, inspect `Test and package` in Actions. It is configured for Windows/Linux with Python 3.10/3.12 and builds a downloadable artifact after tests pass. It must run in your repository; local results do not imply hosted CI has passed.

创建 `v0.1.0` Release，附上 ZIP、`.sha256` 和版本说明。工作流不会自动公开 Release。说明可参考 [CHANGELOG.md](../CHANGELOG.md)。后续发布更新 `screen_crop.py` 的 `__version__`、变更记录、文档版本和文件清单；修改权重时同步模型说明及评估。

Create a `v0.1.0` release with the ZIP, `.sha256`, and release notes from [CHANGELOG.md](../CHANGELOG.md). The workflow does not publish a public release automatically. For later releases, update `__version__` in `screen_crop.py`, the changelog, documentation versions, and file list; model updates also require model-card and evaluation updates.

Suggested description: `Crop pictures from photographed screens with perspective correction, a pretrained model, and manual review.`

Suggested topics: `python`, `opencv`, `image-processing`, `perspective-correction`, `screen-photo`, `batch-processing`.
