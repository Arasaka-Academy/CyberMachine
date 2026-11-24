# src/
> L2 | Parent: /hardware/enclosure/r3/AGENTS.md

design.py：水平6mm通风横带、四角竖锁与接壁底脚；五盘7mm，定义五种打印朝向。
io_geometry.py：原厂前端截面对应七组开孔与导入口，向模型和页面提供同一几何。
check_io.py：独立读取原厂前端面，检查连续直孔量规、USB-C 开放壳和漏孔失败对照。
check_mesh.py：读取实际二进制STL，核对边闭合、方向、连通体和有向体积。
export_candidates.py：导出STEP/STL及GLB；绑定水平横带参数、九件数量、变换和紧固清单。
validate.py：逐730闭合原厂实体求交，保留旧座碰撞对照、连续座区隔离和提升采样。
check_board.py：独立读取原厂 STEP，测四个承托点、M2.5 螺丝头与孔壁，加入放大螺杆的失败对照。
check_mating.py：分别测四承台和四盖压套落座面积，核对外观缝及止口间隙。
check_fastening.py：独立测四竖锁、闭合沉孔、D座/压套/铜套栈、工具和底脚根，含失败对照。
check_top_fan.py：独立测顶扇与盖锁净空，记录四盖螺丝旋出后的提盖包络采样。
check_vents.py：独立读取STEP，测通风面积、贯通与水平6mm横带；以旧弧带作失败对照。
check_service.py：测主板/后扇/四盖锁盲孔与36项工具空间；比较主架和后框材料。
check_frame.py：核对7mm盘、尖拱、键槽、改位底梁/前脚角板及显式基线材料加减。
check_dfm.py：执行五种实际打印朝向的PETG FDM规则，记录警告及设计、I/O和STEP哈希。
slice_candidates.py：执行P1S/PETG五盘切片，保存对象支撑覆盖，绑定输入哈希和指标。
check_print.py：核对预设哈希、对象支撑持久化、内外G-code、床面禁区和路径间距。
README.md：模型坐标、依赖、候选输出与验证边界。

[PROTOCOL]: Update this header on change, then check AGENTS.md
