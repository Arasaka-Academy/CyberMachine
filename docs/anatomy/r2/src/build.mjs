import {writeFileSync,readFileSync,existsSync,mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import * as k from './kit/iso-kit.mjs';
import * as G from './kit/lathe.mjs';
import * as A from './kit/audit.mjs';
import {kitScript} from './scripts/inline-kit.mjs';
import {makeScene,P,SPEC,W,H} from './model.mjs';

const HERE=dirname(fileURLToPath(import.meta.url)),OUT=resolve(HERE,'..');
const ROOT=resolve(HERE,'../../../..'),REPORTS=resolve(ROOT,'validation/r2');
const theme=process.argv.includes('--light')?'light':'dark';
const draft=process.argv.includes('--draft'),quick=process.argv.includes('--quick');
const suffix=theme==='light'?'-light':'';
const modelHash=createHash('sha256');
for(const name of ['model.mjs','reference.mjs'])modelHash.update(readFileSync(resolve(HERE,name)));
const geometryHash=modelHash.digest('hex');
const cachePath=resolve(HERE,'order-cache.json');
const cache=existsSync(cachePath)?JSON.parse(readFileSync(cachePath,'utf8')):{};
if(cache.modelHash!==geometryHash){cache.modelHash=geometryHash;cache.modes={};}
const scenes=[];
for(const mode of ['mixed','9.5','7']){
 const scene=makeScene(mode),{R}=scene;
 if(!draft){
  console.time(`settle ${mode}`);
  const options={states:A.uniformStates(quick?2:60),...(quick?{step:5}:{})};
  if(!process.argv.includes('--audit')&&cache.modes?.[mode]){
   const keys=new Map(cache.modes[mode]);R.items.forEach(it=>it.key=keys.get(it.name));
  }else{
   A.settle(R,P,options);
   if(!quick){cache.modes??={};cache.modes[mode]=R.items.map(it=>[it.name,it.key]);}
  }
  console.timeEnd(`settle ${mode}`);
  const result=A.auditOrExit(R,P,{frames:A.uniformStates(quick?2:60),apart:true});
  if(result){
   mkdirSync(REPORTS,{recursive:true});
   writeFileSync(resolve(REPORTS,`audit-${mode}.json`),JSON.stringify({
    result,failures:A.failures(result),states:R.settled.states,
    geometrySha256:geometryHash,checkedAt:new Date().toISOString(),
    precision:{overlapSampleStepPx:quick?5:.25,depthStates:R.settled.states.length,clearanceStates:options.states.length},
    counts:{items:R.items.length,solids:R.solids.length,tubes:R.tubes.length},
   },null,2)+'\n');
  }
 }
 scenes.push(scene);
}
if(!draft&&!quick)writeFileSync(cachePath,JSON.stringify(cache));
const V=G.viewOf(P);
const group=(it,t=0)=>`<g class="part"${(t===0?it.piece==='enclosure':it.piece==='drives'&&it.drive===1)?' data-active=""':''} data-name="${it.name}" data-piece="${it.piece}" data-drive="${it.drive||0}" data-key="${it.key}" data-lift="${G.dot3(it.move,V)}" data-move="${it.move.join(',')}" transform="${k.translateAlong(P,G.mul3(it.move,t))}">${it.svg}</g>`;
const items=(scene,t)=>[...scene.R.items].sort((a,b)=>a.key+G.dot3(a.move,V)*t-b.key-G.dot3(b.move,V)*t).map(it=>group(it,t)).join('');
const body=scenes.map(s=>`<g data-mode="${s.mode}"${s.mode==='mixed'?'':' style="display:none"'}>${items(s,0)}</g>`).join('');
// The kit's horizontal camera basis is opposite to the CAD renderer's. Reflect
// only the drawing, including all moving assemblies; text and controls stay put.
const drawing=content=>`<g transform="translate(${W} 0) scale(-1 1)">${content}</g>`;
const figure=k.figureSvg({width:W,height:H,label:'CyberMachine R2 五盘 NAS。从完整外壳展开左侧板、I/O 面板、前后风扇与顶盖，底盖保持安装，展示主板接口布局、硬盘四点螺丝固定和 7 mm 垫片。',body:drawing(body)});
const plate=k.plateHtml({fig:'FIG 01 / R2',title:'CyberMachine · 5 BAY',hint:'拖动展开滑块 · 从完整外壳查看内部',readout:'完整外观 · 0%',
 keys:[{mark:'lit',label:'当前查看的组件'},{mark:'raised',label:'其余结构'}],
 caption:'0% 为完整外壳，展开时移开左侧板、I/O 面板、前后模块与顶盖，底盖保留。外壳公共轮廓依据仓库 CAD，主板与接口位置依据原厂 STEP；R2 四点固定单独展示。散热器与接口内部细节为示意，展开距离仅用于看清结构。',
 body:`<div class="iso-stage" tabindex="0" role="group" aria-label="交互结构图。左右键调节展开，空格切换装配与展开，数字 1 至 5 选盘。">${figure}</div>`});
const css=readFileSync(resolve(HERE,'style.css'),'utf8');
const live=readFileSync(resolve(HERE,'live.js'),'utf8');
const controls=`<section class="controls" aria-label="结构图控制">
 <div class="control-row"><span class="control-name">硬盘厚度</span><div class="segmented" aria-label="厚度模式"><button data-thickness="mixed" aria-pressed="true">混合安装</button><button data-thickness="9.5" aria-pressed="false">全 9.5 mm</button><button data-thickness="7" aria-pressed="false">全 7 mm</button></div></div>
 <div class="control-row"><label class="control-name" for="explode">展开程度</label><div class="range-row"><button class="small" id="assembled">完整外观</button><input id="explode" type="range" min="0" max="100" value="0" aria-label="展开程度"><button class="small" id="apart">剖开结构</button><output id="percent" for="explode">0%</output></div></div>
 <div class="control-row"><span class="control-name">查看组件</span><div class="segmented wrap" aria-label="高亮组件"><button data-focus="enclosure" aria-pressed="true">外壳 / 面板</button><button data-focus="drives" aria-pressed="false">硬盘</button><button data-focus="screws" aria-pressed="false">固定螺丝</button><button data-focus="guides" aria-pressed="false">导轨 / 托脚</button><button data-focus="shims" aria-pressed="false">7 mm 垫片</button><button data-focus="board" aria-pressed="false">主板 / 散热</button><button data-focus="fans" aria-pressed="false">三风扇</button></div></div>
 <div class="control-row"><span class="control-name">硬盘盘位</span><div class="drive-row"><div class="segmented" aria-label="硬盘盘位">${[1,2,3,4,5].map(i=>`<button data-select-drive="${i}" aria-pressed="${i===1}">${String(i).padStart(2,'0')}</button>`).join('')}</div><span id="drive-thickness">01 · 9.5 mm</span><button id="tour" class="tour" aria-pressed="false">开始巡览</button></div></div>
 </section>`;
const details=`<section class="details" aria-live="polite"><div class="detail-copy"><span class="eyebrow" id="detail-kicker">PRODUCT / FULL ENCLOSURE</span><h2 id="detail-title">完整外壳，与内部结构一一对应。</h2><p id="detail-text">拖动展开滑块查看内部。主板接口位置依据原厂 STEP，外壳公共轮廓依据仓库 CAD；R2 四点固定单独展示。</p></div><dl id="facts"><div><dt>主体外形</dt><dd>144×168 <small>mm</small></dd></div><div><dt>机箱高度</dt><dd>${SPEC.height} <small>mm</small></dd></div><div><dt>侧板厚度</dt><dd>3 <small>mm</small></dd></div></dl></section>`;
const html=k.pageHtml({title:'CyberMachine R2 · 交互结构图',theme,width:1120,body:`<style>${css}</style><header><div class="topline"><span>ENCLOSURE ANATOMY / 03.11.2026</span><button id="theme" aria-label="切换明暗主题">${theme==='light'?'深色':'浅色'} ↗</button></div><h1>从完整外壳，<br class="phone-break">看到四点锁固。</h1><p class="intro">CyberMachine R2 · Radxa Taco V1.61<br>7 / 9.5 mm 双规格 · 拓竹 P1S<br>144 × 168 × 210 mm · 另加 6 mm 脚垫</p></header>${plate}${controls}${details}<footer><p>前进风、后排风；顶扇向下吹 CM5 与 M.2。图中不模拟转速、温度或气流性能。</p><p>打印前先用试装件核对盘孔与配合公差；实际装配、振动和温度尚需实物验证。</p><p>本图为 R2 结构示意；当前下载为 R1 资料，固定方式不同，R2 打印文件未收录。</p><div class="links"><a href="../../assembly/r2/index.html">3D 分步装配教学 ↗</a><a href="../../../README.md">仓库与版本说明 ↗</a><a href="../../../hardware/enclosure/r1/print/CyberMachine-r1-fit-test-p1s.3mf">R1 试装件 3MF ↗</a><a href="../../assembly/r1.md">R1 打印与装配说明 ↗</a></div><span class="stamp">R2 DATUMS · MILLIMETRES · EXPLANATORY EXPLODE</span></footer>`,script:kitScript()+`\nconst MODEL=${JSON.stringify({P,SPEC})};\n`+live}).replace('<html lang="en">','<html lang="zh-CN">');
writeFileSync(resolve(OUT,`index${suffix}.html`),html);
for(const t of [0,1]){
 const selected=scenes[0];
 const standalone=k.figureSvg({width:W,height:H,standalone:theme,label:'CyberMachine R2 说明用装配与展开结构图',body:`<style>${css}</style><rect width="${W}" height="${H}" fill="${theme==='dark'?'#131313':'#fbfbfa'}"/>${drawing(`<g data-mode="mixed">${items(selected,t)}</g>`)}`})
  .replace('<svg ',`<svg width="${W}" height="${H}" style="width:${W}px;height:${H}px;max-height:none" `);
 writeFileSync(resolve(OUT,`${t?'exploded':'assembled'}${suffix}.svg`),standalone);
}
console.log(`built ${theme} · ${scenes[0].R.items.length} items · ${draft?'draft ordering':'settled ordering'}`);
