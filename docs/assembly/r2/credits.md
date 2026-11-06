# 模型与依赖来源

- CyberMachine R2 机箱、导轨、托脚、垫片和固定点来自本仓库 [model.mjs](../../anatomy/r2/src/model.mjs)及[原厂测量基准](../../anatomy/r2/src/reference.mjs)。教程重新规划装配动作，未修改 R1 制造件或原厂参考文件。
- Radxa TACO V1.61：使用仓库保存的 [原厂 STEP](../../../references/radxa-taco/radxa_taco_3d_stp_v1.61.stp)、[器件位置图](../../../references/radxa-taco/radxa_taco_components_placement_map_v1.61.pdf)、[原理图](../../../references/radxa-taco/radxa_taco_schematic_v1.61.pdf)及[产品简介 Revision 1.2](../../../references/radxa-taco/rad-doc-0030_radxa_taco_product_brief__revision_1.2_g4dfad65.pdf)。原文件名和字节保留，Radxa 商标与设计权归原权利人。
- Raspberry Pi CM5：尺寸化教学模型，包含简化 PCB、芯片、两组连接器和散热器；Raspberry Pi 名称归原权利人。散热器不代表指定商品。
- 通用 M.2 E-Key 2230 卡、插槽补绘、同轴天线及接头为本教程生成的教学示意，未使用外部下载模型；不代表具体品牌的兼容性或制造数据。
- React / React DOM、Three.js、React Three Fiber、Drei、Vite：MIT；Playwright：Apache-2.0。直接依赖版本与完整传递依赖由 [package-lock.json](src/package-lock.json)固定。构建器保留依赖随打包输出的许可证注释；独立许可证文本见 [assets/third-party-licenses.txt](assets/third-party-licenses.txt)。
- [frame-guard.mjs](src/frame-guard.mjs)来自 visualize-in-3d 技能附带的 MIT 屏幕取景检查工具，保留原注释，用于预览逐帧测量。
- 参数几何所依赖的 Anatomy 工具采用 MIT 许可证，保留原始 [kit/LICENSE](../../anatomy/r2/src/kit/LICENSE)与工具结构。Blender 和 OCCT 仅用于离线资产生成，不随页面嵌入运行。

30 秒视频为本教程真实页面的自动化操作预览；原始帧与录制中间日志存放在忽略目录，可由源码重建。
