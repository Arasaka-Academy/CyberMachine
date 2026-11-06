// Export the SAME millimetre geometry used by the R2 figure, without its SVG.
import {mkdirSync,writeFileSync,readFileSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {makeScene,SPEC} from '../../../anatomy/r2/src/model.mjs';
import {BOARD} from '../../../anatomy/r2/src/reference.mjs';

const HERE=dirname(fileURLToPath(import.meta.url));
const ROOT=resolve(HERE,'../../../..');
const WORK=resolve(ROOT,'work/assembly-r2');
mkdirSync(WORK,{recursive:true});
const groups=new Map();
const labels={antennas:'两路内置 FPC 天线',feet:'脚垫',base:'底框','guide-front':'前导轨','guide-rear':'后导轨',right:'右侧框',left:'左侧板',saddle:'主板支架',standoffs:'主板隔离柱','board-screws':'TACO 固定螺丝',hatch:'底部检修盖','io-panel':'I/O 面板','front-panel':'前面板','rear-panel':'后面板',lid:'顶盖','front-fan':'前风扇与护网','rear-fan':'后风扇与护网','top-fan':'顶部风扇与护网',cm5:'Raspberry Pi CM5','cm5-cooler':'CM5 散热器','cm5-screws':'CM5 配套固定件','wifi-slot':'M.2 E-Key 插槽（补绘示意）',wifi:'E-Key 2230 无线模块', 'wifi-screw':'无线模块尾部固定螺丝'};
const Z={o:[0,0,0],a:[0,0,1],u:[1,0,0],v:[0,1,0]};
const rect=(x,y,w,d)=>[[x,y],[x+w,y],[x+w,y+d],[x,y+d]];
const circle=(x,y,r,n=32)=>Array.from({length:n},(_,i)=>[x+r*Math.cos(2*Math.PI*i/n),y+r*Math.sin(2*Math.PI*i/n)]);
const prism=(poly,z,h,holes=[])=>({kind:'prism',F:Z,poly,s0:z,s1:z+h,cut:holes.map(poly=>({kind:'prism',F:Z,poly,s0:z-.02,s1:z+h+.02}))});
const box=(x,y,z,w,d,h)=>prism(rect(x,y,w,d),z,h);
const cylinder=(x,y,z,r,h,inner=0)=>({kind:'body',F:{...Z,o:[x,y,0]},poly:[[z,inner],[z,r],[z+h,r],[z+h,inner]]});
function add(id,shape,material='shell',extra={}){
 if(!groups.has(id))groups.set(id,{id,label:labels[id]??id,shapes:[],...extra});
 const clean=structuredClone(shape);delete clean._b;delete clean._f;delete clean._clip;
 groups.get(id).shapes.push({shape:clean,material});
}
function groupOf(item){
 const n=item.name;
 if(n.startsWith('board.standoff'))return 'standoffs';
 if(n.startsWith('board.screw'))return 'board-screws';
 if(n.startsWith('saddle.'))return 'saddle';
 if(n.startsWith('cm5.mating'))return 'cm5';
 if(n.startsWith('cm5.fin')||n.startsWith('cm5.cooler'))return 'cm5-cooler';
 // Board, ports, CM5 carrier sockets and NVMe slot come from the native STEP.
 if(item.piece==='board')return null;
 if(n.startsWith('stand.foot.'))return 'feet';
 if(n.startsWith('stand.')||n.startsWith('base.')||n.startsWith('post.'))return 'base';
 if(n.startsWith('guide.mount.screw'))return n.endsWith('.46')?'guide-front':'guide-rear';
 if(n.startsWith('side.'))return n.includes('left')?'left':'right';
 if(n==='io.panel')return 'io-panel';
 if(n.startsWith('service-hatch')||n.startsWith('hatch.'))return 'hatch';
 if(n.startsWith('guide.'))return n.includes('.rear.')?'guide-rear':'guide-front';
 if(n.startsWith('screw.'))return `disk-screws-${item.drive}`;
 if(n.startsWith('drive'))return `drive-${item.drive}`;
 if(n.startsWith('shoe'))return `shoe-${item.drive}`;
 if(n.startsWith('shim'))return `shim-${item.drive}-${n.includes('108.75')?'rear':'front'}`;
 if(n==='front.panel')return 'front-panel';
 if(n==='rear.panel')return 'rear-panel';
 if(n==='lid')return 'lid';
 if(n.startsWith('front.'))return 'front-fan';
 if(n.startsWith('rear.'))return 'rear-fan';
 if(n.startsWith('top.'))return 'top-fan';
 throw new Error(`Unclassified R2 geometry: ${n}`);
}
const seven=makeScene('7');
for(const item of seven.R.items){
 const id=groupOf(item);if(!id)continue;
 if(id.startsWith('drive-'))continue;
 const drive=item.drive||0;
 const material=item.name.includes('screw')||item.name.includes('washer')||id==='standoffs'?'metal':id==='cm5'?'plastic':id==='cm5-cooler'?'aluminium':id.endsWith('-fan')?(item.name.includes('blade')?'plastic':'fan'):'shell';
 for(const shape of item.shapes){
  const geometry=structuredClone(shape);
  // CM5 chip packages rise 1.1 mm above the PCB; keep the cooler on their top.
  if(id==='cm5-cooler')geometry.F.o[2]+=1.1;
  // Relieve the nominal cooler base by 0.2 mm beside the native M-Key housing.
  if(item.name==='cm5.cooler.base')geometry.poly=geometry.poly.map(([x,y])=>[x,Math.min(y,98)]);
  add(id,geometry,material,{drive});
 }
}
for(const mode of ['7','9.5'])for(const item of makeScene(mode).R.items){
 if(!item.name.startsWith('drive'))continue;
 const id=`drive-${item.drive}-${mode==='7'?'7':'95'}`;
 const material=item.name.includes('contact')?'gold':item.name.includes('connector')?'plastic':item.name.includes('label')?'label':'disk';
 for(const shape of item.shapes)add(id,shape,material,{drive:item.drive,variant:mode});
}
// CM5 envelope and two mating connectors. Carrier halves are in the native STEP.
const cm5Holes=[37,88].flatMap(x=>[58.7,94.7].map(y=>[x,y]));
add('cm5',prism(rect(35,56.7,55,40),138.5,1.2,cm5Holes.map(([x,y])=>circle(x,y,1.375))),'pcb');
add('cm5',box(48,65,139.7,18,16,1.1),'chip');
add('cm5',box(70,67,139.7,12,9,1),'chip');
for(const [x,y]of cm5Holes){
 add('cm5-screws',cylinder(x,y,139.7,2.15,1),'metal');
 add('cm5-screws',cylinder(x,y,136.5,1.15,3.2),'metal');
}

// E-Key is absent from the supplied 3D STEP. Supplement it from the V1.61
// placement map's U33 footprint; its height is a nominal teaching envelope.
// The 2230 card runs toward -Y. It never substitutes for the M-Key NVMe slot.
const wifi={x:91,y:85.5,w:22,d:30,bottom:138.5,top:139.3,
 insertion:[102,115.5,138.9],entry:[102,113.5,138.9],mount:[102,87.5,139.3],
 antennas:[[94.5,90,140],[109.5,90,140]],pivot:[102,115.5,138.9]};
add('wifi-slot',box(90.6,113.5,135,22.8,7,3.5),'plastic');
add('wifi-slot',box(90.6,118.2,138.5,22.8,2.3,2.4),'plastic');
for(const x of [90.6,113])add('wifi-slot',box(x,113.5,139.4,.4,4.7,1.5),'plastic');
add('wifi-slot',cylinder(102,87.5,135,2.4,3.5,1.15),'metal');
const outline=[[91,85.5],[113,85.5],[113,115.5],[108.7,115.5],[108.7,112.5],[107.4,112.5],[107.4,115.5],[91,115.5]];
add('wifi',prism(outline,138.5,.8,[circle(102,87.5,1.5)]),'pcb');
add('wifi',box(93.2,93,139.3,17.6,16,1.4),'aluminium');
for(let i=0;i<40;i++){
 const x=91.5+i*.52;if(x>107.1&&x<109)continue;
 add('wifi',box(x,112.6,139.3,.28,2.6,.04),'gold');
}
for(const [x,y,z]of wifi.antennas){
 add('wifi',cylinder(x,y,139.3,1,0.7,.45),'gold');
}
add('wifi-screw',cylinder(102,87.5,139.3,2.2,1),'metal');
add('wifi-screw',cylinder(102,87.5,136.5,1.1,2.8),'metal');
// Two generic internal FPC antennas: adhesive mounting, no additional case holes.
for(const y of [62,100]){
 add('antennas',box(139.4,y-4,147,0.8,8,25),'plastic');
 add('antennas',box(139.3,y-3,151,0.1,6,18),'gold');
}
const antennaRoutes=wifi.antennas.map((start,i)=>[start,[start[0]+5,start[1]-5,146],[128,i?96:75,152],[139.3,i?100:62,150]]);

const parts=[...groups.values()].map(g=>({...g,label:labels[g.id]??
 (g.id.startsWith('drive-')?`${g.drive} 号 SATA 硬盘`:g.id.startsWith('shim-')?`${g.drive} 号薄盘垫片`:g.id.startsWith('shoe-')?`${g.drive} 号托脚`:`${g.drive} 号四点固定螺丝`)}));
const referenceNames=['docs/anatomy/r2/src/model.mjs','docs/anatomy/r2/src/reference.mjs','references/radxa-taco/radxa_taco_3d_stp_v1.61.stp','references/radxa-taco/radxa_taco_components_placement_map_v1.61.pdf'];
const sources=Object.fromEntries(referenceNames.map(n=>[n,createHash('sha256').update(readFileSync(resolve(ROOT,n))).digest('hex')]));
const data={units:'mm',renderMapping:'[x,z,-y]/1000',spec:SPEC,board:BOARD,wifi,antennaRoutes,
 anchors:{sata:SPEC.sata.map(x=>[x,76.5,122.7003]),drive:SPEC.sata.map(x=>[x,76.5,122.7]),cm5:[[65.0542,59.75,136.45],[65.0442,93.75,136.45]],wifi:wifi.insertion,wifiMount:wifi.mount,antenna:wifi.antennas},
 sources,parts};
writeFileSync(resolve(WORK,'analytic.json'),JSON.stringify(data));
writeFileSync(resolve(HERE,'catalog.json'),JSON.stringify({...data,parts:parts.map(({shapes,...part})=>part)},null,2)+'\n');
console.log(`Exported ${parts.length} logical parts; ${parts.reduce((n,p)=>n+p.shapes.length,0)} analytic shapes → ${WORK}`);
