import * as k from './kit/iso-kit.mjs';
import * as G from './kit/lathe.mjs';
import * as A from './kit/audit.mjs';

export const SPEC = Object.freeze({width:144,depth:168,height:210,feet:6,pitch:21.5,
  sata:[29,50.5,72,93.5,115],holes:[32.1,108.7],sideOffset:3,sidePitch:76.6,
  screw:'M3 × 6',washer:.5,engagement:2.25,shim:2.5,boardZ:135,
  heatsinkCeiling:170,topFanBottom:180,frontFan:[120,120,25],topFan:[92,92,25]});
export const W=1040,H=830;
export const P=k.fitProjection([
 ...k.boxCorners({x:0,y:0,w:144,d:168,r:0},-6,210),
 ...k.boxCorners({x:3,y:-75,w:138,d:3,r:0},0,132),
 ...k.boxCorners({x:3,y:225,w:138,d:3,r:0},0,207),
 ...k.boxCorners({x:0,y:0,w:144,d:168,r:0},283,286)],W,H,
  {pad:36,azimuth:232,elevation:25});
export const MOVES={frame:[0,0,0],front:[0,-75,0],rear:[0,60,0],top:[0,0,76]};
const add=G.add3,mul=G.mul3,at=p=>k.iso(p,P),V=G.viewOf(P);
const path=(p,closed=true)=>k.pathOf(p.map(at),closed);
const rect=(x,y,w,h)=>[[x,y],[x+w,y],[x+w,y+h],[x,y+h]];
const signed=p=>p.reduce((s,[x,y],i)=>{const q=p[(i+1)%p.length];return s+x*q[1]-y*q[0]},0);
const oriented=(p,positive=true)=>((signed(p)>0)===positive?p:[...p].reverse());
export const XF=G.frameOf([0,0,0],[1,0,0],[0,1,0],[0,0,1]);
export const YF=G.frameOf([0,0,0],[0,1,0],[1,0,0],[0,0,1]);
export const ZF=G.frameOf([0,0,0],[0,0,1],[1,0,0],[0,1,0]);
function coord(F,s,[u,v]){return add(add(add(F.o,mul(F.a,s)),mul(F.u,u)),mul(F.v,v))}
function capsule(cx,cy,w,h){return k.roundedPlan({x:cx-w/2,y:cy-h/2,w,d:h,r:Math.min(w,h)/2},5)}

// Native SVG faces for an arbitrary prism, including through apertures and their reveals.
// The audit records the same outer prism with the same cut prisms.
function prismPaths(F,outer,holes,s0,s1){
 const rings=[oriented(outer),...holes.map(p=>oriented(p,false))];
 const near=G.dot3(F.a,V)>0?s1:s0,far=near===s1?s0:s1;
 const capNormal=mul(F.a,near===s1?1:-1),buckets=[[],[],[],[],[]],edges=[],creases=[],fills=[];
 const cap=rings.map((r,i)=>k.pathOf(oriented(r.map(p=>at(coord(F,near,p))),i===0),true)).join('');
 fills.push(cap);buckets[G.toneOf(capNormal,P)].push(cap);
 rings.forEach((r,ri)=>{
  const flags=r.map((p,i)=>{const q=r[(i+1)%r.length];return G.dot3(add(mul(F.u,q[1]-p[1]),mul(F.v,p[0]-q[0])),V)>1e-8});
  r.forEach((p,i)=>{
   const q=r[(i+1)%r.length],a=coord(F,near,p),b=coord(F,near,q),c=coord(F,far,q),e=coord(F,far,p);
   if(flags[i]){
    const normal=G.unit3(add(mul(F.u,q[1]-p[1]),mul(F.v,p[0]-q[0])));
    const face=k.pathOf(oriented([a,b,c,e].map(at)),true);
    fills.push(face);buckets[G.toneOf(normal,P)].push(face);
    edges.push(path([c,e],false));creases.push(path([a,b],false));
   }else edges.push(path([a,b],false));
   if(flags[i]!==flags[(i+r.length-1)%r.length])edges.push(path([a,e],false));
  });
 });
 return {fill:fills.join(''),outline:edges.join(''),crease:creases.join(''),top:buckets[4].join(''),shades:buckets.slice(0,4).map(b=>b.join(''))};
}

export function makeScene(mode='mixed'){
 const R=A.recorder(P),byName=new Map();
 function put(name,center,svg,shape,{piece='structure',ride='frame',owner=name,drive=0,...rest}={}){
  shape.name=name;shape.owner=owner;
  const it=R.put({name,at:center,svg,piece,ride,move:MOVES[ride]??[0,0,0],drive,shapes:[R.solid(shape)],...rest});
  byName.set(name,it);return it;
 }
 function prism(name,F,outer,s0,s1,{holes=[],tone='mid',lit=false,inner='',extra='',...opts}={}){
  const cut=holes.map(h=>A.prism(F,h,s0-.02,s1+.02));
  const shape=A.prism(F,outer,s0,s1,{cut});
  const u=outer.reduce((s,p)=>s+p[0],0)/outer.length,v=outer.reduce((s,p)=>s+p[1],0)/outer.length;
  return put(name,coord(F,(s0+s1)/2,[u,v]),k.solidSvg(prismPaths(F,outer,holes,s0,s1),{tone,lit,crease:'faint',inner})+extra,shape,opts);
 }
 function box(name,x,y,z,w,d,h,opts={}){
  return prism(name,ZF,rect(x,y,w,d),z,z+h,opts);
 }
 function disc(name,F,s0,s1,r,{hole=0,tone='mid',inner='',...opts}={}){
  const shape=hole?A.ring(F,s0,s1,hole,r):A.disc(F,s0,s1,r);
  const paths=hole?G.lathe([[s0,hole],[s0,r],[s1,r],[s1,hole]],F,P,{steps:32}):G.solidOf([[s0,r],[s1,r]],F,P,{steps:r>10?48:20});
  return put(name,add(F.o,mul(F.a,(s0+s1)/2)),k.solidSvg(paths,{tone,crease:'faint',inner}),shape,opts);
 }
 function faceDetails(x,thickness,i){
  const xx=x-2.7;
  const label=rect(49,37,52,68),F={...XF,o:[xx-.12,0,0]};
  const matrix=planeMatrix([xx-.14,53,47],[0,1,0],[0,0,1]);
  const rules=[0,3,12,15,18].map((v,j)=>k.lineSvg(k.segment([xx-.15,53,47+v],[xx-.15,80+(j>1?12:0),47+v],P),{tone:'lo',free:true})).join('');
  return prism(`drive${i}.label`,F,label,0,.12,{tone:'hi',piece:'drives',drive:i,owner:`drive${i}`,extra:rules});
 }
 function planeMatrix(o,ex,ey){const q=at(o),x=at(add(o,ex)),y=at(add(o,ey));return `matrix(${x[0]-q[0]} ${x[1]-q[1]} ${y[0]-q[0]} ${y[1]-q[1]} ${q[0]} ${q[1]})`}

 // Base is an open structural frame; the omitted bottom hatch is called out in the caption.
 box('stand.base.front',3,3,0,138,15,8,{tone:'lo',piece:'structure',owner:'base'});
 box('stand.base.rear',3,150,0,138,15,8,{tone:'lo',owner:'base'});
 box('stand.base.left',3,18,0,15,132,8,{tone:'lo',owner:'base'});
 box('stand.base.right',126,18,0,15,132,8,{tone:'lo',owner:'base'});
 for(const x of [7,137])for(const y of [7,161]){
  disc(`stand.foot.${x}.${y}`,G.frameAlong([x,y,-6],[0,0,1]),0,6,7,{tone:'lo'});
 }
 for(const x of [10,134])for(const y of [46,106.85]){
  disc(`post.${x}.${y}`,G.frameAlong([x,y,8],[0,0,1]),0,10,4.5,{owner:'base',piece:'guides'});
  box(`guide.mount.${x}.${y}`,x-6,y-6,18,12,12,4,{piece:'guides',owner:y===46?'guide.front':'guide.rear'});
  disc(`guide.mount.screw.${x}.${y}`,G.frameAlong([x,y,22],[0,0,1]),0,2.2,2.85,{tone:'hi',piece:'guides'});
 }
 // A cutaway keeps the rear wall's upper vent section and two real side mounting strips.
 box('side.rear.riser',133,157,8,8,8,199,{tone:'lo',owner:'side'});
 box('side.front.riser',133,3,8,8,8,199,{tone:'lo',owner:'side'});
 box('rear.upper',3,165,132,138,3,75,{tone:'lo',ride:'rear',piece:'fans',holes:[]});
 // The upper wall vents are actual closed apertures, not dashed illustration marks.
 R.items.pop();R.solids.pop();
 prism('rear.upper.vented',YF,rect(3,132,138,75),165,168,{tone:'lo',ride:'rear',piece:'fans',
  holes:[149,158,167,176,185,194].flatMap(z=>[25,48,71,94,117].map(x=>capsule(x,z,17,5)))});

 for(const rear of [false,true]){
  const y=rear?111.75:39.5,side=rear?108.75:41.1,tag=rear?'rear':'front';
  box(`guide.${tag}.low`,6,y,8,132,1.6,4,{piece:'guides',owner:`guide.${tag}`});
  // Partition the printed union at the pad shoulders so no SVG faces interlock.
  const spans=SPEC.sata.map(x=>[x+.3-4.2,x+.3+4.2]);
  let from=6;
  for(const [left,right] of [...spans,[138,138]]){
   if(left>from)box(`guide.${tag}.top.${from}`,from,y,110,left-from,1.6,4,{piece:'guides',owner:`guide.${tag}`});
   from=right;
  }
  for(const x of [6,128]){
   box(`guide.${tag}.end.${x}`,x,y,12,10,1.6,6,{piece:'guides',owner:`guide.${tag}`});
   box(`guide.${tag}.end.shoulder.${x}`,x,rear?112.85:y,18,10,.5,4,{piece:'guides',owner:`guide.${tag}`});
  }
  for(let index=0;index<5;index++){
   const x=SPEC.sata[index],i=index+1,xx=x+.3;
   const xl=x-4.7,xr=xl+13.5,pl=xx-4.2,pr=xx+4.2;
   for(const [suffix,rx,rz,rw,rh]of [['left',xl,12,pl-xl,98],['right',pr,12,xr-pr,98],['bottom',pl,12,8.4,14.1],['middle',pl,38.1,8.4,64.6]]){
    prism(`guide.${tag}.web${i}.${suffix}`,YF,rect(rx,rz,rw,rh),y,y+1.6,
     {piece:'guides',drive:i,owner:`guide.${tag}`});
   }
   for(const flank of [x-4.7,x+7.2])box(`guide.${tag}.flank${i}.${flank}`,flank,side,18,1.6,3,96,{piece:'guides',drive:i,owner:`guide.${tag}`});
   for(const z of SPEC.holes){
    const face=rear?111.6:38.25;
    prism(`guide.${tag}.pad${i}.${z}`,YF,rect(xx-4.2,z-6,8.4,12),face,face+3,
      {holes:[capsule(xx,z,3.4,6.4)],piece:'guides',drive:i,owner:`guide.${tag}`});
   const F=G.frameAlong([xx,rear?114.6:38.25,z],[0,rear?1:-1,0]);
    disc(`screw.${tag}.${i}.${z}.washer`,F,0,.5,3.5,{hole:1.6,piece:'screws',drive:i,tone:'hi',owner:`fastener.${tag}.${i}.${z}`});
    const ring=path(Array.from({length:6},(_,j)=>coord(F,2.2,[1.14*Math.cos(j*Math.PI/3),1.14*Math.sin(j*Math.PI/3)])));
    disc(`screw.${tag}.${i}.${z}.head`,F,.5,2.2,2.85,{piece:'screws',drive:i,tone:'hi',owner:`fastener.${tag}.${i}.${z}`,inner:k.lineSvg(ring,{tone:'lo'})});
   }
  }
 }
 // Five independent drives; the base face stays on -X when changing thickness.
 SPEC.sata.forEach((x,index)=>{
  const i=index+1,thickness=mode==='7'?7:mode==='9.5'?9.5:(i%2===0?7:9.5);
  const body=box(`drive${i}.body`,x-2.7,41.5,22.25,thickness,69.85,100.45,{tone:'hi',piece:'drives',drive:i,owner:`drive${i}`});
  // A printed label is a surface treatment carried by the drive, not an independently sorted object.
  const label=faceDetails(x,thickness,i);
  body.svg+=label.svg;body.shapes.push(...label.shapes);R.items.splice(R.items.indexOf(label),1);byName.delete(label.name);
  box(`drive${i}.connector`,x-1.8,55.5,122.7,2,42,1.7,{tone:'lo',piece:'drives',drive:i,owner:`drive${i}`});
  for(let j=0;j<7;j++)box(`drive${i}.contact${j}`,x-1.82,57+j*5.5,123.1,.02,3,1.1,{tone:'hi',piece:'drives',drive:i,owner:`drive${i}`});
  // Platform touches the standard drive envelope; the 0.25 mm production play is simplified here.
  box(`shoe${i}.platform`,x-6.5,50,18,17.1,29.5,4.25,{piece:'guides',drive:i,owner:`shoe${i}`});
  box(`shoe${i}.cross`,x-6.5,46,18,17.1,4,4,{piece:'guides',drive:i,owner:`shoe${i}`});
  for(const xx of [x-6.5,x+9.15])box(`shoe${i}.arm.${xx}`,xx,34.9,18,1.45,11.1,4,{piece:'guides',drive:i,owner:`shoe${i}`});
  box(`shoe${i}.ear`,x-6.5,30.9,5,17.1,4,23,{piece:'guides',drive:i,owner:`shoe${i}`});
  box(`guide.front.retainer${i}`,x-3.95,34.9,8,12,4.6,12,{piece:'guides',drive:i,owner:'guide.front'});
  if(thickness===7)for(const yy of [41.1,108.75]){
   box(`shim${i}.${yy}`,x+4.7,yy,34,2.5,3,80,{tone:'hi',piece:'shims',drive:i,owner:`shim${i}`});
   box(`shim${i}.${yy}.stop`,x+4.7,yy===108.75?yy-1:yy,114,4.1,4,2,{tone:'hi',piece:'shims',drive:i,owner:`shim${i}`});
  }
 });
 // Motherboard saddle with five real slots; the board is a component-envelope proxy.
 prism('saddle',ZF,rect(6,34,132,102),124.4,127.4,{piece:'board',tone:'mid',holes:SPEC.sata.map(x=>rect(x-4.5,39,13.1,74.8))});
 for(const [x,y]of [[20.1,60.2],[12.9,116.95],[105,60.2],[119.45,116.9]]){
  disc(`board.standoff.${x}`,G.frameAlong([x,y,127.4],[0,0,1]),0,6,2.25,{piece:'board',tone:'mid'});
  disc(`board.screw.${x}`,G.frameAlong([x,y,135],[0,0,1]),0,1.1,2,{piece:'board',tone:'hi'});
 }
 box('board.pcb',9.18,35.68,133.4,113.71,84.87,1.6,{tone:'mid',piece:'board',owner:'board'});
 // The hidden side mounts connect the saddle to the structural side riser.
 for(const yy of [46,132])box(`saddle.side${yy}`,129,yy-4,117.4,12,8,10,{piece:'board',owner:'saddle'});
 // Cooler visual proxy is below the reserved 35 mm height; the readout states only the envelope.
 box('cm5.standoffs',35,56.7,135,55,40,3.5,{tone:'lo',piece:'board',owner:'cm5'});
 box('cm5.pcb',35,56.7,138.5,55,40,1.2,{piece:'board',owner:'cm5'});
 box('cm5.cooler.base',34.55,55.2,139.7,56,43,4,{tone:'hi',piece:'board',owner:'cm5'});
 for(let i=0;i<11;i++)box(`cm5.fin${i}`,35.55,56.2+i*3.8,143.7,54,1.6,12,{tone:'hi',piece:'board',owner:'cm5'});
 box('m2.connector',34.7,98.3,135,80,22,3,{tone:'lo',piece:'board',owner:'m2'});
 box('m2.pcb',34.7,98.3,138,80,22,1.2,{piece:'board',owner:'m2'});
 box('m2.heatspreader',39.7,98.3,139.2,68,22,6,{tone:'hi',piece:'board',owner:'m2'});
 for(const [x,w,h]of [[10.65,16.23,16],[31.65,16.23,16],[51.04,15.67,16],[70.6,14,8],[88,9,6],[106,12,11]]){
  box(`io.port${x}`,x,35.68,135,w,14,h,{piece:'board',tone:'hi',owner:'board'});
  // Dark closed socket recess is an inlay on the connector face.
  prism(`io.socket${x}`,YF,rect(x+1,136,w-2,h-2),35.56,35.68,{piece:'board',tone:'lo',owner:'board'});
 }
 function fan(name,c,size,axis,ride){
  const [cx,cy,cz]=c,F=axis==='y'?{...YF,o:[cx,cy,cz]}:{...ZF,o:[cx,cy,cz]};
  const r=size*.44,s=size/2;
  prism(`${name}.frame`,F,rect(-s,-s,size,size),-12.5,12.5,{holes:[k.circleRing(0,0,r,64)],tone:'lo',piece:'fans',ride,owner:name});
  disc(`${name}.hub`,F,-8,8,size*.145,{tone:'mid',piece:'fans',ride,owner:name});
  for(let j=0;j<4;j++){
   const angle=j*Math.PI/2,cs=Math.cos(angle),sn=Math.sin(angle);
   const inner=size*.12;
   const arm=rect(inner,-1.4,r+1-inner,2.8).map(([u,v])=>[u*cs-v*sn,u*sn+v*cs]);
   prism(`${name}.motor.strut${j}`,F,arm,8,10,{tone:'lo',piece:'fans',ride,owner:name});
  }
  for(let i=0;i<7;i++){
   const a=i*Math.PI*2/7,cs=Math.cos(a),sn=Math.sin(a);
   const blade=[[size*.145,-1],[r*.55,-9],[r*.94,-6],[r*.94,6],[r*.55,11],[size*.145,3]].map(([u,v])=>[u*cs-v*sn,u*sn+v*cs]);
   prism(`${name}.blade${i}`,F,blade,-1,1,{tone:'lo',piece:'fans',ride,owner:name});
  }
  for(const dx of [-1,1])for(const dy of [-1,1]){
   const off=size===92?41.25:52.5;
   const isRear=name.startsWith('rear'),screwSide=axis==='z'||isRear?1:-1;
   const FF={...F,o:coord(F,screwSide*12.5,[dx*off,dy*off]),a:mul(F.a,screwSide)};
   disc(`${name}.bolt.${dx}.${dy}`,FF,0,2.2,2.7,{piece:'fans',tone:'mid',ride,owner:name});
  }
  // Guard strips span the real fan face, carried by the same module.
  for(let j=-3;j<=3;j++){
   const v=j*size/9,half=Math.sqrt(r*r-v*v);
   const guardSide=axis==='z'||name.startsWith('rear')?1:-1;
   prism(`${name}.guard${j}`,F,rect(-half,v-1.4,half*2,2.8),guardSide>0?12.5:-14.5,guardSide>0?14.5:-12.5,
    {tone:'mid',piece:'fans',ride,owner:name});
  }
 }
 // Front and rear panel silhouettes plus real fan apertures, kept separate from the rotors.
 for(const rear of [false,true]){
  const ride=rear?'rear':'front',y=rear?165:0;
  prism(`${ride}.panel`,YF,rect(3,0,138,132),y,y+3,{holes:[k.circleRing(72,68,57,64)],tone:'lo',ride,piece:'fans',owner:ride});
  fan(`${ride}.fan`,[72,rear?150.5:17.5,68],120,'y',ride);
 }
 prism('lid',ZF,rect(0,0,144,168),207,210,{holes:[k.circleRing(68,91,43,64)],tone:'mid',ride:'top',piece:'fans',owner:'top'});
 fan('top.fan',[68,91,192.5],92,'z','top');
 // Physical frame contact: a narrow rear rail supports the saddle at its side lug.
 box('stand.saddle.support',133,128,22,8,8,95.4,{tone:'lo',owner:'side'});
 return {R,byName,mode,thicknesses:SPEC.sata.map((_,i)=>mode==='7'?7:mode==='9.5'?9.5:(i%2?7:9.5))};
}

export const stateOf=t=>t;
