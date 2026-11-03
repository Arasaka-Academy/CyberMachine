const {P,SPEC}=MODEL;
const stage=document.querySelector('.iso-stage'),svg=stage.querySelector('svg');
const groups=new Map([...svg.querySelectorAll('[data-mode]')].map(el=>[el.dataset.mode,{el,items:[...el.children].map(el=>({el,key:+el.dataset.key,lift:+el.dataset.lift,move:el.dataset.move.split(',').map(Number),piece:el.dataset.piece,drive:+el.dataset.drive,name:el.dataset.name})),order:''}]));
const range=document.querySelector('#explode'),percent=document.querySelector('#percent'),readout=document.querySelector('[data-readout]');
const still=matchMedia('(prefers-reduced-motion: reduce)');
const focusOrder=['enclosure','drives','screws','guides','shims','board','fans'];
let mode='mixed',focus='enclosure',drive=1,x=0,target=0,frame=0,last=0,visible=true,touring=false,tourClock=0,idleTimer=0,lastDrawX=null,lastDrawMode=null;
const $=s=>document.querySelector(s),clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const thicknessOf=i=>mode==='7'?7:mode==='9.5'?9.5:i%2===0?7:9.5;
const descriptions={
 enclosure:{kicker:()=>`PRODUCT / FULL ENCLOSURE`,title:'完整外壳，与内部结构一一对应。',text:'左侧板、凹入式 I/O 面板和底部检修盖均保留。拖动展开滑块查看内部；双网口、双层 USB-A、HDMI、USB-C 和 DC 按原厂 STEP 的位置排列。面板开孔与独立护网依据仓库 CAD。',facts:[['主体外形','144×168','mm'],['机箱高度',SPEC.height,'mm'],['侧板厚度',3,'mm']]},
 drives:{kicker:()=>`DRIVE ${String(drive).padStart(2,'0')} / ${thicknessOf(drive)} MM`,title:'同一 SATA 基准，两种厚度。',text:'9.5 mm 硬盘直接安装；7 mm 硬盘在正 X 侧增加 2.5 mm 可拆垫片，保持底面与 SATA 插接位置一致。',facts:[['盘位间距',SPEC.pitch,'mm'],['每盘固定',4,'颗 M3'],['硬盘螺丝总数',20,'颗']]},
 screws:{kicker:()=>`DRIVE ${String(drive).padStart(2,'0')} / FOUR-POINT MOUNT`,title:'前后各两颗，支架承担重量。',text:'每盘使用四颗 M3×6 侧固定螺丝及 0.5 mm 垫圈。先拆前后风扇模块，露出操作面。此视图淡显选中硬盘与导轨，显示前后四个固定点；螺丝埋入部分省略。',facts:[['两孔纵向间距',SPEC.sidePitch,'mm'],['距硬盘底面',SPEC.sideOffset,'mm'],['名义旋入深度',SPEC.engagement,'mm']]},
 guides:{kicker:()=>`DRIVE ${String(drive).padStart(2,'0')} / SERVICE ACCESS`,title:'独立承托，从底部逐盘维护。',text:'导轨约束盘位，独立托脚承担硬盘重量。维护时需拆前后风扇、卸下该盘四颗螺丝与托脚，再打开底部检修盖。图中底盖保持安装，未模拟硬盘抽取和底盖拆卸路径。',facts:[['独立托脚',5,'组'],['导轨长圆孔','3.4×6.4','mm'],['硬盘厚度',thicknessOf(drive),'mm']]},
 shims:{kicker:()=>`7 MM ADAPTER / +X SIDE`,title:'薄了 2.5 mm，定位面保持一致。',text:'每块 7 mm 硬盘使用前后两条可拆垫片；9.5 mm 硬盘不安装垫片。此视图淡显选中硬盘与导轨，露出正 X 侧间隙；螺丝孔位与 SATA 定位基准共用。',facts:[['垫片厚度',SPEC.shim,'mm'],['每盘垫片',2,'条'],['选中盘厚度',thicknessOf(drive),'mm']]},
 board:{kicker:()=>`UPPER CHAMBER / CM5 + M.2`,title:'主板在上，给散热器留出空间。',text:'Taco 水平安装，CM5 与 M.2 朝上。主板以上预留 35 mm 散热器包络，包络顶部与 92 mm 顶扇下沿之间至少留 10 mm。散热马甲在图中为示意外形。',facts:[['散热器包络',35,'mm'],['包络上方净距',SPEC.topFanBottom-SPEC.heatsinkCeiling,'mm'],['主板安装螺丝','M2.5','']]},
 fans:{kicker:()=>`COOLING / 120 + 120 + 92`,title:'前后通风，顶扇照顾上舱。',text:'前后各一只 120×120×25 mm 风扇，前进后出；顶盖安装 92×92×25 mm 风扇向下吹 CM5 与 M.2，上舱从侧面排热。扇叶保持静止，不表示实际转速。',facts:[['前后风扇','120','mm'],['顶部风扇',92,'mm'],['风扇厚度',25,'mm']]}
};
function textUI(){
 document.querySelectorAll('[data-thickness]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.thickness===mode));
 document.querySelectorAll('[data-focus]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.focus===focus));
 document.querySelectorAll('[data-select-drive]').forEach(b=>b.setAttribute('aria-pressed',+b.dataset.selectDrive===drive));
 $('#drive-thickness').textContent=String(drive).padStart(2,'0')+' · '+thicknessOf(drive)+' mm';
 const desc=descriptions[focus]; $('#detail-kicker').textContent=desc.kicker();$('#detail-title').textContent=desc.title;$('#detail-text').textContent=desc.text;
 $('#facts').innerHTML=desc.facts.map(([label,value,unit])=>`<div><dt>${label}</dt><dd>${value} <small>${unit}</small></dd></div>`).join('');
 $('#tour').textContent=touring?'暂停巡览':'开始巡览';$('#tour').setAttribute('aria-pressed',touring);
 for(const g of groups.values())for(const it of g.items){
  const active=it.piece===focus&&(!it.drive||it.drive===drive);
  it.el.toggleAttribute('data-active',active);
  it.el.toggleAttribute('data-ghost',(focus==='screws'||focus==='shims')&&(it.name==='io.panel'||it.drive===drive&&(it.piece==='guides'||it.name===`drive${drive}.body`)));
 }
}
function draw(){
 const g=groups.get(mode);
 if(lastDrawX!==x||lastDrawMode!==mode){
  for(const it of g.items)if(it.move.some(n=>n!==0))it.el.setAttribute('transform',translateAlong(P,it.move.map(n=>n*x)));
  const sorted=[...g.items].sort((a,b)=>a.key+a.lift*x-b.key-b.lift*x);
  const order=sorted.map(it=>it.name).join('|');
  if(order!==g.order){for(const it of sorted)g.el.appendChild(it.el);g.order=order;}
  lastDrawX=x;lastDrawMode=mode;
 }
 const value=Math.round(x*100),label=x<.001?'完整外观':x>.999?'完全展开':'剖开展示';
 range.value=Math.round(target*100);percent.value=Math.round(target*100)+'%';const line=label+' · '+value+'%';if(readout.textContent!==line)readout.textContent=line;
 stage.setAttribute('aria-description',label+'，展开 '+value+'%，当前查看'+descriptions[focus].title);
}
function tick(now){
 const dt=last?Math.min((now-last)/1000,.05):1/60;last=now;
 if(touring&&!still.matches){tourClock+=dt;if(tourClock>=4.8){tourClock=0;focus=focusOrder[(focusOrder.indexOf(focus)+1)%focusOrder.length];textUI();}}
 x=still.matches?target:x+(target-x)*(1-Math.exp(-dt/.31));
 if(Math.abs(target-x)<.0001)x=target;
 draw();frame=visible&&(x!==target||touring&&!still.matches)?requestAnimationFrame(tick):0;
}
function run(){if(!frame&&visible&&!document.hidden){last=0;frame=requestAnimationFrame(tick);}}
function pause(){touring=false;clearTimeout(idleTimer);textUI();}
function steer(value){pause();target=clamp(+value,0,1);draw();run();}
function setMode(next){if(!groups.has(next))return;mode=next;for(const [key,g]of groups)g.el.style.display=key===mode?'':'none';textUI();draw();}
function select(piece,index){pause();if(focusOrder.includes(piece))focus=piece;if(index)drive=clamp(+index,1,5);if(focus!=='enclosure'&&target<.65)target=.8;textUI();draw();run();}
range.addEventListener('input',()=>steer(+range.value/100));$('#assembled').addEventListener('click',()=>steer(0));$('#apart').addEventListener('click',()=>steer(1));
document.querySelectorAll('[data-thickness]').forEach(b=>b.addEventListener('click',()=>{pause();setMode(b.dataset.thickness);}));
document.querySelectorAll('[data-focus]').forEach(b=>b.addEventListener('click',()=>{select(b.dataset.focus);if(focus==='shims'&&thicknessOf(drive)!==7)setMode('7');}));
document.querySelectorAll('[data-select-drive]').forEach(b=>b.addEventListener('click',()=>select(focus,b.dataset.selectDrive)));
$('#tour').addEventListener('click',()=>{touring=!touring;tourClock=0;if(touring&&target<.65)target=.8;textUI();run();});
$('#theme').addEventListener('click',()=>{const light=document.body.dataset.theme!=='light';document.body.dataset.theme=light?'light':'dark';$('#theme').textContent=light?'深色 ↗':'浅色 ↗';});
stage.addEventListener('click',e=>{const it=e.target.closest('.part');if(it)select(it.dataset.piece,it.dataset.drive);});
stage.addEventListener('pointerover',e=>{const it=e.target.closest('.part');stage.style.cursor=it?'pointer':'default';});
stage.addEventListener('keydown',e=>{
 if(['ArrowRight','ArrowLeft','Home','End',' ','Escape','1','2','3','4','5'].includes(e.key))e.preventDefault();
 if(e.key==='ArrowRight')steer(target+.1);else if(e.key==='ArrowLeft')steer(target-.1);else if(e.key==='Home')steer(0);else if(e.key==='End')steer(1);else if(e.key===' ')steer(target>.5?0:1);else if(e.key==='Escape')pause();else if(/^[1-5]$/.test(e.key))select(focus,+e.key);
});
new IntersectionObserver(entries=>{visible=entries.at(-1).isIntersecting;if(visible)run();else{cancelAnimationFrame(frame);frame=0;}},{rootMargin:'80px 0px'}).observe(stage);
document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;}else run();});
still.addEventListener('change',()=>{if(still.matches)pause();run();});
window.__cybermachine={get state(){return {mode,focus,drive,x,target,touring,visible,reduced:still.matches};},set({mode:m,focus:f,drive:d,explode:e}={}){pause();if(m)setMode(m);if(f)focus=f;if(d)drive=d;if(e!==undefined){x=target=clamp(e,0,1);}textUI();draw();},animate(e){steer(e);}};
textUI();draw();run();
