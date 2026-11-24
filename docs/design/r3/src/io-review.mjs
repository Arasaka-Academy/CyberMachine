/**
 * [INPUT]: CAD 导出的接口截面、原厂节点名与 three.js 场景。
 * [OUTPUT]: 接口轮廓、高亮、选中命中面与近景取景包络。
 * [POS]: 只消费 CAD 事实；不推断电缆插头或制造配合。
 * [PROTOCOL]: Update this header on change, then check AGENTS.md
 */
import * as THREE from 'three';

const finite=value=>typeof value==='number'&&Number.isFinite(value);
const profile=value=>Array.isArray(value)?value.filter(p=>Array.isArray(p)&&p.every(finite)).map(p=>p.length===3?[p[0],p[2]]:p.slice(0,2)).filter(p=>p.length===2):[];
const profiles=(many,one)=>(Array.isArray(many)?many.map(profile):[profile(one)]).filter(points=>points.length>=3);
const world=([x,y,z])=>new THREE.Vector3(x/1000,z/1000,-y/1000);
const mm=value=>Number(value).toFixed(2).replace(/\.00$/,'');
function bounds(value){
 if(!Array.isArray(value))return null;
 const pair=value.length===6?[value.slice(0,3),value.slice(3,6)]:value;
 return pair.length===2&&pair.every(p=>Array.isArray(p)&&p.length===3&&p.every(finite))?new THREE.Box3().setFromPoints(pair.map(world)):null;
}
function dimensions(points){
 if(!points.length)return '截面数据未附';
 const xs=points.map(p=>p[0]),zs=points.map(p=>p[1]);
 return `${mm(Math.max(...xs)-Math.min(...xs))} × ${mm(Math.max(...zs)-Math.min(...zs))} mm`;
}
export function normalizePorts(metadata){
 return (Array.isArray(metadata?.ports)?metadata.ports:[]).flatMap(port=>{
  if(!/^[\w-]+$/.test(port.id??''))return [];
  const outers=profiles(port.outerProfilesMm,port.outerProfileMm??port.apertureProfileMm);
  const inners=profiles(port.innerProfilesMm,port.innerProfileMm);
  const frontY=[port.outerY,port.outerPlaneY,port.frontY].find(finite);
  if(!outers.length||!finite(frontY))return [];
  return [{...port,label:String(port.label??port.id),outers,inners,frontY,
   innerY:[port.innerY,port.innerPlaneY].find(finite)??frontY,
   nativeNames:Array.isArray(port.nativeNames)?port.nativeNames.filter(n=>typeof n==='string'):[]}];
 });
}
export class IoReview{
 constructor(metadata,model){
  this.ports=normalizePorts(metadata);this.group=new THREE.Group();this.group.name='io-review';this.entries=new Map();
  const nativeNodes=new Map();
  model.traverse(node=>{const leaf=(node.userData.name??node.name).split('/').at(-1);if(!nativeNodes.has(leaf))nativeNodes.set(leaf,node);});
  for(const port of this.ports){
   const group=new THREE.Group(),lines=[],box=new THREE.Box3(),picks=[];
   const sections=[...port.outers.map(points=>({points,y:port.frontY})),...port.inners.map(points=>({points,y:port.innerY}))];
   for(const section of sections){
    const points=section.points.map(([x,z])=>world([x,section.y-.025,z]));points.forEach(p=>box.expandByPoint(p));
    const line=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:'#247d61',transparent:true,opacity:.45,depthWrite:false}));group.add(line);lines.push(line);
   }
   const body=bounds(port.bodyBoundsMm);if(body)box.union(body);
   for(const outline of port.outers){
    const contour=outline.map(([x,z])=>new THREE.Vector2(x/1000,z/1000));
    const hit=new THREE.Mesh(new THREE.ShapeGeometry(new THREE.Shape(contour)),new THREE.MeshBasicMaterial({side:THREE.DoubleSide,colorWrite:false,depthWrite:false}));
    hit.position.z=-(port.frontY-.04)/1000;hit.userData.ioPort=port.id;group.add(hit);
    const triangles=THREE.ShapeUtils.triangulateShape(contour,[]);
    const area=triangle=>new THREE.Triangle(...triangle.map(i=>new THREE.Vector3(contour[i].x,contour[i].y,0))).getArea();
    const triangle=triangles.sort((a,b)=>area(b)-area(a))[0];
    const pick=triangle?triangle.reduce((p,i)=>p.add(contour[i]),new THREE.Vector2()).divideScalar(3):contour[0];
    picks.push(new THREE.Vector3(pick.x,pick.y,hit.position.z));
   }
   const native=[];
   for(const name of port.nativeNames){
    const node=model.getObjectByName(name)??nativeNodes.get(name);
    node?.traverse(mesh=>{if(mesh.isMesh){mesh.userData.ioPort=port.id;native.push({mesh,color:mesh.material.color.clone(),emissive:mesh.material.emissive?.clone()});}});
   }
   const measure=new THREE.Mesh(new THREE.BoxGeometry(...box.getSize(new THREE.Vector3()).toArray()),new THREE.MeshBasicMaterial({visible:false}));measure.position.copy(box.getCenter(new THREE.Vector3()));measure.updateMatrixWorld(true);
   this.entries.set(port.id,{port,group,lines,box,native,measure,picks});this.group.add(group);
  }
  const all=this.box(null);
  if(!all.isEmpty()){
   this.allMeasure=new THREE.Mesh(new THREE.BoxGeometry(...all.getSize(new THREE.Vector3()).toArray()),new THREE.MeshBasicMaterial({visible:false}));
   this.allMeasure.position.copy(all.getCenter(new THREE.Vector3()));this.allMeasure.updateMatrixWorld(true);
  }
  this.group.visible=false;
 }
 sync(active,selected,dark){
  this.group.visible=active;
  const accent=new THREE.Color(dark?'#9cc8a7':'#247d61');
  for(const [id,e]of this.entries){
   const focus=active&&id===selected;
   for(const line of e.lines){line.material.color.copy(accent);line.material.opacity=selected?(focus?1:.2):.7;}
   for(const n of e.native){n.mesh.material.color.copy(n.color);if(n.emissive)n.mesh.material.emissive.copy(n.emissive);if(focus){n.mesh.material.color.lerp(accent,.25);n.mesh.material.emissive?.copy(accent).multiplyScalar(.25);}}
  }
 }
 box(selected){
  const box=new THREE.Box3();
  for(const [id,e]of this.entries)if(!selected||selected===id)box.union(e.box);
  return box;
 }
 subject(selected){
  if(selected&&this.entries.has(selected))return this.entries.get(selected).measure;
  return this.allMeasure??null;
 }
 camera(selected){
  const box=this.box(selected);if(box.isEmpty())return null;
  const center=box.getCenter(new THREE.Vector3());center.z=box.max.z;
  return {target:center.toArray(),offset:selected?[.006,.008,.070]:[.015,.017,.150],fov:26,box};
 }
 facts(selected){
  const p=this.entries.get(selected)?.port;
  if(!p)return [['I/O 开口',`${this.ports.length} 组 CAD 轮廓`],['轮廓来源','本次 CAD 截面'],['验证边界','插接与按压待实测']];
  const body=bounds(p.bodyBoundsMm);
  const recess=body?(-body.max.z*1000-p.frontY):null;
  return [['外孔尺寸',p.outers.map(dimensions).join(' / ')],['内孔尺寸',p.inners.length?p.inners.map(dimensions).join(' / '):'单截面开孔'],['前缘包络退距',finite(recess)?`${mm(recess)} mm`:'数字数据未附']];
 }
 probe(camera,width,height){
  return this.ports.map(p=>{const e=this.entries.get(p.id),pickPixels=e.picks.map(pick=>{const point=pick.clone().project(camera);return [(point.x*.5+.5)*width,(-point.y*.5+.5)*height];});return {id:p.id,label:p.label,nativeMatched:e.native.length,highlightedNative:e.native.filter(n=>!n.mesh.material.color.equals(n.color)).length,nativeNames:p.nativeNames,sections:e.lines.length,outerProfiles:p.outers.length,box:[e.box.min.toArray(),e.box.max.toArray()],pickPixel:pickPixels[0],pickPixels};});
 }
}
