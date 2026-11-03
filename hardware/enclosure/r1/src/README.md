# CyberMachine R1 CAD 源码

本目录保存适配 Radxa Taco V1.61 的五盘 NAS 机箱源码。模型单位均为毫米，STEP 中各打印件保留独立解析实体及装配坐标。预览中的主板、硬盘、风扇与散热件属于购买件或外形包络，不包含在可打印几何中。

## 目录与正式资料

- `design.py`：CAD 几何、分件网格、主板参考包络和 STEP 导出。
- `validate.py`：已有 CAD 中间文件的网格、干涉、硬盘抽取及紧固件检查。
- `prepare_slicer.py`：根据本机 Bambu Studio 配置生成 P1S PETG 预设与打印盘计划。
- `render.py`：在兼容的 Blender 环境中导入已生成网格，渲染装配和拆解预览。
- `package_delivery.py`：核对切片及数字验证结果，输出英文命名的打印资料、预览、源码和设计包。

已交付的 [STEP](../cad/CyberMachine-r1-enclosure.step)、[打印资料](../print/) 与 [装配说明](../../../../docs/assembly/r1.md) 单独存放。原板 STEP 位于[参考资料目录](../../../../references/radxa-taco/radxa_taco_3d_stp_v1.61.stp)，读取时保持原文件不变。

## CAD 重建

原交付记录所用环境为 Python 3.12.9、`cadquery-ocp-novtk==8.0.1.1.0`、`numpy==2.5.4`、`trimesh==5.2.0`。脚本使用 OCCT 8 的集合及类型转换 API；使用 OCP 7 需要适配。无需安装 CadQuery 主包。

在独立 Python 环境中安装对应依赖后，从仓库根目录运行：

```sh
python3 hardware/enclosure/r1/src/design.py --board-step references/radxa-taco/radxa_taco_3d_stp_v1.61.stp
```

默认工作空间从脚本所在位置解析，与启动命令时的当前目录无关；`--board-step` 的相对路径仍相对当前目录。需要在其他位置工作时，使用绝对输入路径与 `--root` 指定工作空间。`--only` 保留原构建步骤筛选功能。

输出包括 `work/parts/`、装配与打印朝向的 STL、中间清单、参考干涉检查，以及 `outputs/CyberMachine-r1-enclosure.step`。该脚本不会更新仓库中的正式 STEP 或打印文件。

## 辅助流程的前置条件

以下命令示例均在仓库根目录运行。辅助脚本固定使用仓库下的 `work/` 和 `outputs/`；若 CAD 使用自定义 `--root`，需先将所需中间数据安排到仓库工作目录后再运行这些辅助流程。

| 脚本 | 运行方式 | 额外输入与环境 |
| --- | --- | --- |
| 数字验证 | `python3 hardware/enclosure/r1/src/validate.py` | CAD 构建完成后的 BREP、网格、清单和原板缓存；OCP 与 trimesh |
| 切片准备 | `python3 hardware/enclosure/r1/src/prepare_slicer.py` | CAD 网格及清单；原脚本使用 macOS Bambu Studio 的 BBL 配置目录 |
| 预览渲染 | `blender --background --python hardware/enclosure/r1/src/render.py` | CAD 装配网格与主板参考网格；支持原脚本 STL 导入及材质 API 的 Blender 环境 |
| 打包 | `python3 hardware/enclosure/r1/src/package_delivery.py` | 完整切片结果、网格与干涉检查结果、渲染 PNG；Pillow、macOS STHeiti 字体 |

切片准备只生成配置和排版计划，不执行 Bambu Studio 切片。打包需要 `work/slicer/release/CyberMachine-r1-5bay-p1s-petg.3mf`、该目录的 `result.json`、`work/slicer/coupon/CyberMachine-r1-fit-test-p1s.3mf`，以及验证和渲染步骤生成的中间数据。这些中间数据未随正式资料入库，需在对应工具环境中重新准备。

打包还需要 CAD 构建产生的 `outputs/CyberMachine-r1-enclosure.step`。候选设计包目录为 `outputs/CyberMachine-r1-design-package/`，压缩包为 `outputs/CyberMachine-r1-design-package.zip`。

包内保留 `hardware/`、`docs/`、`references/`、`validation/` 的仓库相对结构，包含 R1 源码、模型、打印资料、装配说明、预览、参考文件与数字报告，便于继续解析脚本和文档的相对路径。包内另有 R1 README 和 `SHA256SUMS.txt`；包内清单与仓库根目录的正式资料清单分别维护。

## 修改与验证边界

源码按坐标构造 CAD。修改外形尺寸时，也需检查对应的面板、紧固件、接口与净空坐标，并重新检查干涉、导出和切片。第三方参考模型保持独立，修改后的几何应先验证，再替换正式资料。

已有数字检查不能代替真实打印与试装；螺孔位置、插接深度、螺纹深度、温升、噪声及振动仍需使用实物验证。
