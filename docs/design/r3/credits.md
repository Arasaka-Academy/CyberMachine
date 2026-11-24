# R3 模型与来源

| 内容 | 来源与使用方式 |
| --- | --- |
| TACO V1.61 主板及元件 | 仓库既有的 [Radxa 原厂 STEP](../../../references/radxa-taco/radxa_taco_3d_stp_v1.61.stp)。只读导入，保留实体几何，未改原文件字节。资料权利归原厂，不附加许可声明。 |
| R3 外壳、骨架与五个盘托 | 本项目 [R3 参数源码](../../../hardware/enclosure/r3/src/design.py)。本次自主重构，没有下载外部机箱模型。 |
| I/O 孔口轮廓与原厂实体映射 | 本次 CAD 导出的元数据。页面消费与 GLB 同批的截面和节点名，不从界面另造开孔。 |
| 硬盘、风扇、CM5 与散热器 | R3 参数源码中的尺寸包络。外形用于排布审阅，不代表具体购买件的完整几何。 |
| three.js 0.187.0 | [three.js 项目](https://github.com/mrdoob/three.js)，MIT。负责 WebGL 场景与材质。 |
| OrbitControls / GLTFLoader | three.js `examples/jsm/controls/OrbitControls.js` 与 `examples/jsm/loaders/GLTFLoader.js`，沿用 three.js MIT 许可。 |
| frame-guard | 本机已安装的 `visualize-in-3d/scripts/frame-guard.js`。该技能声明 MIT。源码保留原注释，补充本项目文件头；只用于视口裁切与尺寸测量。 |
| 构建与浏览器检查 | Vite / Playwright，版本见 [package-lock.json](src/package-lock.json)。它们不作为页面运行资源加载。完整依赖许可记录沿用 [R2 汇总](../../assembly/r2/assets/third-party-licenses.txt)。 |

页面内嵌本地候选模型、脚本和样式，不请求外部模型、图片、字体或脚本。以上外部链接仅用于来源追溯。

## three.js MIT 许可

```text
The MIT License

Copyright © 2010-2026 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

## frame-guard 所属技能的 MIT 授权文本

该工具源文件没有单列版权人；保留原文件注释与技能名，不推定其他版权人。

```text
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

[PROTOCOL]: Update this header on change, then check AGENTS.md
