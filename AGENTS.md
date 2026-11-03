# CyberMachine 仓库工作约定

## 项目与版本

CyberMachine 是 NAS 设备硬件设计仓库。当前硬件平台是 Radxa Taco V1.61 + Raspberry Pi CM5，设计单位为毫米。

- R1 包含制造设计、CAD 源码和打印资料；R2 当前只有四点螺丝固定方案的交互示意。分别维护版本，不将 R1 打印件标注为 R2。
- 修改尺寸、孔位、安装方向或坐标基准时，同步检查接口、紧固件、净空、硬盘抽取路径和配套文档。交互图的示意展开位移不代表装配行程。
- 数字几何、切片和浏览器检查分别记录。实物打印、试装、温升、振动和噪声结论必须有对应的实测证据。

## 目录职责

| 目录 | 职责 |
| --- | --- |
| `hardware/enclosure/r1/src/` | R1 CAD 与辅助流程源码，依赖和中间数据要求见其中的 README |
| `hardware/enclosure/r1/cad/` | 正式机箱 STEP |
| `hardware/enclosure/r1/print/` | 正式 3MF、STL ZIP、打印盘清单 |
| `docs/assembly/` | 按版本保存的装配、五金和打印说明 |
| `docs/images/r1/`、`docs/images/r2/` | 对应版本的正式预览图 |
| `docs/anatomy/r2/` | R2 离线 HTML、SVG、使用说明及 `src/` 绘图源码 |
| `references/radxa-taco/` | 保留原厂名称与内容的主板参考文件 |
| `validation/r1/`、`validation/r2/` | 对应版本的数字检查、图形审计与历史日志 |
| `work/`、`outputs/` | 被 Git 忽略的中间文件与重新生成的交付候选文件 |

## 命名与维护边界

- 文档正文以中文为主。目录和普通文件使用小写英文与连字符；Python 文件使用下划线。保留 `README.md`、`AGENTS.md`、`SHA256SUMS.txt` 和第三方 `LICENSE` 的通行名称。
- 独立分发的模型、打印项目与压缩包使用 `CyberMachine-r1-` 项目及版本前缀；新的硬件修订建立独立版本目录，并同步根 README 的状态表。
- 原厂参考资料保留型号、版本与内容。更换参考版本时另存文件，并更新对应引用。
- `docs/anatomy/r2/src/kit/` 是第三方工具，保留其许可证与原始结构；改动时说明具体原因。
- 历史日志保留原始正文及日期；整理路径或补充验证时添加有日期的说明，不能将旧结果表述为本次新执行的验证。
- 代码从自身文件位置定位仓库目录，不依赖个人绝对路径。用户指定的输入路径和工作空间按相应命令参数处理。
- Git 换行规则由根目录 `.gitattributes` 管理：普通文本使用 LF，原厂 CAD 与打印盘 CSV 保留原始字节，压缩项目及图片、PDF 按二进制处理。提交前核对暂存内容与校验清单，避免 Git 转换原始文件的换行。
- 检索优先使用 `rg`。环境提供 `rtk` 时通过它运行命令；文档中的命令保持标准工具语法，便于跨机器使用。

## 修改与生成流程

1. 先阅读根 README 和受影响模块的说明，核对当前改动，保留无关文件与用户已有工作。
2. 目录迁移前记录文件清单和 SHA256；迁移时保持 STEP、STP、3MF、STL ZIP、PDF、PNG 内容不变，并同步文档及脚本中的路径。
3. 修改交互图时先改 `docs/anatomy/r2/src/`，再生成 HTML / SVG。普通构建不执行完整几何审计；几何变更需显式使用 `--audit`。
4. 修改 CAD 时先在 `work/`、`outputs/` 生成候选结果，检查几何、网格、干涉与切片后再更新正式资料。辅助流程需要的本机软件和未入库中间数据见源码 README。
5. 保留正式交付文件在仓库中；临时工作数据使用现有忽略目录。更新正式文件后，最后重新生成根目录清单并校验。

## 必要检查

对修改的 Python / JavaScript 做语法检查，解析 JSON 和 SVG，并检查 Markdown / HTML 本地链接及图片路径。

从仓库根目录构建两套页面：

```sh
node docs/anatomy/r2/src/build.mjs
node docs/anatomy/r2/src/build.mjs --light
```

目录或路径变更还需从其他工作目录使用绝对脚本路径构建。几何修改需执行：

```sh
node docs/anatomy/r2/src/build.mjs --audit
```

浏览器检查离线打开、深浅主题、三种硬盘厚度模式、组件与盘位选择、键盘操作及 390px 布局，确认无页面错误和横向溢出。涉及动画逻辑时，补查减少动态效果、离屏暂停和返回恢复。

环境不具备 CAD、切片或渲染依赖时，记录具体未执行项；语法或浏览器通过不能替代对应流程的实际验证。

## 更新完整性清单

在仓库根目录、完成修改和生成之后运行以下脚本。清单覆盖所有 Git 跟踪及未忽略的实际文件，排除清单自身；无需先暂存文件。

```sh
python3 - <<'PY'
from hashlib import sha256
from pathlib import Path
import subprocess

root = Path.cwd()
names = subprocess.check_output([
    "git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"
]).decode("utf-8").split("\0")
paths = sorted({
    name for name in names
    if name and name != "SHA256SUMS.txt" and (root / name).is_file()
})
lines = [sha256((root / name).read_bytes()).hexdigest() + "  " + name for name in paths]
(root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
shasum -a 256 -c SHA256SUMS.txt
```

生成后核对清单是否完整覆盖此次正式资料，确认临时工作文件未被纳入。
