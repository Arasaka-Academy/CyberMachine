# src/
> L2 | Parent: /docs/design/r3/AGENTS.md

index.html：设计审阅界面的语义结构，离线构建入口。
main.mjs：读取CAD尺寸及通风槽元数据；展示五盘7mm、水平6mm横带、四点锁盖和双件骨架。
io-review.mjs：消费 CAD 接口截面及节点名，生成高亮、命中面与近景包络。
frame-guard.mjs：viz3d 视口测量工具，检查主体裁切与像素尺寸。
style.css：浅深主题、固定硬盘规格、产品审阅排版与场景控制。
responsive.css：宽屏、窄屏、390px 与减少动态效果布局。
build.mjs：读取候选GLB、metadata与许可，核对模型SHA，内嵌页面并重定位文档链接。
package.json：构建及浏览器检查命令，沿用 R2 锁定依赖。
package-lock.json：锁定 three.js、Vite 与 Playwright，排除未使用的 React 依赖。
browser.mjs：对照CAD核对九件、五盘7mm及水平6mm横带端点；验证盖锁、顶扇、I/O、键盘和手机视图。

[PROTOCOL]: Update this header on change, then check AGENTS.md
