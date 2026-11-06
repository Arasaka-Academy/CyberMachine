import React,{Suspense,useEffect,useMemo,useRef,useState} from 'react';
import {Canvas,useFrame,useThree} from '@react-three/fiber';
import {Html,OrbitControls} from '@react-three/drei';
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {measureSubjects} from './frame-guard.mjs';
import modelUrl from '../assets/assembly.glb.gz?inline';
import poster from '../../../images/r2/exploded.png?inline';
import {catalog,poseOf,cameraFor,toWorld,cableState,phaseAt,targetFor,targetAnchor,thickness} from './lesson.mjs';

export const THEMES={
 light:{background:'#eef1eb',floor:'#e3e8e0',grid:'#c8d2c6',accent:'#167a62',shell:'#dce2d9',metal:'#b2bfba',pcb:'#315f50',chip:'#26332e',plastic:'#293b32',fan:'#809288',disk:'#b6c2b9',label:'#f2f3e9',gold:'#b99a63',aluminium:'#bdc8c1'},
 dark:{background:'#17231e',floor:'#1e2d25',grid:'#30473a',accent:'#80d6b1',shell:'#829086',metal:'#bacbc1',pcb:'#295d46',chip:'#15231c',plastic:'#243b2d',fan:'#637b6a',disk:'#99afa0',label:'#b9c8b8',gold:'#b49b6b',aluminium:'#a5b8ac'},
 blueprint:{background:'#142d3b',floor:'#1c3b4a',grid:'#315565',accent:'#8ce3ce',shell:'#8eabb2',metal:'#b7ccd0',pcb:'#3b686b',chip:'#183a46',plastic:'#294f5c',fan:'#698e97',disk:'#9eb8be',label:'#c6dce0',gold:'#bfcdb0',aluminium:'#a4c1c8'},
};
let resource;
function useModel(){
 if(!resource){
  resource={};
  const b64=modelUrl.split(',')[1];
  const bytes=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));
  resource.promise=new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer()
   .then(buffer=>new GLTFLoader().parseAsync(buffer,''))
   .then(gltf=>{resource.value=gltf;},error=>{resource.error=error;});
 }
 if(resource.error)throw resource.error;
 if(!resource.value)throw resource.promise;
 return resource.value;
}
function CameraRig({state,reduced,revision,controls,interacting}){
 const {camera,size}=useThree();
 const desired=useRef(null);
 const phase=phaseAt(state.chapter,state.progress).index;
 const closeup=state.chapter===4&&state.progress>=.78;
 useEffect(()=>{
  const view=cameraFor(state);
  const target=new THREE.Vector3(...toWorld(view.target));
  const position=new THREE.Vector3(...toWorld(view.position)).sub(target).multiplyScalar(Math.max(1,1.25/(size.width/size.height))).add(target);
  desired.current={position,target};
  interacting.current=false;
 },[state.chapter,state.mode,state.selectedPart,state.selectedBay,state.installed.includes('taco'),phase,closeup,revision,size.width,size.height]);
 useFrame((_,delta)=>{
  if(!desired.current||!controls.current||interacting.current)return;
  const k=reduced?1:1-Math.exp(-Math.min(delta,.05)*7);
  camera.position.lerp(desired.current.position,k);
  controls.current.target.lerp(desired.current.target,k);
  controls.current.update();
 });
 return null;
}
function DirectionArrow({from,to,color}){
 const obj=useMemo(()=>{
  const a=new THREE.Vector3(...toWorld(from)),b=new THREE.Vector3(...toWorld(to));
  const delta=b.sub(a),length=delta.length();
  return new THREE.ArrowHelper(delta.normalize(),a,length,color,Math.min(.006,length*.25),.0035);
 },[...from,...to,color]);
 useEffect(()=>()=>{obj.line.geometry.dispose();obj.cone.geometry.dispose();obj.line.material.dispose();obj.cone.material.dispose();},[obj]);
 return <primitive object={obj}/>;
}
function Antennas({state,color}){
 const data=cableState(state);
 const [start1,start2]=catalog.anchors.antenna;
 const cables=useMemo(()=>[start1,start2].map((start,i)=>{
  const points=catalog.antennaRoutes[i].map(toWorld).map(p=>new THREE.Vector3(...p));
  return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points),40,.00065,7,false);
 }),[]);
 const cableRefs=useRef([]),plugRefs=useRef([]);
 useFrame(()=>{
  const pose=cableState(state);
  cableRefs.current.forEach((obj,i)=>{
   if(!obj)return;
   obj.visible=pose.visible;
   obj.position.set(...toWorld(pose.offset));
   // Re-solve only the short terminal section as the plug is pressed down.
   const start=[...catalog.anchors.antenna[i]];start[2]+=pose.lift;
   const curve=new THREE.CatmullRomCurve3([start,...catalog.antennaRoutes[i].slice(1)].map(toWorld).map(p=>new THREE.Vector3(...p)));
   const positions=obj.geometry.attributes.position;
   if(obj.userData.lift!==pose.lift){
    const fresh=new THREE.TubeGeometry(curve,40,.00065,7,false);
    positions.array.set(fresh.attributes.position.array);positions.needsUpdate=true;
    obj.geometry.attributes.normal.array.set(fresh.attributes.normal.array);obj.geometry.attributes.normal.needsUpdate=true;
    fresh.dispose();obj.userData.lift=pose.lift;
   }
   const plug=plugRefs.current[i];
   if(plug){plug.visible=pose.visible;plug.position.set(...toWorld(start.map((n,j)=>n+pose.offset[j])));}
  });
 });
 useEffect(()=>()=>cables.forEach(g=>g.dispose()),[cables]);
 return <group>
  {cables.map((geometry,i)=><React.Fragment key={i}>
   <mesh ref={e=>{cableRefs.current[i]=e;}} geometry={geometry}><meshStandardMaterial color={state.theme==='light'?'#2c3c33':'#a7c0ae'} roughness={.65}/></mesh>
   <mesh ref={e=>{plugRefs.current[i]=e;}}><cylinderGeometry args={[.0012,.0012,.001,16]}/><meshStandardMaterial color={color} metalness={.6} roughness={.35}/></mesh>
  </React.Fragment>)}
 </group>;
}
function WorkSupports({state,palette}){
 const bench=state.mode==='learn'&&(state.chapter===1||state.chapter===2);
 const raised=state.chapter===4||state.mode==='practice';
 const boardBench=state.mode==='practice'&&!state.installed.includes('taco')||state.mode==='learn'&&state.chapter===3;
 return <group>
  {(bench||boardBench)&&[[40,60],[83,60],[40,95],[83,95]].map(([x,y])=><mesh key={`${x}-${y}`} position={toWorld([x+(boardBench?195:0),y,11.7])} castShadow receiveShadow><cylinderGeometry args={[.004,.005,.0234,16]}/><meshStandardMaterial color={palette.fan} roughness={.9}/></mesh>)}
  {raised&&[[7,7],[137,7],[7,161],[137,161]].map(([x,y])=><mesh key={`${x}-${y}`} position={toWorld([x,y,-73])} castShadow receiveShadow><boxGeometry args={[.012,.134,.012]}/><meshStandardMaterial color={palette.fan} metalness={.2} roughness={.6}/></mesh>)}
  {raised&&catalog.spec.sata.flatMap((x,i)=>[46,106].map(y=><mesh key={`tray-${i}-${y}`} position={toWorld([x+1.8,y,-142])} castShadow receiveShadow><boxGeometry args={[.017,.006,.011]}/><meshStandardMaterial color={palette.fan} roughness={.85}/></mesh>))}
 </group>;
}
function Targets({state,onInstall}){
 const id=state.selectedPart;if(state.mode!=='practice'||!id)return null;
 const correct=targetFor(id);
 const targets=[correct,...(id==='wifi'?['m-key']:[])];
 return targets.map(target=>{
  let p=targetAnchor(target);
  if(['cm5-socket','e-key','m-key','antenna'].includes(target)&&!state.installed.includes('taco'))p=p.map((n,i)=>n+[195,0,-110][i]);
  const label={'cm5-socket':'CM5 连接器','e-key':'E-Key 2230','m-key':'M-Key NVMe',antenna:'天线端子','board-mount':'主板安装位',frame:'框架安装位',enclosure:'合拢机箱'}[target]??`${target.split('-')[1]} 号盘位`;
  return <Html key={target} position={toWorld(p)} center zIndexRange={[25,10]}>
   <button className={`target-pin ${target==='m-key'?'neutral':''}`} data-target={target}
    onClick={e=>{e.stopPropagation();onInstall(id,target);}}
    onDragOver={e=>{e.preventDefault();e.dataTransfer.dropEffect='move';}}
    onDragEnter={e=>e.preventDefault()}
    onDrop={e=>{e.preventDefault();e.stopPropagation();const part=e.dataTransfer.getData('application/x-cybermachine-part')||e.dataTransfer.getData('text/plain');onInstall(part,target);}}
    aria-label={`安装到${label}`}><span className="pin-dot"/>{label}<span aria-hidden="true">＋</span></button>
  </Html>;
 });
}
function TeachingMarks({state}){
 if(state.mode!=='learn')return null;
 const {chapter:c,progress:p}=state;
 let marks=[];
 const shifted=(point,id)=>{
  const pose=poseOf(id,state),v=new THREE.Vector3(...toWorld(point)),pivot=new THREE.Vector3(...toWorld(pose.pivot));
  v.sub(pivot).applyAxisAngle(new THREE.Vector3(1,0,0),pose.angle).add(pivot).add(new THREE.Vector3(...toWorld(pose.offset)));
  return v.toArray();
 };
 if(c===1&&p>=.20&&p<.55)marks=catalog.anchors.cm5.map((point,i)=>({point:point.map((v,j)=>j===2?v+2:v),id:'cm5',text:`${i+1} · 连接器上方均匀受力`,side:i?'right':'left'}));
 if(c===1&&p<.20)marks=[{point:[40,60,133.4],id:'taco',text:'绝缘支撑 · 托住载板',side:'left'}];
 if(c===2)marks=[{point:[102,118.5,141],id:'wifi-slot',text:'E-Key · 无线 2230',side:'right'},{point:[36,109,144],id:'taco',text:'M-Key · NVMe',side:'left'}];
 if(c===3&&p>=.78)marks=[0,3,2,1].map((index,i)=>({point:[...catalog.board.holes[index],137],id:'taco',text:`${i+1}`,side:'hole'}));
 if(c===4&&p>=.66&&p<.84){
  const x=catalog.spec.sata[state.selectedBay-1]+.3,y=p<.78?37.8:115;
  marks=[32.1,108.7].map((z,i)=>({point:[x,y,z],id:`disk-screws-${state.selectedBay}`,text:`${p<.78?'前':'后'}侧 ${i+1}/2`,side:'left'}));
 }
 return marks.map((m,i)=><Html key={`${c}-${m.text}-${i}`} position={shifted(m.point,m.id)} center zIndexRange={[8,2]} style={{pointerEvents:'none'}}><div className={`teaching-mark ${m.side}`}><span/>{m.text}</div></Html>);
}
function Assembly({state,onReady,onPick}){
 const gltf=useModel();
 const {gl,camera,size}=useThree();
 const model=useMemo(()=>{
  const scene=gltf.scene.clone(true);
  scene.traverse(node=>{
   if(node.isMesh){node.material=node.material.clone();node.castShadow=true;node.receiveShadow=true;node.userData.originalMaterial=node.material.name;}
  });
  return scene;
 },[gltf]);
 const nodes=useMemo(()=>{
  const result=[];
  for(const node of model.children){
   const id=node.userData.partId??node.name;
   if(id.startsWith('anchor-'))continue;
   const meshes=[];node.traverse(m=>{if(m.isMesh)meshes.push(m);});
   result.push({node,id,meshes});
  }
  return result;
 },[model]);
 useEffect(()=>{
  onReady({nodes:nodes.length,meshes:nodes.reduce((n,p)=>n+p.meshes.length,0),probe:()=>{
   model.updateMatrixWorld(true);
   const anchors={};model.traverse(n=>{if(n.name.startsWith('anchor-'))anchors[n.name]=n.getWorldPosition(new THREE.Vector3()).toArray().map(v=>v*1000);});
   return {anchors,drawCalls:gl.info.render.calls,triangles:gl.info.render.triangles,camera:camera.position.toArray(),visibleParts:nodes.filter(p=>p.node.visible).map(p=>p.id),
    subjects:measureSubjects(camera,nodes.filter(p=>p.node.visible).map(p=>({name:p.id,object:p.node})),{width:size.width,height:size.height,margin:4})};
  }});
  return()=>{model.traverse(n=>{if(n.isMesh)n.material.dispose();});};
 },[model]);
 const vec=useMemo(()=>new THREE.Vector3(),[]);
 useFrame(()=>{
  const palette=THEMES[state.theme];
  for(const {node,id,meshes}of nodes){
   const pose=poseOf(id,state);
   node.visible=pose.visible&&!(state.cutaway&&['left','lid','front-panel','rear-panel','io-panel','front-fan','rear-fan','top-fan'].includes(id));
   if(!node.visible)continue;
   const pivot=new THREE.Vector3(...toWorld(pose.pivot));
   node.quaternion.setFromAxisAngle(new THREE.Vector3(1,0,0),pose.angle);
   vec.copy(pivot).applyQuaternion(node.quaternion);
   node.position.set(...toWorld(pose.offset)).add(pivot).sub(vec);
   for(const mesh of meshes){
    const material=mesh.material;
    const key=`${state.theme}/${pose.active}/${pose.opacity}`;
    if(material.userData.applied===key)continue;
    material.color.set(palette[mesh.userData.originalMaterial]??palette.shell);
    if(pose.active){material.color.lerp(new THREE.Color(palette.accent),.28);material.emissive.set(palette.accent);material.emissiveIntensity=.055;}
    else material.emissiveIntensity=0;
    material.opacity=pose.opacity;
    const transparent=pose.opacity<.99;
    if(material.transparent!==transparent){material.transparent=transparent;material.needsUpdate=true;}
    material.depthWrite=!transparent;
    material.userData.applied=key;
   }
  }
 });
 return <primitive object={model} onClick={e=>{
  if(e.delta>3)return;e.stopPropagation();let node=e.object;
  while(node.parent&&node.parent!==model)node=node.parent;
  onPick(node.userData.partId??node.name);
 }}/>;
}
function Scene({state,reduced,revision,onReady,onPick,onInstall,onInteract}){
 const palette=THEMES[state.theme],controls=useRef(),interacting=useRef(false);
 const {scene}=useThree();
 useEffect(()=>{scene.background=new THREE.Color(palette.background);},[palette]);
 const floorZ=state.mode==='practice'||state.chapter===4?-145:0;
 let arrow;
 if(state.mode==='learn'){
  if(state.chapter===0)arrow=[[72,46,78],[72,46,28]];
  if(state.chapter===1)arrow=[[65,76,74],[65,76,35]];
  if(state.chapter===2)arrow=state.progress<.46?[[102,87,40],[102,110,40]]:[[102,87,52],[102,87,32]];
  if(state.chapter===3)arrow=[[75,75,205],[75,75,155]];
  if(state.chapter===4&&state.progress<.60){const bay=state.selectedBay;arrow=[[catalog.spec.sata[bay-1]-8,75,40],[catalog.spec.sata[bay-1]-8,75,86]];}
 }
 return <>
  <ambientLight intensity={.85}/><hemisphereLight args={['#f0f6ee','#657365',1.15]}/>
  <directionalLight position={[-.35,.65,.4]} intensity={3.4} color="#fff8ed" castShadow shadow-mapSize={[2048,2048]} shadow-bias={-.00002} shadow-normalBias={.0003}
   shadow-camera-left={-.5} shadow-camera-right={.5} shadow-camera-top={.45} shadow-camera-bottom={-.45} shadow-camera-near={.02} shadow-camera-far={1.8}/>
  <directionalLight position={[.35,.2,-.3]} intensity={.8} color="#dbeee5"/>
  <mesh rotation={[-Math.PI/2,0,0]} position={[.07,floorZ/1000,-.08]} receiveShadow onClick={()=>onPick(null)}>
   <planeGeometry args={[2,2]}/><meshStandardMaterial color={palette.floor} roughness={1}/>
  </mesh>
  <gridHelper args={[1.6,64,palette.grid,palette.grid]} position={[.07,floorZ/1000+.00008,-.08]} material-transparent material-opacity={.35}/>
  <WorkSupports state={state} palette={palette}/>
  <Suspense fallback={null}><Assembly state={state} onReady={onReady} onPick={onPick}/></Suspense>
  <Antennas state={state} color={palette.gold}/>
  {arrow&&<DirectionArrow from={arrow[0]} to={arrow[1]} color={palette.accent}/>}
  <Targets state={state} onInstall={onInstall}/>
  <TeachingMarks state={state}/>
  <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={.12} minDistance={.055} maxDistance={1.4}
   minPolarAngle={.12} maxPolarAngle={Math.PI*.51} enablePan onStart={()=>{interacting.current=true;onInteract();}}/>
  <CameraRig state={state} reduced={reduced} revision={revision} controls={controls} interacting={interacting}/>
 </>;
}
export class SceneBoundary extends React.Component{
 constructor(props){super(props);this.state={failed:false};}
 static getDerivedStateFromError(){return {failed:true};}
 componentDidCatch(error){this.props.onError?.(error.message);}
 render(){return this.state.failed?<div className="scene-fallback"><img src={poster} alt="CyberMachine R2 展开结构图"/><p>此浏览器未能启动三维视图。下方仍可逐章阅读安装说明。</p></div>:this.props.children;}
}
export function Viewer({state,reduced,revision,onReady,onPick,onInstall,onInteract,active}){
 const initial=useMemo(()=>cameraFor(state),[]);
 return <SceneBoundary onError={error=>onReady({error})}>
  <Canvas shadows dpr={[1,1.75]} frameloop={active?'always':'never'} camera={{fov:30,near:.001,far:4,position:toWorld(initial.position)}}
   gl={{antialias:true,alpha:false,powerPreference:'high-performance'}}
   onCreated={({gl})=>{gl.toneMapping=THREE.ACESFilmicToneMapping;gl.toneMappingExposure=1.05;}}
   fallback={<div className="scene-fallback"><img src={poster} alt="R2 结构图"/><p>三维视图需要支持 WebGL 的浏览器。</p></div>}>
   <Scene state={state} reduced={reduced} revision={revision} onReady={onReady} onPick={onPick} onInstall={onInstall} onInteract={onInteract}/>
  </Canvas>
 </SceneBoundary>;
}
