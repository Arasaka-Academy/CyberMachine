import catalog from './catalog.json' with {type:'json'};

export {catalog};
export const clamp=(n,a=0,b=1)=>Math.max(a,Math.min(b,n));
export const ease=t=>{t=clamp(t);return t*t*(3-2*t);};
const travel=(p,a,b)=>1-ease((p-a)/(b-a));
function path(p,a,b,points){
 const t=clamp((p-a)/(b-a))*(points.length-1),i=Math.min(points.length-2,Math.floor(t)),u=ease(t-i);
 return points[i].map((n,j)=>n+(points[i+1][j]-n)*u);
}
export const thickness=(mode,bay)=>mode==='7'?7:mode==='9.5'?9.5:bay%2===0?7:9.5;
export const toWorld=([x,y,z])=>[x/1000,z/1000,-y/1000];
export const PHASES=[
 [
  {end:.16,title:'辨认底框与前后方向',copy:'I/O 朝前，检修口朝下。先清除支撑和毛刺，并完成热熔螺母操作。',focus:['base']},
  {end:.48,title:'前后导轨轻轻预紧',copy:'前导轨带独立托脚的安装位。保留整组导轨的调整量，暂不锁死。',focus:['guide-front','guide-rear']},
  {end:.70,title:'固定右侧框',copy:'让主板和硬盘的安装空间保持开放；左侧板、前后风扇模块稍后安装。',focus:['right']},
  {end:1,title:'安装主板支架与隔离柱',copy:'先在支架下方固定四根 6 mm 隔离柱。四个 TACO 安装孔不是规则矩形。',focus:['saddle','standoffs']},
 ],
 [
  {end:.20,title:'支撑 TACO，核对两组连接器',copy:'在稳固、绝缘的台面上支撑载板。核对 CM5 的方向，让两组 100-pin 接口同时对准。',focus:['taco','cm5']},
  {end:.55,title:'垂直压合，避免倾斜受力',copy:'在连接器所在区域均匀施力，并支撑载板下方。不要按散热器、接口外壳或板边来强行压合。',focus:['cm5']},
  {end:.75,title:'安装 CM5 配套固定件',copy:'确认两组连接器完全贴合，再使用模块或散热器配套的固定件；不要照搬 TACO 的螺丝长度。',focus:['cm5-screws']},
  {end:1,title:'安装散热器，检查高度',copy:'按散热器的说明安装导热材料与固定件。上舱预留包络最高 Z=170 mm，与顶扇至少相隔 10 mm。',focus:['cm5-cooler']},
 ],
 [
  {end:.18,title:'找到 E-Key，核对缺口',copy:'无线模块使用 E-Key 2230；旁边的 M-Key 2280 用于 NVMe。外形接近，不表示能互换。',focus:['wifi','wifi-slot']},
  {end:.46,title:'倾斜插入金手指',copy:'保持缺口方向一致，沿插槽方向轻推到位。不要把错误缺口或未对准的模块强压进去。',focus:['wifi']},
  {end:.76,title:'压平并固定尾部',copy:'轻压模块尾部，使半圆孔对准支撑点，再安装配套固定螺丝。不要用螺丝把悬空的卡板拉弯。',focus:['wifi-screw','wifi']},
  {end:1,title:'接入天线，整理余线',copy:'核对实际模块的端子与天线规格，垂直对正接头后扣合。走线避开风扇叶片，预留拆盖余量。',focus:['antennas']},
 ],
 [
  {end:.28,title:'确认方向与上方通道',copy:'CM5 和无线模块朝上，五个 SATA 插座朝下，I/O 朝机箱前方。顶盖和风扇模块保持拆下。',focus:['taco']},
  {end:.78,title:'对准四个不规则安装孔',copy:'将预装总成从上方放入，先同时对准四根隔离柱。避免让支架或工具碰到下方 SATA 插座。',focus:['taco','standoffs']},
  {end:1,title:'均匀固定主板',copy:'主板上方使用 M2.5×4 螺丝固定到 6 mm 隔离柱。上下螺丝的合计伸入量应小于柱长。',focus:['board-screws']},
 ],
 [
  {end:.08,title:'薄盘先加垫片',copy:'断电并支稳机箱，留出下方操作空间。7 mm 硬盘在正 X 侧放前后两条 2.5 mm 垫片；9.5 mm 不加。',focus:['shims']},
  {end:.60,title:'逐盘向上对准 SATA',copy:'沿导轨从下方向上托入，手动对准后自然插合。不能用壳体、托脚或螺丝把接口强行拉到位。',focus:['drives']},
  {end:.66,title:'确认整组导轨自然对准',copy:'五块硬盘都能自然插合后，再锁紧导轨四颗安装螺丝。调节导轨时避免给 SATA 接口施加侧向力。',focus:['guide-front','guide-rear']},
  {end:.84,title:'四点固定，托脚承重',copy:'每盘四颗 M3×6 加 0.5 mm 垫圈，前后各两颗；托脚刚好承托底端，不向上顶压 SATA。旋入深度以硬盘规格为准。',focus:['fasteners']},
  {end:1,title:'安装风扇与面板',copy:'前进风、后排风、顶扇向下。收好余线，安装面板、顶盖和检修盖，最后装脚垫，避免脚垫挡住检修盖边角。下方支撑用于展示操作空间。',focus:['closure']},
 ],
];
export const CHAPTERS=[
 {title:'先搭起开放的框架',short:'机箱准备',description:'底框、导轨与支架先就位。给之后的每一步，留出操作空间。',duration:16,parts:'底框 · 导轨 · 支架',note:'前后风扇模块、左侧板和底盖暂不安装。'},
 {title:'让两组接口一起对齐',short:'CM5 预装',description:'先在台面上完成计算模块与散热器的预装，再把总成放进机箱。',duration:16,parts:'TACO · CM5 · 散热器',note:'压合时支撑载板，不让连接器承受弯曲载荷。'},
 {title:'给无线模块留对插槽',short:'无线网卡',description:'找到 E-Key，插入 2230 模块，再完成固定与天线连接。',duration:16,parts:'E-Key 2230 · 天线',note:'通用模块示意。实际接头、固定件和驱动需按选定型号核对。'},
 {title:'把预装总成稳稳放入',short:'TACO 入箱',description:'保持接口方向正确，让四个安装孔同时对上隔离柱。',duration:14,parts:'预装主板 · 四根隔离柱',note:'I/O 朝前、SATA 朝下；顶盖保持开放。'},
 {title:'五块硬盘，逐一就位',short:'硬盘与收尾',description:'从薄盘垫片到四点固定，最后合上这台五盘 NAS。',duration:26,parts:'5×SATA · 固定件 · 风扇',note:'操作全程断电。SATA 对准后自然插合，托脚只承重。'},
];
export function phaseAt(chapter,progress){
 const phases=PHASES[chapter];let start=0;
 for(let i=0;i<phases.length;i++){
  const phase=phases[i];if(progress<phase.end||i===phases.length-1)return {...phase,index:i,start,fraction:clamp((progress-start)/(phase.end-start))};
  start=phase.end;
 }
}
const BOARD_PARTS=new Set(['taco','wifi-slot','cm5','cm5-cooler','cm5-screws','wifi','wifi-screw','antennas']);
const FRAME=new Set(['base','guide-front','guide-rear','right','saddle','standoffs']);
const CLOSURE=new Set(['left','io-panel','front-panel','rear-panel','lid','hatch','feet','front-fan','rear-fan','top-fan']);
const isBoard=id=>BOARD_PARTS.has(id);
export function movingBay(progress){return Math.min(5,Math.max(1,Math.floor((progress-.09)/.092)+1));}
function focused(id,focus,bay){
 return focus.some(f=>f===id||f==='shims'&&id.startsWith(`shim-${bay}-`)||f==='drives'&&id.startsWith(`drive-${bay}-`)||f==='fasteners'&&[ `disk-screws-${bay}`,`shoe-${bay}`].includes(id)||f==='closure'&&CLOSURE.has(id));
}

/** Pure pose function. Geometry stays in its original assembled coordinates. */
export function poseOf(id,state){
 const {chapter:c,progress:p,thicknessMode:mode,selectedBay:bay}=state;
 const phase=phaseAt(c,p);
 let visible=true,offset=[0,0,0],angle=0,pivot=[0,0,0],opacity=1;
 if(state.mode==='practice')return practicePose(id,state);
 if(id.startsWith('drive-')){
  const [,n,variant]=id.split('-');
  visible=c===4&&(variant==='7'?thickness(mode,+n)===7:thickness(mode,+n)===9.5);
  offset=[0,0,-167.25*travel(p,.09+(+n-1)*.092,.18+(+n-1)*.092)];
 }
 if(id.startsWith('shim-')){
  visible=c===4&&thickness(mode,+id.split('-')[1])===7;
  const side=id.endsWith('front')?20:-20;
  offset=path(p,0,.075,[[-170,side,-179],[-170,side,0],[0,side,0],[0,0,0]]);
 }
 if(id.startsWith('shoe-')){visible=c===4;offset=path(p,.66,.74,[[-170,-30,-150],[-170,-30,-50],[0,0,-50],[0,0,0]]);}
 if(id.startsWith('disk-screws-')){visible=c===4;offset=[0,0,0];opacity=p<.72?0:1;}
 if(FRAME.has(id)){
  visible=c===0||c>=3;
  if(c===0){
   if(id==='guide-front'||id==='guide-rear')offset=path(p,.16,.48,[[-145,0,-8],[-145,0,45],[0,0,45],[0,0,0]]);
   if(id==='right')offset=[65*travel(p,.48,.70),0,0];
   if(id==='saddle')offset=path(p,.70,.91,[[-340,0,-117.4],[-340,0,100],[0,0,100],[0,0,0]]);
   if(id==='standoffs')offset=path(p,.91,1,[[-210,-35,-127.4],[-210,-35,60],[0,0,60],[0,0,0]]);
  }
 }
 if(CLOSURE.has(id)){
  visible=c===4&&p>=(id==='io-panel'?.84:id==='hatch'?.97:id==='feet'?.99:.90);
  const t=travel(p,.90,.97);
  if(id==='left')offset=[-75*t,0,0];
  if(id==='front-panel'||id==='front-fan')offset=[0,-90*t,0];
  if(id==='io-panel')offset=path(p,.84,.90,[[0,-90,-36],[0,0,0]]);
  if(id==='rear-panel'||id==='rear-fan')offset=[0,90*t,0];
  if(id==='lid'||id==='top-fan')offset=[0,0,85*t];
  if(id==='hatch')offset=[0,0,-30*travel(p,.97,.99)];
  if(id==='feet'){visible=p>=.99;offset=[0,0,-20*travel(p,.99,1)];}
 }
 if(id==='board-screws'){visible=c>=3;offset=c===3?path(p,.78,1,[[-150,-20,-142],[-150,-20,30],[0,0,30],[0,0,0]]):[0,0,0];}
 if(isBoard(id)){
  visible=c>=1;
  offset=c===1||c===2?[0,0,-110]:c===3?path(p,0,.78,[[195,0,-110],[195,0,110],[0,0,110],[0,0,0]]):[0,0,0];
  if(c===1){
   if(id==='wifi'||id==='wifi-screw'||id==='antennas')visible=false;
   if(id==='cm5')offset= p<.20?path(p,0,.20,[[-85,-25,-136.45],[-85,-25,-72],[0,0,-72]]):[0,0,-110+38*travel(p,.20,.55)];
   if(id==='cm5-screws')offset=path(p,.55,.75,[[-150,30,-136.5],[-150,30,-80],[0,0,-80],[0,0,-110]]);
   if(id==='cm5-cooler')offset=path(p,.75,1,[[-85,65,-140.8],[-85,65,-75],[0,0,-75],[0,0,-110]]);
  }
  if(c===2){
   if(id==='antennas')visible=p>=.76;
   if(id==='wifi'){
    if(p<.18)offset=path(p,0,.18,[[64,-20,-138.5],[64,-20,-90],[0,-18,-110]]);
    else offset[1]=-18*travel(p,.18,.46);
    angle=p<.18?-.33*ease(p/.18):-.33*travel(p,.46,.70);pivot=catalog.wifi.pivot;
   }
   if(id==='wifi-screw')offset=path(p,.70,.76,[[46,-20,-136.5],[46,-20,-85],[0,0,-85],[0,0,-110]]);
  }
 }
 const active=state.pickedPart===id||focused(id,phase.focus,bay);
 if(c===4&&id.startsWith('drive-')&&+id.split('-')[1]!==bay&&p<.84)opacity=.22;
 return {visible:visible&&opacity>0,offset,angle,pivot,opacity,active};
}

export function cameraFor(state){
 const {chapter,progress,mode,selectedPart,installed=[]}=state;
 if(mode==='practice'){
  if(selectedPart==='taco'&&!installed.includes('taco'))return {position:[-380,-620,410],target:[160,80,95]};
  const boardFocus=['cm5','wifi','antennas'].includes(selectedPart)&&!installed.includes('taco');
  if(boardFocus)return {position:[385,-85,160],target:[270,84,35]};
  return {position:[-400,-570,290],target:[130,85,40]};
 }
 return [
  progress<.70?{position:[-430,-530,345],target:[0,78,93]}:{position:[-260,-370,275],target:[65,80,110]},
  progress<.2?{position:[210,-160,200],target:[36,92,25]}:{position:[170,-90,185],target:[65,77,35]},
  progress<.18?{position:[225,165,150],target:[122,95,30]}:{position:[190,160,140],target:[100,103,30]},
  progress<.78?{position:[-435,-590,410],target:[150,80,152]}:{position:[-170,-245,310],target:[65,85,143]},
  progress<.66?{position:[-385,-545,205],target:[72,77,38]}:
  progress<.78?{position:[-135,-180,144],target:[catalog.spec.sata[state.selectedBay-1],58,74]}:
  progress<.84?{position:[-135,335,144],target:[catalog.spec.sata[state.selectedBay-1],98,74]}:
  {position:[-410,-590,270],target:[72,80,45]},
 ][chapter];
}

export function requiredActions(mode){
 return ['frame','cm5','wifi','antennas','taco',
  ...[1,2,3,4,5].filter(i=>thickness(mode,i)===7).map(i=>`shim-${i}`),
  ...[1,2,3,4,5].flatMap(i=>[`drive-${i}`,`fix-${i}`]),'close'];
}
export function actionLabel(id){
 const n=id.split('-')[1];
 return {frame:'框架与导轨',cm5:'CM5 与散热器',wifi:'E-Key 2230 网卡',antennas:'两路天线',taco:'TACO 主板总成',close:'风扇与封盖'}[id]??
 (id.startsWith('shim-')?`${n} 号盘 · 两条垫片`:id.startsWith('drive-')?`${n} 号 SATA 硬盘`:`${n} 号盘 · 四颗侧螺丝与托脚`);
}
export function targetFor(id){
 return {frame:'frame',cm5:'cm5-socket',wifi:'e-key',antennas:'antenna',taco:'board-mount',close:'enclosure'}[id]??`bay-${id.split('-')[1]}`;
}
export function targetAnchor(target){
 if(target.startsWith('bay-'))return [catalog.spec.sata[+target.split('-')[1]-1],38,74];
 return {frame:[72,46,25],'cm5-socket':[65,77,140],'e-key':[102,105,141],'m-key':[39,109,143],antenna:[102,90,143],'board-mount':[72,77,145],enclosure:[72,80,211]}[target]??[72,80,100];
}
export function tryInstall(installed,id,target,mode){
 const no=reason=>({ok:false,reason,installed});
 if(!requiredActions(mode).includes(id))return no('当前厚度不需要这个零件。');
 if(target!==targetFor(id))return no(id==='wifi'&&target==='m-key'?'这里是 M-Key NVMe 插槽。无线网卡请装入 E-Key 插槽。':'这个位置与零件不对应，请选择高亮的安装位置。');
 if(installed.includes(id))return no('这个零件已经安装好了。');
 const missing=ids=>ids.filter(x=>!installed.includes(x));
 let needs=[];
 if(id==='antennas')needs=['wifi'];
 if(id==='taco')needs=['frame','cm5','wifi','antennas'];
 if(id.startsWith('shim-'))needs=['taco'];
 if(id.startsWith('drive-')){
  const n=+id.split('-')[1];needs=['taco',...(thickness(mode,n)===7?[`shim-${n}`]:[])];
 }
 if(id.startsWith('fix-'))needs=[`drive-${id.split('-')[1]}`];
 if(id==='close')needs=requiredActions(mode).filter(x=>x!=='close');
 const todo=missing(needs);
 if(todo.length)return no(`请先安装${todo.slice(0,2).map(actionLabel).join('、')}${todo.length>2?`，还有 ${todo.length-2} 项`:''}。`);
 return {ok:true,installed:[...installed,id],reason:id==='close'?'装配练习完成。五个盘位已固定，机箱已合拢。':`${actionLabel(id)}已就位。`};
}
export function resetStorage(installed){return installed.filter(id=>['frame','cm5','wifi','antennas','taco'].includes(id));}

function practicePose(id,state){
 const {installed,selectedPart,thicknessMode:mode}=state;
 const has=n=>installed.includes(n);
 let visible=false,offset=[0,0,0],opacity=1,active=false;
 if(id==='base')visible=true;
 if(FRAME.has(id)){visible=id==='base'||has('frame')||selectedPart==='frame';active=selectedPart==='frame';if(!has('frame')&&id!=='base')offset=[0,0,30];}
 if(isBoard(id)){
  offset=has('taco')?[0,0,0]:[195,0,-110];
  visible=id==='taco'||id==='wifi-slot';
  if(id.startsWith('cm5')){visible=has('cm5')||selectedPart==='cm5';if(!has('cm5'))offset[2]+=30;active=selectedPart==='cm5';}
  if(id==='wifi'||id==='wifi-screw'){visible=has('wifi')||selectedPart==='wifi';if(!has('wifi'))offset[2]+=20;active=selectedPart==='wifi';}
  if(id==='antennas'){visible=has('antennas')||selectedPart==='antennas';active=selectedPart==='antennas';}
  if(id==='taco'||id==='wifi-slot')active=selectedPart==='taco';
 }
 if(id==='board-screws')visible=has('taco');
 if(id.startsWith('drive-')){
  const [,n,v]=id.split('-');visible=(has(`drive-${n}`)||selectedPart===`drive-${n}`)&&(v==='7'?thickness(mode,+n)===7:thickness(mode,+n)===9.5);
  active=selectedPart===`drive-${n}`;if(!has(`drive-${n}`))offset=[0,0,-167.25];
 }
 if(id.startsWith('shim-')){const action=`shim-${id.split('-')[1]}`;visible=(has(action)||selectedPart===action)&&thickness(mode,+id.split('-')[1])===7;active=selectedPart===action;if(!has(action))offset=[0,id.endsWith('front')?20:-20,0];}
 if(id.startsWith('shoe-')||id.startsWith('disk-screws-')){const n=id.split('-').at(-1);visible=has(`fix-${n}`);active=selectedPart===`fix-${n}`;}
 if(CLOSURE.has(id)){visible=has('close');active=selectedPart==='close';}
 if(visible&&!has('close')&&id.startsWith('drive-')&&selectedPart?.split('-')[1]!==id.split('-')[1])opacity=.3;
 return {visible,offset,opacity,active,angle:0,pivot:[0,0,0]};
}

export function cableState(state){
 const pose=poseOf('antennas',state);
 const attached=state.mode==='practice'?state.installed.includes('antennas'):state.chapter>=3||state.chapter===2&&state.progress===1;
 const lift=state.mode==='practice'?(attached?0:8):state.chapter===2?9*travel(state.progress,.76,1):0;
 return {...pose,lift,attached};
}
