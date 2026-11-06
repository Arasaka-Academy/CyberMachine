# GitHub Pages 交互结构图

在线查看 [CyberMachine R2 交互结构图](https://arasaka-academy.github.io/CyberMachine/)。站点首页自动进入 R2 深色页面，也可直接访问：

- [深色主题](https://arasaka-academy.github.io/CyberMachine/docs/anatomy/r2/)
- [浅色主题](https://arasaka-academy.github.io/CyberMachine/docs/anatomy/r2/index-light.html)
- [R2 3D 装配教学与练习](https://arasaka-academy.github.io/CyberMachine/docs/assembly/r2/)，复现见[教程说明](assembly/r2/README.md)
- [30 秒操作预览](https://arasaka-academy.github.io/CyberMachine/docs/assembly/r2/preview.mp4)

页面保留三种硬盘厚度、展开滑块、组件与盘位选择、键盘操作和巡览。图中的下载继续使用 R1 文件与名称；R2 提供结构示意与装配设计教学，对应的制造文件和实物验证状态见[仓库说明](../README.md)。HTML 仍可下载后离线打开。

## 构建与预览

结构图需要 Node.js 20.10+、Python 3.10+ 和 Git，无需额外依赖。三维教程需要 Node.js 22.12+ 和锁定的 npm 依赖；使用已收录模型构建，不运行 CAD 或 Blender。在仓库根目录运行：

```sh
node docs/anatomy/r2/src/build.mjs
node docs/anatomy/r2/src/build.mjs --light
npm --prefix docs/assembly/r2/src ci
npm --prefix docs/assembly/r2/src run build
python3 scripts/build_figure_pages.py
python3 -m http.server 8000 --bind 127.0.0.1 --directory outputs/github-pages
```

访问 `http://127.0.0.1:8000/`。暂存器保持仓库相对路径，复制 `docs/`、`hardware/`、`references/`、`validation/` 中 Git 管理或未忽略的公开文件，以及根目录 README、AGENTS 和完整性清单，保证说明、图片与模型下载的本地链接可用。`work/`、`outputs/` 和 Git 元数据不会发布。

默认输出为被 Git 忽略的 `outputs/github-pages/`。为保护已有输出，目标目录必须尚不存在；重复构建时使用新的目录，例如 `python3 scripts/build_figure_pages.py --output outputs/github-pages-preview`。从其他工作目录运行时，使用脚本绝对路径；默认输出仍位于仓库中。暂存时检查全部 HTML 和 Markdown 的本地文件链接。

## 自动发布

[Pages 工作流](https://github.com/Arasaka-Academy/CyberMachine/blob/main/.github/workflows/pages.yml)在 `main` 上的页面、正式资料、构建脚本或校验清单更新后自动执行，也可在 GitHub Actions 手动触发。仓库 Settings → Pages 的 Source 使用 **GitHub Actions**。

工作流先校验正式文件 SHA256，再重新构建深浅结构图及三维教程、运行教程逻辑检查，并确认页面与提交内容一致，随后暂存、检查链接、上传并部署。普通构建复用几何缓存；这项发布流程不执行新的 CAD、切片、几何审计或实物试装。
