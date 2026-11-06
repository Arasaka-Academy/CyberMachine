# CyberMachine R2 · 3D 装配教学

[在线使用教程](https://arasaka-academy.github.io/CyberMachine/docs/assembly/r2/) · [在线查看 30 秒预览](https://arasaka-academy.github.io/CyberMachine/docs/assembly/r2/preview.mp4)

直接用现代浏览器打开 [index.html](index.html)，无需启动服务器或联网。JavaScript、样式、压缩模型和备用图片全部内嵌；外部文档与视频链接需要保留对应文件。[30 秒低清操作预览](preview.mp4)展示真实页面操作。

这是一份 **R2 装配设计教程**。R2 尚无制造 STEP、打印项目或实物试装；R1 文件继续按 [R1 装配说明](../r1.md)使用。通用 E-Key 模型不承诺具体网卡的驱动兼容性。

## 学什么

| 章节 | 重点 |
| --- | --- |
| 机箱准备 | 底框、前后导轨预紧、右侧框、主板支架和四根隔离柱；保持操作面开放 |
| CM5 预装 | 台面绝缘支撑，两组板对板接口同时对位，垂直均匀压合，安装配套固定件与散热器 |
| 无线网卡 | 区分 E-Key 2230 与 M-Key NVMe；缺口对齐、倾斜插入、压平固定、端子连接和避让走线 |
| TACO 入箱 | I/O 朝前、SATA 朝下；从上方进入，对准四个不规则孔，按数字顺序逐步均匀固定 |
| 硬盘与收尾 | 7 mm 盘先放两条 2.5 mm 垫片，9.5 mm 盘直接安装；逐盘向上插合、导轨对准、四点固定、托脚承托、风扇与面板合拢 |

I/O 面板从前下方斜向入位，保持接口开窗对准；检修盖先装，脚垫最后安装，避开边角。展示用支撑架不属于机箱打印件。装配全过程断电，机箱支稳；螺丝长度、旋入深度、隔离柱、导热材料和天线接头均需核对实际配套规格。

## 页面操作

- 每章独立滑块控制本章动作，支持 0.5 / 1 / 2 / 4 倍播放、暂停、重播、任意跳章和回退。零件位置由章节和进度直接求值。
- 拖动旋转，滚轮缩放；「复位视角」回到对应近景；点选实体可高亮。「查看内部」移开遮挡件。
- 三种厚度：混装时 02 / 04 为 7 mm，其余为 9.5 mm；也可切换全 7 mm、全 9.5 mm。逐盘演示会跟随正在插入的盘位，暂停后可独立选盘查看；固定件阶段保留手动选择。
- 工作台获得焦点后：空格播放/暂停，左右键调节进度，Home / End 到起点/终点，数字 1–5 跳章，Escape 暂停并取消选择。滑块和按钮保留原生键盘操作。
- 「自己装一次」支持桌面拖放，也可先选托盘零件，再点安装标记，适用于手机。插错槽、缺本盘垫片、缺侧螺丝或过早封盖时，说明原因并保留进度。
- 切换厚度保留主板预装，重置硬盘、垫片与固定件，避免把旧配置的完成状态带入新配置。
- 浅色、深色与蓝图主题；系统启用减少动态效果时直接显示本章完成状态。视图离屏或页面隐藏后暂停，返回时从原进度恢复。

## 模型与坐标

源数据全部保留毫米坐标，统一通过 `[x,z,-y]/1000` 映射到渲染空间。机箱来自现有 [R2 参数几何](../../anatomy/r2/src/model.mjs)，网格由 OCCT 生成；TACO 直接读取仓库 [V1.61 原厂 STEP](../../../references/radxa-taco/radxa_taco_3d_stp_v1.61.stp)，保留 730 个实体。变换为绕 Y 轴 180° 后平移 `(72.1,120,135)` mm。

CM5 的 55 × 40 mm 外形、两组连接器、硬盘、散热器与紧固件含示意细节。原厂 STEP 没有 E-Key 连接器实体：按 V1.61 器件位置图 U33 补绘，连接器高度、通用网卡元件、天线外形仍是教学包络。M-Key 仅保留插槽用来比较，本课程不安装 NVMe。两路 FPC 天线示意粘贴在右侧框内侧，实际射频位置仍需按模块和天线说明验证；天线只演示连接与避让走线，未新增机壳孔位。螺纹与盘侧螺丝埋入段省略，不可据此确定加工或旋入深度。

模型包含 SATA、CM5、E-Key、网卡尾孔和天线的具名锚点。锚点对齐验证的是这套数字模型；E-Key 等补绘锚点不代表已经测量过实物。模型与依赖出处见 [credits.md](credits.md)。

## 复现

仅重建页面需要 Node.js 22.12+；依赖版本由 [package-lock.json](src/package-lock.json)固定，已收录模型，无需安装 Blender 或 OCCT。

```sh
cd docs/assembly/r2/src
npm ci
npm test
npm run build
npm run test:browser
npm run record
```

浏览器检查与录制默认使用 Playwright Chromium，先运行 `npx playwright install chromium`。也可通过环境变量 `CHROME_PATH` 指定本机 Chrome 可执行文件；录制另外需要 ffmpeg。页面构建以脚本自身位置解析目录，可从其他工作目录执行 `node /path/to/CyberMachine/docs/assembly/r2/src/build.mjs`。

重新生成模型需要 Python 3.12、`cadquery-ocp-novtk==8.0.1.1.0` 和 Blender 3.6。以下命令在仓库根目录执行；Blender 可执行文件按本机安装路径替换：

```sh
node docs/assembly/r2/src/export-scene.mjs
uv run --python 3.12 --with cadquery-ocp-novtk==8.0.1.1.0 python docs/assembly/r2/src/mesh_model.py
blender --background --factory-startup --python docs/assembly/r2/src/build_assets.py
node docs/assembly/r2/src/audit.mjs
uv run --python 3.12 --with cadquery-ocp-novtk==8.0.1.1.0 python docs/assembly/r2/src/audit_motion.py
node docs/assembly/r2/src/build.mjs
```

中间数据位于忽略目录 `work/assembly-r2/`。教学模型文件为 [assembly.glb](assets/assembly.glb)，页面嵌入使用其确定性 gzip 副本。修改模型后应依次更新网格、GLB、页面与验证记录。

| 文件 | 职责 |
| --- | --- |
| [export-scene.mjs](src/export-scene.mjs)、[mesh_model.py](src/mesh_model.py)、[build_assets.py](src/build_assets.py) | 参数几何、原厂 STEP、网格、材质与具名锚点 |
| [lesson.mjs](src/lesson.mjs)、[catalog.json](src/catalog.json) | 零件、教学内容、动画、镜头与练习前置条件 |
| [scene.jsx](src/scene.jsx)、[app.jsx](src/app.jsx)、[style.css](src/style.css) | 三维场景、操作界面与响应式主题 |
| [build.mjs](src/build.mjs) | Vite 构建并内嵌所有运行资源 |
| [tests](src/tests/)、[audit_motion.py](src/audit_motion.py) | 逻辑、离线浏览器及精确实体路径采样检查 |
| [record-film.mjs](src/record-film.mjs) | 虚拟时钟驱动真实页面操作，录制 30 秒预览 |

## 验证记录

本次数字检查、浏览器版本、采样精度与限制见 [装配验证说明](../../../validation/r2/assembly-validation.md)、[路径检查](../../../validation/r2/assembly-motion.json)和[浏览器记录](../../../validation/r2/assembly-browser.json)。截图在 [R2 图片目录](../../images/r2/)。

路径检查采样每章 101 个进度与阶段边界，覆盖三种厚度；它不是连续扫掠证明。插座有意插接、螺丝座接触和原有结构连接分别记录。未进行实物打印、试装、温升、振动、噪声、实际无线驱动与信号测试。
