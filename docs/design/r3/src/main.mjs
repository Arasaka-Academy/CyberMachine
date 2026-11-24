/**
 * [INPUT]: R3 CAD、四点锁盖与双件骨架 metadata、three.js 与视口测量。
 * [OUTPUT]: CAD 外形、五盘7mm、水平6mm通风横带、板底及锁盖审阅。
 * [POS]: 场景直接消费 CAD；取景与拆解保留真实尺寸和 SATA 基准。
 * [PROTOCOL]: Update this header on change, then check AGENTS.md
 */
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import encodedModel from 'virtual:r3-model';
import metadata from 'virtual:r3-metadata';
import {IoReview} from './io-review.mjs';
import {measureSubjects} from './frame-guard.mjs';
import './style.css';
import './responsive.css';

const $=selector=>document.querySelector(selector);
const all=selector=>[...document.querySelectorAll(selector)];
const stage=$('#stage');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const state={view:'appearance',explode:.65,bay:0,theme:'light',side:'top',io:false,port:null,topView:false,rearView:false,bonesOnly:false,ready:false};
const ioMode=()=>state.view==='appearance'&&state.io;
const topMode=()=>state.view==='appearance'&&!state.io&&state.topView;
const rearMode=()=>state.view==='appearance'&&!state.io&&state.rearView;
const structuralKinds=['spine','rear-fan-frame'];
const coverKinds=['lid','top-fan','lid-fasteners'];
const enclosureParts=metadata.parts?.filter(part=>['shell','lid'].includes(part.name))??[];
const enclosureSizeMm=enclosureParts.length?[0,1,2].map(axis=>Math.max(...enclosureParts.map(part=>part.boundsMm[1][axis]))-Math.min(...enclosureParts.map(part=>part.boundsMm[0][axis]))):[154,144,194];
const enclosureSizeLabel=enclosureSizeMm.map(value=>Number(value.toFixed(2))).join(' × ')+' mm';
const notes={
 appearance:{number:'01 / 一体外观',title:'让通风，<br>也有韵律。',copy:'顶部同心纹与前后管风琴式槽阵呼应。上盖沿内止口定位，四处内置厚座承接四颗竖向 M3；螺丝头藏入顶面沉孔，保留连续圆角外观。',caption:'一体外观',detail:enclosureSizeLabel,facts:[['上盖锁紧','四点 4 颗竖向 M3'],['名义合盖缝','0.30 mm'],['止口单侧间隙','0.35 mm']]},
 exploded:{number:'02 / 结构拆解',title:'主架一体，<br>后框平印。',copy:'主骨架保持一体，后风扇框平印并沿用风扇螺丝。五个同款托架独立固定硬盘；顶扇随盖拆卸。四颗盖螺丝的共同位移仅作示意，实装须先完整旋出。',caption:'结构拆解',detail:'9 个主要打印件 · 风扇与五金另计',facts:[['外壳','底壳 + 整体上盖'],['内部','主骨架 + 后扇框 + 5 托架'],['展示位移','不代表装配行程']]},
 clearance:{number:'03 / 主板净空',title:'四点承托，<br>板底留空。',copy:'主板保留原厂 STEP 的正反面元件。四个小承托台只接触安装孔周围，取消横跨板底的托板；可以翻到背面观察 SATA 与支撑位置。',caption:'主板与孔周承托',detail:'真实原厂元件 · 座接接触除外',facts:[['孔周承托台','Ø5 mm'],['承托台至原厂器件','最小 1.87 mm¹'],['原厂两面下凸 / 上凸','10.70 / 15.50 mm']]},
 bench:{number:'04 / 箱外预装',title:'在箱外装好，<br>整组放入。',copy:'先在开放的主骨架上安装主板和散热器，再安装五块 7 mm 硬盘与托架、插接 SATA。后风扇框靠定位键就位，与风扇共用四颗 M3×35；总成入箱后，从壳底锁紧。',caption:'箱外预装总成',detail:'固定五盘 7 mm · 主板与盘托独立固定',facts:[['预装对象','主板 / 五盘 / 后风扇'],['总成固定','壳底 4 颗 M3'],['上盖固定','四点 4 颗 M3×25']]},
};
const holes=[[20.1,60.2],[12.9,116.95],[105,60.2],[119.45,116.9]];
const toWorld=([x,y,z])=>new THREE.Vector3(x/1000,z/1000,-y/1000);
const scene=new THREE.Scene();
const camera=new THREE.PerspectiveCamera(32,1,.005,10);
const semantic=new Map();
let renderer,controls,root,floor,ringGroup,ioReview,raf=0,visible=true,dirty=true,settle=0;
let dragging=false,pointerDown=null;
let desiredCamera,desiredTarget;
const base=new Map();
const materials=[];

function applyTheme(){
 const dark=state.theme==='dark';
 document.documentElement.classList.toggle('dark',dark);
 $('#theme').setAttribute('aria-label',`切换${dark?'浅':'深'}色主题`);
 scene.background=new THREE.Color(dark?'#27372e':'#e9ede4');
 scene.fog=new THREE.Fog(dark?'#27372e':'#e9ede4',1.25,3.5);
 if(floor)floor.material.color.set(dark?'#27372e':'#e9ede4');
 for(const {mesh,kind} of materials){
  if(kind==='shell'||kind==='lid')mesh.material.color.set(dark?'#bcc5b5':'#dce3d4');
  else if(kind==='lid-fasteners')mesh.material.color.set(dark?'#9ba99e':'#59665e');
  else if(structuralKinds.includes(kind))mesh.material.color.set(dark?'#7d9c83':'#477d64');
  else if(kind.startsWith('carrier'))mesh.material.color.set(dark?'#6b8873':'#859d89');
  else if(kind.startsWith('drive'))mesh.material.color.set(state.bay===Number(kind.split('-')[1])?(dark?'#c1dfbe':'#4f9670'):(dark?'#a7b6a4':'#bac5b4'));
 }
 ioReview?.sync(ioMode(),state.port,dark);
 invalidate();
}
function invalidate(){dirty=true;settle=12;if(!raf&&renderer&&visible&&!document.hidden)raf=requestAnimationFrame(frame);}
function resize(){
 const {width,height}=stage.getBoundingClientRect();
 if(!renderer||!width||!height)return;
 renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();
 resetCamera(true);invalidate();
}
function settings(){
 if(ioMode()){const view=ioReview?.camera(state.port);if(view)return view;}
 if(topMode()){
  const box=new THREE.Box3();
  for(const kind of coverKinds){const node=semantic.get(kind);if(node)box.union(new THREE.Box3().setFromObject(node));}
  return {target:box.isEmpty()?[.072,.182,-.100]:box.getCenter(new THREE.Vector3()).toArray(),offset:[.09,.38,.15],fov:32,box:box.isEmpty()?null:box};
 }
 if(rearMode()){
  const box=root?new THREE.Box3().setFromObject(root):null;
  return {target:box?box.getCenter(new THREE.Vector3()).toArray():[.072,.097,-.100],offset:[-.27,.16,-.42],fov:32,box};
 }
 if(state.view==='clearance')return state.side==='bottom'?{target:[.069,.128,-.083],offset:[.17,-.095,.20],fov:30}:{target:[.069,.13,-.083],offset:[.18,.17,.19],fov:30};
 if(state.view==='bench'){
  const box=new THREE.Box3();
  for(const node of semantic.values())if(node.visible)box.union(new THREE.Box3().setFromObject(node));
  return {target:box.isEmpty()?[.072,.09,-.104]:box.getCenter(new THREE.Vector3()).toArray(),offset:state.bonesOnly?[.25,.16,.30]:[.26,.21,.30],fov:32,box:box.isEmpty()?null:box};
 }
 if(state.view==='exploded'){
  const box=new THREE.Box3();
  for(const node of semantic.values())if(node.visible)box.union(new THREE.Box3().setFromObject(node));
  return {target:box.isEmpty()?[.072-.040*state.explode,.11+.04*state.explode,-.10]:box.getCenter(new THREE.Vector3()).toArray(),offset:[.32+.20*state.explode,.23+.14*state.explode,.37+.20*state.explode],fov:32,box:box.isEmpty()?null:box};
 }
 return {target:[.072,.085,-.100],offset:[.32,.22,.375],fov:32,box:root?new THREE.Box3().setFromObject(root):null};
}
function resetCamera(immediate=false){
 if(!controls)return;
 const s=settings();
 const aspect=stage.clientWidth/stage.clientHeight;
 const fit=Math.max(1,.94/aspect)*(state.view==='clearance'&&aspect<1?1.25:1);
 desiredTarget=new THREE.Vector3(...s.target);
 desiredCamera=desiredTarget.clone().add(new THREE.Vector3(...s.offset).multiplyScalar(fit));
 if(s.box){
  const preview=new THREE.PerspectiveCamera(s.fov,aspect,.005,10);
  for(let attempt=0;attempt<30;attempt++){
   preview.position.copy(desiredCamera);preview.lookAt(desiredTarget);preview.updateMatrixWorld();
   let inside=true;
   for(let i=0;i<8;i++){const p=new THREE.Vector3(i&1?s.box.max.x:s.box.min.x,i&2?s.box.max.y:s.box.min.y,i&4?s.box.max.z:s.box.min.z).project(preview);if(Math.abs(p.x)>.82||Math.abs(p.y)>.76)inside=false;}
   if(inside)break;desiredCamera.sub(desiredTarget).multiplyScalar(1.08).add(desiredTarget);
  }
 }
 camera.fov=s.fov;camera.updateProjectionMatrix();
 controls.minPolarAngle=state.view==='clearance'?.1:.12;
 controls.maxPolarAngle=state.view==='clearance'?Math.PI-.12:Math.PI/2-.025;
 controls.minDistance=ioMode()?.045:.17;
 dragging=false;
 if(immediate||reduced.matches){camera.position.copy(desiredCamera);controls.target.copy(desiredTarget);controls.update();}
 invalidate();
}
function modeUI(){
 const n=notes[state.view];
 $('#note-number').textContent=n.number;
 $('#note-title').innerHTML=n.title;
 $('#note-copy').textContent=n.copy;
 let facts=n.facts;
 if(topMode()){
  const fan=metadata.topFan,size=fan?.nominalSizeMm;
  const margins=size?[(enclosureSizeMm[0]-size[0])/2,(enclosureSizeMm[1]-size[1])/2].map(value=>Number(value.toFixed(2))):null;
  $('#note-number').textContent='01 / 同心顶纹';$('#note-title').textContent='风扇居中，纹路向外展开。';
  $('#note-copy').textContent='外侧四颗 M3 竖向压紧厚座，内侧四颗固定顶扇，头部均低于顶面。同心断环围绕中心展开。断电后完整旋出外侧盖螺丝，再小幅提盖并断开顶扇接头；线束与装配需试装。';
  facts=[['顶扇含垫包络',size?`${size.join(' × ')} mm`:'当前模型未附'],['四点竖向锁盖','4 颗 M3×25'],['顶扇左右 / 前后边距',margins?`${margins.join(' / ')} mm`:'读取 CAD 元数据'],['扇框至散热器包络',Number.isFinite(fan?.coolerNominalGapMm)?`${fan.coolerNominalGapMm} mm`:'待数字检查']];
 }
 if(rearMode()){
  $('#note-number').textContent='01 / 管风琴槽阵';$('#note-title').textContent='分段错落，前后呼应。';
  $('#note-copy').textContent='十五列圆端槽以对称缓拱收边，上下两排槽端沿水平横带齐平。6 mm 等宽连接带直接成形在底壳；后上舱延续圆端短槽。开孔面积由数字检查记录，实际风量与格栅刚度待测。';
  facts=[['槽阵构图','15 列 / 对称缓拱'],['连接横带','水平等宽 6 mm'],['开孔边缘','圆端 / 分段'],['后部风扇','120 × 25 mm']];
 }
 if(ioMode()){
  const port=ioReview?.ports.find(p=>p.id===state.port);
  $('#note-number').textContent='01 / I/O 细节';$('#note-title').textContent=port?.label??'逐个接口，对齐实际截面。';
  $('#note-copy').textContent='轮廓线来自本次 CAD 的孔口截面。选中项目后，同时强调对应开孔与原厂实体。前缘包络退距只描述数字模型；插头包胶、卡扣、插入行程与按钮操作需实物核对。';
  facts=ioReview?.facts(state.port)??[['接口截面','当前模型未附']];
 }
 if(state.view==='bench'&&state.bonesOnly){
  const frame=metadata.frameReinforcement;
  $('#note-title').textContent='主骨架一体，后扇框平印。';
  $('#note-copy').textContent='纵肋、斜撑和主板立柱根筋保留在主骨架，底脚连筋把锁点接入底框。开窗顶部收成 45° 尖顶，后风扇框分开平印并沿用风扇螺丝固定；刚度、振动与实物装配待测。';
  facts=[['纵肋厚 / 斜撑宽',frame?`${frame.longitudinalWebThicknessMm} / ${frame.diagonalWidthMm} mm`:'读取 CAD 元数据'],['底框高 / 后扇立柱厚',frame?`${frame.baseHeightMm} / ${frame.rearFanUprightThicknessMm} mm`:'读取 CAD 元数据'],['后框与风扇共用','4 颗 M3×35']];
 }
 $('#note-facts').replaceChildren(...facts.map(([label,value])=>{const row=document.createElement('div');row.className='fact';const name=document.createElement('span'),content=document.createElement('b');name.textContent=label;content.textContent=value;row.append(name,content);return row;}));
 if(state.view==='clearance'){const footnote=document.createElement('p');footnote.className='clearance-footnote';footnote.textContent='¹ 本次数字实体检查；仅覆盖原厂主板。CM5、散热器和实物焊脚另测。';$('#note-facts').append(footnote);}
 $('#view-caption').textContent=n.caption;
 $('#view-detail').textContent=n.detail;
 if(ioMode()){$('#view-caption').textContent=ioReview?.ports.find(p=>p.id===state.port)?.label??'I/O 逐口检视';$('#view-detail').textContent='CAD 孔口截面 · 原厂接口实体';}
 if(topMode()){$('#view-caption').textContent='四点锁盖与同心格栅';$('#view-detail').textContent='四颗 M3 竖向锁紧 · 顶扇随盖拆卸';}
 if(rearMode()){$('#view-caption').textContent='后部格栅与排风';$('#view-detail').textContent='一体开孔 · 实际风量待测';}
 if(state.view==='bench'&&state.bonesOnly){$('#view-caption').textContent='主骨架与后风扇框';$('#view-detail').textContent='一体承力主架 · 平印后框 · 共用风扇螺丝';}
 $('#explode-control').hidden=state.view!=='exploded';
 $('#board-side').hidden=state.view!=='clearance';
 $('#board-side').textContent=state.side==='top'?'看板背面 ↺':'看板正面 ↺';
 $('#io-detail').hidden=state.view!=='appearance';$('#io-detail').disabled=!ioReview?.ports.length;
 $('#io-detail').textContent=ioMode()?'整体外观 ↩':'I/O 细节';
 $('#io-detail').title=ioReview?.ports.length?'查看 CAD 孔口与原厂接口':'当前模型未包含接口截面数据';
 $('#io-controls').hidden=!ioMode();
 $('#top-view').hidden=state.view!=='appearance'||ioMode();$('#top-view').textContent=topMode()?'整体':'顶部';$('#top-view').setAttribute('aria-pressed',topMode());
 $('#rear-view').hidden=state.view!=='appearance'||ioMode();$('#rear-view').textContent=rearMode()?'正面':'背面';$('#rear-view').setAttribute('aria-pressed',rearMode());
 $('#bones').hidden=state.view!=='bench';$('#bones').textContent=state.bonesOnly?'完整总成':'仅看骨架';$('#bones').setAttribute('aria-pressed',state.bonesOnly);
 all('[data-port]').forEach(b=>b.setAttribute('aria-pressed',(b.dataset.port||null)===state.port));
 all('[data-view]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.view===state.view));
 all('[data-bay]').forEach(b=>b.setAttribute('aria-pressed',Number(b.dataset.bay)===state.bay));
 $('#selected-info').textContent=state.bay?`盘位 ${String(state.bay).padStart(2,'0')} · 7 mm · SATA 原始基准`:'五盘位 × 7 mm · 保留 SATA 原始坐标';
}
function offsetWorld(node,offset){
 const inverse=new THREE.Matrix3().setFromMatrix4(node.parent.matrixWorld.clone().invert());
 node.position.add(new THREE.Vector3(...offset).applyMatrix3(inverse));
}
function pose(){
 if(!root)return;
 const e=state.explode;
 for(const [kind,node] of semantic){
  const b=base.get(node);
  node.position.copy(b.position);node.scale.copy(b.scale);node.visible=true;
  if(state.view==='exploded'){
   if(kind==='shell')offsetWorld(node,[-.19*e,0,0]);
   else if(coverKinds.includes(kind))offsetWorld(node,[0,.14*e,0]);
   else if(kind==='rear-fan-frame'||kind==='rear-fan')offsetWorld(node,[0,0,-.075*e]);
   else if(['taco','cm5','cooler'].includes(kind))offsetWorld(node,[0,.075*e,0]);
   else if(kind.startsWith('drive-')||kind.startsWith('carrier-'))offsetWorld(node,[0,-.028*e,0]);
  }
  if(state.view==='clearance')node.visible=['taco','spine'].includes(kind);
  if(state.view==='bench'&&['shell',...coverKinds].includes(kind))node.visible=false;
  if(state.view==='bench'&&state.bonesOnly)node.visible=structuralKinds.includes(kind);
 }
 for(const {mesh,kind} of materials){
  mesh.material.transparent=kind==='spine'&&state.view==='clearance';
  mesh.material.opacity=mesh.material.transparent?.32:1;
  mesh.material.depthWrite=!mesh.material.transparent;
  mesh.castShadow=!(kind==='spine'&&state.view==='clearance');
 }
 ringGroup.visible=state.view==='clearance';
 floor.visible=!(state.view==='clearance'&&state.side==='bottom');
 floor.position.y=state.view==='bench'?.0078:state.view==='exploded'?-.028*e-.0004:-.0004;
 applyTheme();
}
function update(changes,{cameraReset=false}={}){
 Object.assign(state,changes);modeUI();pose();if(cameraReset)resetCamera(false);invalidate();
}
function kindOf(node){
 const aliases={'fan':'rear-fan','rear-fan':'rear-fan','cm5-envelope':'cm5','cooler-envelope':'cooler'};
 const n=node.name.replaceAll('_','-');
 return aliases[n]??n;
}
function setupModel(model){
 root=model;
 root.traverse(node=>{
  const kind=kindOf(node);
  if(['shell',...coverKinds,...structuralKinds,'taco','rear-fan','cm5','cooler'].includes(kind)||/^(drive|carrier)-[1-5]$/.test(kind))semantic.set(kind,node);
 });
 if(!semantic.has('shell')||!semantic.has('taco'))throw new Error('CAD 缺少 shell 或 taco 语义节点。');
 scene.add(root);root.updateMatrixWorld(true);
 for(const [kind,node] of semantic){
  base.set(node,{position:node.position.clone(),scale:node.scale.clone()});
  node.traverse(mesh=>{
   if(!mesh.isMesh)return;
   mesh.castShadow=true;mesh.receiveShadow=true;
   mesh.userData.kind=kind;
   mesh.material=mesh.material.clone();
   mesh.material.roughness=kind==='lid-fasteners'?.36:kind==='taco'?.72:kind.startsWith('drive')?.45:.7;
   mesh.material.metalness=kind==='lid-fasteners'?.55:kind.startsWith('drive')?.28:.02;
   if(kind!=='taco')materials.push({mesh,kind});
  });
 }
 ioReview=new IoReview(metadata,root);scene.add(ioReview.group);
 const portButtons=[{id:'',label:'全部'},...ioReview.ports];
 $('#ports').replaceChildren(...portButtons.map(port=>{const button=document.createElement('button');button.dataset.port=port.id;button.textContent=port.label;button.setAttribute('aria-label',port.id?`检视 ${port.label}`:'查看全部接口');button.addEventListener('click',()=>update({port:port.id||null},{cameraReset:true}));return button;}));
 state.ready=true;
 $('#loading').hidden=true;
 modeUI();pose();resetCamera(true);invalidate();
}
function frame(){
 raf=0;
 if(!renderer||!visible||document.hidden)return;
 if(!dragging&&desiredCamera&&desiredTarget){
  if(reduced.matches){camera.position.copy(desiredCamera);controls.target.copy(desiredTarget);}
  else {camera.position.lerp(desiredCamera,.16);controls.target.lerp(desiredTarget,.16);}
  if(camera.position.distanceTo(desiredCamera)<.00002&&controls.target.distanceTo(desiredTarget)<.00002){desiredCamera=null;desiredTarget=null;}
  dirty=true;
 }
 controls.update();
 if(dirty||settle>0){renderer.render(scene,camera);dirty=false;settle--;}
 if(desiredCamera||settle>0)raf=requestAnimationFrame(frame);
}
function fail(error){
 console.error('R3 model view:',error);
 $('#loading').hidden=true;$('#fallback').hidden=false;
 $('#fallback').querySelector('p').textContent='三维模型暂时无法显示。';
 state.error=String(error);
}
async function init(){
 try{
  renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure=.95;
  renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  stage.prepend(renderer.domElement);
  controls=new OrbitControls(camera,renderer.domElement);
  controls.enableDamping=true;controls.dampingFactor=.14;
  controls.minDistance=.17;controls.maxDistance=1.8;controls.enablePan=true;
  controls.addEventListener('start',()=>{dragging=true;desiredCamera=null;desiredTarget=null;invalidate();});
  controls.addEventListener('change',invalidate);
  controls.addEventListener('end',()=>{settle=30;invalidate();});
  scene.add(new THREE.HemisphereLight('#f3f6e8','#91a08c',2.4));
  const key=new THREE.DirectionalLight('#fff8df',3.3);key.position.set(-.25,.65,.45);key.castShadow=true;key.shadow.mapSize.set(2048,2048);key.shadow.camera.left=-.4;key.shadow.camera.right=.4;key.shadow.camera.top=.45;key.shadow.camera.bottom=-.4;key.shadow.camera.near=.05;key.shadow.camera.far=2;key.shadow.bias=-.00015;key.shadow.normalBias=.00025;key.shadow.radius=4;key.target.position.set(.05,.09,-.1);scene.add(key,key.target);
  const fill=new THREE.DirectionalLight('#e8f2ea',1.6);fill.position.set(.45,.3,-.5);scene.add(fill);
  floor=new THREE.Mesh(new THREE.PlaneGeometry(10,10),new THREE.MeshStandardMaterial({color:'#e9ede4',roughness:1,metalness:0}));floor.rotation.x=-Math.PI/2;floor.position.y=-.0004;floor.receiveShadow=true;scene.add(floor);
  ringGroup=new THREE.Group();
  for(const [x,y]of holes){
   const ring=new THREE.Mesh(new THREE.TorusGeometry(.0032,.00025,8,48),new THREE.MeshBasicMaterial({color:'#d5a354',depthTest:false}));ring.rotation.x=Math.PI/2;ring.position.copy(toWorld([x,y,133.5]));ring.renderOrder=5;ringGroup.add(ring);
  }
  scene.add(ringGroup);
  applyTheme();
  new ResizeObserver(resize).observe(stage);
  new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(!visible&&raf){cancelAnimationFrame(raf);raf=0;}else invalidate();},{threshold:.02}).observe(stage);
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&raf){cancelAnimationFrame(raf);raf=0;}else invalidate();});
  const bytes=Uint8Array.from(atob(encodedModel),c=>c.charCodeAt(0));
  const buffer=await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
  const gltf=await new GLTFLoader().parseAsync(buffer,'');
  setupModel(gltf.scene);
 }catch(error){fail(error);}
}

all('[data-view]').forEach(b=>b.addEventListener('click',()=>update({view:b.dataset.view,side:'top',io:false,port:null,topView:false,rearView:false},{cameraReset:true})));
all('[data-bay]').forEach(b=>b.addEventListener('click',()=>{
 const showInside=state.view==='appearance';
 update({bay:state.bay===Number(b.dataset.bay)?0:Number(b.dataset.bay),bonesOnly:false,...(showInside?{view:'bench',io:false}:{})},{cameraReset:showInside||state.bonesOnly});
}));
$('#explode').addEventListener('input',e=>{const value=Number(e.target.value);$('#explode-value').textContent=value+'%';update({explode:value/100},{cameraReset:true});});
$('#theme').addEventListener('click',()=>update({theme:state.theme==='light'?'dark':'light'}));
$('#reset').addEventListener('click',()=>resetCamera(false));
$('#board-side').addEventListener('click',()=>update({side:state.side==='top'?'bottom':'top'},{cameraReset:true}));
$('#io-detail').addEventListener('click',()=>update({io:!state.io,port:null,bay:0,topView:false,rearView:false},{cameraReset:true}));
$('#top-view').addEventListener('click',()=>update({topView:!state.topView,rearView:false},{cameraReset:true}));
$('#rear-view').addEventListener('click',()=>update({rearView:!state.rearView,topView:false},{cameraReset:true}));
$('#bones').addEventListener('click',()=>update({bonesOnly:!state.bonesOnly,bay:0},{cameraReset:true}));
stage.addEventListener('keydown',event=>{
 if(event.target!==stage)return;
 const views=['appearance','exploded','clearance','bench'];
 if(/^[1-4]$/.test(event.key)){update({view:views[Number(event.key)-1],side:'top',io:false,port:null,topView:false,rearView:false},{cameraReset:true});event.preventDefault();}
 else if(event.key==='Home'){resetCamera(false);event.preventDefault();}
 else if(event.key==='Escape'){update({bay:0,port:null},{cameraReset:ioMode()});event.preventDefault();}
 else if(event.key==='ArrowRight'||event.key==='ArrowLeft'){
  if(ioMode()&&ioReview?.ports.length){const ports=ioReview.ports,index=ports.findIndex(p=>p.id===state.port);const next=(index+(event.key==='ArrowRight'?1:ports.length-1)+ports.length)%ports.length;update({port:ports[next].id},{cameraReset:true});}
  else {const showInside=state.view==='appearance';update({bay:((state.bay||1)+(event.key==='ArrowRight'?0:3))%5+1,bonesOnly:false,...(showInside?{view:'bench',io:false}:{})},{cameraReset:showInside||state.bonesOnly});}event.preventDefault();
 }
});
stage.addEventListener('pointerdown',event=>{pointerDown=[event.clientX,event.clientY];});
stage.addEventListener('pointerup',event=>{
 if(!state.ready||!pointerDown||Math.hypot(event.clientX-pointerDown[0],event.clientY-pointerDown[1])>6)return;
 const r=stage.getBoundingClientRect();
 const raycaster=new THREE.Raycaster();raycaster.setFromCamera(new THREE.Vector2((event.clientX-r.left)/r.width*2-1,-(event.clientY-r.top)/r.height*2+1),camera);
 const targets=ioMode()?[root,ioReview.group]:[root];
 const hit=raycaster.intersectObjects(targets,true).find(x=>{if(!x.object.isMesh)return false;let n=x.object;while(n){if(!n.visible)return false;n=n.parent;}return true;});
 if(hit){if(ioMode()&&hit.object.userData.ioPort){update({port:hit.object.userData.ioPort},{cameraReset:true});return;}const kind=hit.object.userData.kind;if(kind?.startsWith('drive-')||kind?.startsWith('carrier-'))update({bay:Number(kind.split('-')[1]),bonesOnly:false});}
});
function partMetrics(name){
 const node=semantic.get(name);if(!node)return null;
 const box=new THREE.Box3().setFromObject(node);
 const members=name==='lid-fasteners'?node.children.map(child=>{const bounds=new THREE.Box3().setFromObject(child);return {name:child.name,bounds:[bounds.min.toArray(),bounds.max.toArray()]};}):undefined;
 return {visible:node.visible,position:node.getWorldPosition(new THREE.Vector3()).toArray(),bounds:[box.min.toArray(),box.max.toArray()],...(members?{members}:{})};
}
function enclosureMetrics(){
 const box=new THREE.Box3();
 for(const kind of ['shell','lid']){const node=semantic.get(kind);if(node)box.union(new THREE.Box3().setFromObject(node));}
 if(box.isEmpty())return null;
 const size=box.getSize(new THREE.Vector3());
 return {bounds:[box.min.toArray(),box.max.toArray()],dimensionsMm:[size.x*1000,size.z*1000,size.y*1000]};
}
window.__r3={state,update,resetCamera:()=>resetCamera(true),metrics:()=>{
 const subject=ioMode()?ioReview?.subject(state.port):state.view==='appearance'?(topMode()?semantic.get('lid'):root):semantic.get('taco');
 const subjects=['bench','exploded'].includes(state.view)||topMode()?[...semantic].filter(([kind,node])=>node.visible&&(!topMode()||coverKinds.includes(kind))).map(([name,object])=>({name,object})):subject?[{name:ioMode()?'io':state.view==='appearance'?'assembly':'taco',object:subject}]:[];
 return {nodes:[...semantic.keys()],sceneChildren:root?.children.length,canvas:renderer?.domElement.getBoundingClientRect().toJSON(),rafActive:!!raf,visible,ready:state.ready,
  cameraPose:controls?{position:camera.position.toArray(),target:controls.target.toArray()}:null,
  subject:state.ready?measureSubjects(camera,subjects,{width:stage.clientWidth,height:stage.clientHeight,margin:5}):null,
  coverParts:state.ready?{lid:partMetrics('lid'),fan:partMetrics('top-fan'),fasteners:partMetrics('lid-fasteners')}:null,
  enclosure:state.ready?enclosureMetrics():null,
  ventilation:state.ready?metadata.ventilation:null,
  spine:state.ready?partMetrics('spine'):null,
  rearFrame:state.ready?partMetrics('rear-fan-frame'):null,
  rearFan:state.ready?partMetrics('rear-fan'):null,
  io:state.ready?{active:ioMode(),selected:state.port,ports:ioReview.probe(camera,stage.clientWidth,stage.clientHeight)}:null,
  visibleParts:[...semantic].filter(([,node])=>node.visible).map(([name])=>name),
  driveBounds:state.ready?[...semantic].filter(([k])=>k.startsWith('drive-')).map(([name,node])=>({name,min:new THREE.Box3().setFromObject(node).min.toArray(),max:new THREE.Box3().setFromObject(node).max.toArray()})):null};
 }};
modeUI();init();
