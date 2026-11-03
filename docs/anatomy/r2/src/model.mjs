import * as k from './kit/iso-kit.mjs';
import * as G from './kit/lathe.mjs';
import * as A from './kit/audit.mjs';
import {BOARD,PORTS} from './reference.mjs';

export const SPEC = Object.freeze({width:144,depth:168,height:210,feet:6,pitch:21.5,
  sata:[29,50.5,72,93.5,115],holes:[32.1,108.7],sideOffset:3,sidePitch:76.6,
  screw:'M3 × 6',washer:.5,engagement:2.25,shim:2.5,boardZ:135,
  heatsinkCeiling:170,topFanBottom:180,frontFan:[120,120,25],topFan:[92,92,25]});
export const W=1040,H=830;
export const P=k.fitProjection([
 ...k.boxCorners({x:0,y:0,w:144,d:168,r:0},-6,210),
 ...k.boxCorners({x:-80,y:0,w:3,d:168,r:0},0,207),
 ...k.boxCorners({x:3,y:-75,w:138,d:3,r:0},0,132),
 ...k.boxCorners({x:3,y:225,w:138,d:3,r:0},0,207),
 ...k.boxCorners({x:0,y:0,w:144,d:168,r:0},283,286)],W,H,
  {pad:36,azimuth:232,elevation:25});
export const MOVES={frame:[0,0,0],front:[0,-75,0],rear:[0,60,0],top:[0,0,76],left:[-80,0,0],io:[0,-75,-36]};
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
function prismPaths(F,outer,holes,s0,s1,id){
 const rings=[oriented(outer),...holes.map(p=>oriented(p,false))];
 const near=G.dot3(F.a,V)>0?s1:s0,far=near===s1?s0:s1;
 const capNormal=mul(F.a,near===s1?1:-1),buckets=[[],[],[],[],[]],edges=[],creases=[],fills=[],reveals=[];
 const cap=rings.map((r,i)=>k.pathOf(oriented(r.map(p=>at(coord(F,near,p))),i===0),true)).join('');
 fills.push(cap);buckets[G.toneOf(capNormal,P)].push(cap);
 rings.forEach((r,ri)=>{
  const tones=ri?[[],[],[],[],[]]:buckets,outline=ri?[]:edges,crease=ri?[]:creases,fill=ri?[]:fills;
  const flags=r.map((p,i)=>{const q=r[(i+1)%r.length];return G.dot3(add(mul(F.u,q[1]-p[1]),mul(F.v,p[0]-q[0])),V)>1e-8});
  r.forEach((p,i)=>{
   const q=r[(i+1)%r.length],a=coord(F,near,p),b=coord(F,near,q),c=coord(F,far,q),e=coord(F,far,p);
   if(flags[i]){
    const normal=G.unit3(add(mul(F.u,q[1]-p[1]),mul(F.v,p[0]-q[0])));
    const face=k.pathOf(oriented([a,b,c,e].map(at)),true);
    fill.push(face);tones[G.toneOf(normal,P)].push(face);
    outline.push(path([c,e],false));crease.push(path([a,b],false));
   }else outline.push(path([a,b],false));
   if(flags[i]!==flags[(i+r.length-1)%r.length])outline.push(path([a,e],false));
  });
  if(ri){
   const opening=path(r.map(p=>coord(F,near,p))),clip=`${id}-${ri}`;
   // Inner walls are visible only through the near opening. Without this clip,
   // their far edges spill onto the panel as arrows and bow-tie screw holes.
   reveals.push({clip,opening,paths:{fill:fill.join(''),outline:outline.join(''),crease:crease.join(''),top:tones[4].join(''),shades:tones.slice(0,4).map(b=>b.join(''))}});
   edges.push(opening);
  }
 });
 return {paths:{fill:fills.join(''),outline:edges.join(''),crease:creases.join(''),top:buckets[4].join(''),shades:buckets.slice(0,4).map(b=>b.join(''))},reveals};
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
  const {paths,reveals}=prismPaths(F,outer,holes,s0,s1,`opening-${mode}-${name.replace(/[^a-z0-9-]/gi,'-')}`);
  const walls=reveals.map(({clip,opening,paths})=>`<clipPath id="${clip}"><path d="${opening}"/></clipPath><g clip-path="url(#${clip})">${k.solidSvg(paths,{tone,lit,crease:'faint'})}</g>`).join('');
  return put(name,coord(F,(s0+s1)/2,[u,v]),k.solidSvg(paths,{tone,lit,crease:'faint',inner:walls+inner})+extra,shape,opts);
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

 // Match the CAD's stepped hatch recess; the cover fits below the upper ledge.
 for(const [z,h,inset]of [[0,3.5,7],[3.5,4.5,15]]){
  box(`stand.base.front.${z}`,3,3,z,138,inset,h,{tone:'lo',owner:'base'});
  box(`stand.base.rear.${z}`,3,165-inset,z,138,inset,h,{tone:'lo',owner:'base'});
  box(`stand.base.left.${z}`,3,3+inset,z,inset,162-2*inset,h,{tone:'lo',owner:'base'});
  box(`stand.base.right.${z}`,141-inset,3+inset,z,inset,162-2*inset,h,{tone:'lo',owner:'base'});
 }
 box('base.air-dam',12,123,8,120,3,14,{tone:'lo',owner:'base'});
 prism('service-hatch',ZF,k.roundedPlan({x:10.3,y:10.3,w:123.4,d:147.4,r:2},6),.2,3.3,
  {holes:[14,130].flatMap(x=>[14,154].map(y=>k.circleRing(x,y,1.7,20))),tone:'lo',piece:'enclosure',owner:'hatch'});
 for(const x of [14,130])for(const y of [14,154]){
  disc(`hatch.screw.${x}.${y}`,G.frameAlong([x,y,.2],[0,0,-1]),0,1.2,2.8,{piece:'enclosure',owner:'hatch'});
  // The threaded shaft is enclosed by the hatch bore and the base ledge.
  // As with the drive screws, draw only its exposed head, not the hidden shank.
 }
 for(const x of [7,137])for(const y of [7,161]){
  disc(`stand.foot.${x}.${y}`,G.frameAlong([x,y,-6],[0,0,1]),0,6,7,{tone:'lo'});
 }
 for(const x of [10,134])for(const y of [46,106.85]){
  disc(`post.${x}.${y}`,G.frameAlong([x,y,8],[0,0,1]),0,10,4.5,{owner:'base',piece:'guides'});
  box(`guide.mount.${x}.${y}`,x-6,y-6,18,12,12,4,{piece:'guides',owner:y===46?'guide.front':'guide.rear'});
  disc(`guide.mount.screw.${x}.${y}`,G.frameAlong([x,y,22],[0,0,1]),0,2.2,2.85,{tone:'hi',piece:'guides'});
 }
 // Both full side panels are retained. Only the left panel leaves in the explode.
 const sideScrews=[[22,4],[146,4],[7,16],[7,120],[161,16],[161,120],[161,184],[37.5,128],[37.5,198],[46,122.4],[132,122.4]];
 for(const left of [true,false]){
  const x=left?0:141,ride=left?'left':'frame',tag=left?'left':'right';
  prism(`side.${tag}`,XF,rect(0,0,168,207),x,x+3,{tone:'mid',ride,piece:'enclosure',owner:`side.${tag}`,
   holes:[...sideScrews.map(([y,z])=>k.circleRing(y,z,1.7,20)),
    ...[149,158,167,176,185,194].flatMap(z=>[54,77,100,123,146].map(y=>capsule(y,z,17,5))),
    ...(left?[rect(75.2,133.2,18,7.2)]:[])]});
  for(const y of [3,157]){
   box(`side.${tag}.lid-mount.${y}`,left?3:133,y,199,8,8,8,{tone:'mid',ride,piece:'enclosure',owner:`side.${tag}`});
  }
 }
 // The I/O panel is recessed 30.5 mm, with the five CAD access windows.
 prism('io.panel',YF,rect(3,124,138,83),30.5,33.5,{tone:'mid',ride:'io',piece:'enclosure',owner:'io-panel',
  holes:[rect(9.85,130.25,17.83,18.9),rect(30.85,130.25,17.83,18.9),rect(50.24,131.002,17.27,20.298),
   rect(69.8,130.2,29.4,13),rect(105.5,130.2,14,17.2)]});

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
  box(`drive${i}.connector`,x-1,55.5,122.7,2,42,1.7,{tone:'lo',piece:'drives',drive:i,owner:`drive${i}`});
  for(let j=0;j<7;j++)box(`drive${i}.contact${j}`,x-1.02,57+j*5.5,123.1,.02,3,1.1,{tone:'hi',piece:'drives',drive:i,owner:`drive${i}`});
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
 // Motherboard saddle with five real slots; native PCB outline and mounting datums.
 // Partition the single printed saddle at its window edges. A whole plate with
 // five holes wraps the underside SATA bodies and cannot have one painter key.
 const saddleOptions={piece:'board',tone:'mid',owner:'saddle'};
 box('saddle.front',6,34,124.4,132,5,3,saddleOptions);
 box('saddle.rear',6,113.8,124.4,132,22.2,3,saddleOptions);
 let ribStart=6;
 for(const [left,right]of [...SPEC.sata.map(x=>[x-4.5,x+8.6]),[138,138]]){
  box(`saddle.rib.${ribStart}`,ribStart,39,124.4,left-ribStart,74.8,3,saddleOptions);
  ribStart=right;
 }
 for(const [x,y]of BOARD.holes){
  disc(`board.standoff.${x}`,G.frameAlong([x,y,127.4],[0,0,1]),0,6,2.25,{piece:'board',tone:'mid'});
  disc(`board.screw.${x}`,G.frameAlong([x,y,135],[0,0,1]),0,1.1,2,{piece:'board',tone:'hi'});
 }
 prism('board.pcb',ZF,BOARD.outline,BOARD.bottom,BOARD.top,{tone:'mid',piece:'board',owner:'board',
  holes:BOARD.holes.map(([x,y])=>k.circleRing(x,y,1.35,24))});
 // The CAD fuses these mounts into the saddle. Keep that exact union, with
 // tangent pieces: the upper inner 9 mm already belongs to a rib / rear plate.
 for(const xx of [3,129])for(const yy of [46,132]){
  box(`saddle.side.${xx}.${yy}`,xx,yy-4,117.4,12,8,7,{piece:'board',owner:'saddle'});
  box(`saddle.side.outer.${xx}.${yy}`,xx===3?3:138,yy-4,124.4,3,8,3,{piece:'board',owner:'saddle'});
 }
 SPEC.sata.forEach((x,i)=>{
  const {y,depth,bottom,width}=BOARD.sata;
  // Five underside receptacles meet the actual drive connector datum.
  prism(`board.sata${i+1}`,ZF,rect(x-width/2,y,width,depth),bottom,BOARD.bottom,{tone:'lo',piece:'board',owner:'board',
   holes:[rect(x-1.25,y+.5,2.5,depth-1)]});
 });
 // Cooler visual proxy is below the reserved 35 mm height; the readout states only the envelope.
 for(const [i,y]of [58.06,92.06].entries()){
  box(`cm5.board-connector${i}`,53.7442,y,135,22.6,3.38,1.45,{tone:'lo',piece:'board',owner:'cm5'});
  box(`cm5.mating-connector${i}`,53.7442,y,136.45,22.6,3.38,2.05,{tone:'lo',piece:'board',owner:'cm5'});
 }
 prism('cm5.pcb',ZF,k.roundedPlan({x:35,y:56.7,w:55,d:40,r:3},6),138.5,139.7,{piece:'board',owner:'cm5'});
 box('cm5.cooler.base',34.55,55.2,139.7,56,43,4,{tone:'hi',piece:'board',owner:'cm5'});
 for(let i=0;i<11;i++)box(`cm5.fin${i}`,35.55,56.2+i*3.8,143.7,54,1.6,12,{tone:'hi',piece:'board',owner:'cm5'});
 // End-mounted M-key socket; the previous full-length connector was misleading.
 box('m2.connector.lower',32.7998,98.175,135,7.1002,21.85,3.5,{tone:'lo',piece:'board',owner:'m2'});
 box('m2.connector.back',32.7998,98.175,138.5,1.9002,21.85,1.2,{tone:'lo',piece:'board',owner:'m2'});
 box('m2.connector.upper',32.7998,98.175,139.7,7.1002,21.85,3.82,{tone:'lo',piece:'board',owner:'m2'});
 prism('m2.pcb',ZF,k.roundedPlan({x:34.7,y:98.3,w:80,d:22,r:1},4),138.5,139.7,{piece:'board',owner:'m2'});
 box('m2.heatspreader',40.2,98.3,139.7,67.5,22,6,{tone:'hi',piece:'board',owner:'m2'});
 disc('m2.mount',G.frameAlong([111.7,109.3,135],[0,0,1]),0,3.5,2.3,{piece:'board',owner:'m2'});
 disc('m2.screw',G.frameAlong([111.7,109.3,139.7],[0,0,1]),0,1.2,2.4,{piece:'board',owner:'m2'});
 // Recognisable major peripherals, located from the vendor STEP.
 disc('rtc.holder',G.frameAlong([20.5,84,135],[0,0,1]),0,4.3,7.1,{piece:'board',tone:'lo',owner:'board'});
 disc('rtc.cell',G.frameAlong([20.5,84,139.3],[0,0,1]),0,.5,5.8,{piece:'board',tone:'hi',owner:'board'});
 box('power.terminal',10.65,62.8,135,5.8,10.2,11.4,{piece:'board',tone:'mid',owner:'board'});
 box('tf.socket',107.5811,68.8501,135,15,16.1,1.9,{piece:'board',tone:'hi',owner:'board'});
 for(const port of PORTS){
  const [x,y,z,x1,y1,z1]=port.bounds,w=x1-x,h=z1-z,cx=(x+x1)/2;
  const options={piece:'board',tone:'hi',owner:'board'};
  let holes;
  if(port.kind==='rj45'){
   holes=[[[x+1.2,z+2],[x+5,z+2],[x+5,z+.9],[x1-5,z+.9],[x1-5,z+2],[x1-1.2,z+2],[x1-1.2,z1-1.4],[x+1.2,z1-1.4]]];
  }else if(port.kind==='usb-a'){
   holes=[rect(x+1.1,133.05,w-2.2,6.05),rect(x+1.1,142.25,w-2.2,6.25)];
  }else if(port.kind==='hdmi'){
   holes=[[[x+1.3,139.9],[x1-1.3,139.9],[x1-1.3,137.7],[x1-3.5,134.3],[x+3.5,134.3],[x+1.3,137.7]]];
  }else if(port.kind==='usb-c'){
   holes=[capsule(cx,137.7,w-1,3.6)];
  }else{
   holes=[k.circleRing(cx,139,3.1,32)];
  }
  // Keep the front lip below the PCB, but stop it at the PCB front edge.
  // Hidden solder pins and embedded housing surfaces are intentionally omitted.
  prism(`io.${port.id}.lip`,YF,rect(x,z,w,h),y,BOARD.front,{...options,holes});
  box(`io.${port.id}.body`,x,BOARD.front,135,w,y1-BOARD.front,z1-135,options);
  for(let i=0;i<holes.length;i++){
   prism(`io.${port.id}.well${i}`,YF,holes[i],BOARD.front-.12,BOARD.front,{...options,tone:'lo'});
  }
  if(port.kind==='dc'){
   disc('io.dc.pin',G.frameAlong([cx,BOARD.front-.12,139],[0,-1,0]),0,BOARD.front-y-.6,.85,options);
  }else if(port.kind==='rj45'){
   box(`io.${port.id}.tongue`,x+2.2,y+.8,134.1,w-4.4,BOARD.front-y-.92,.8,{...options,tone:'lo'});
   for(let j=0;j<8;j++)box(`io.${port.id}.contact${j}`,x+3.1+j*1.25,y+1,134.9,.4,BOARD.front-y-1.12,.15,options);
  }else if(port.kind==='usb-a'){
   for(const zz of [135,144.2])box(`io.${port.id}.tongue${zz}`,x+2.5,y+.7,zz,w-5,BOARD.front-y-.82,1.2,{...options,tone:'lo'});
  }else{
   const zz=port.kind==='hdmi'?137:137.4,ww=port.kind==='hdmi'?w-5:w-2.8;
   box(`io.${port.id}.tongue`,cx-ww/2,y+.7,zz,ww,BOARD.front-y-.82,.6,{...options,tone:'lo'});
  }
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
   const surface=axis==='z'?17.5:isRear?17.5:-17.5;
   const FF={...F,o:coord(F,surface,[dx*off,dy*off]),a:mul(F.a,screwSide)};
   disc(`${name}.bolt.${dx}.${dy}`,FF,0,2.2,2.7,{piece:'fans',tone:'mid',ride,owner:name});
  }
 }
 // Front and rear panel silhouettes plus real fan apertures, kept separate from the rotors.
 for(const rear of [false,true]){
  const ride=rear?'rear':'front',y=rear?165:0;
  const mountHoles=[19.5,124.5].flatMap(x=>[15.5,120.5].map(z=>k.circleRing(x,z,2.25,24)));
  prism(`${ride}.panel`,YF,rect(3,0,138,rear?207:132),y,y+3,{holes:[k.circleRing(72,68,57,64),...mountHoles,
   ...(rear?[149,158,167,176,185,194].flatMap(z=>[25,48,71,94,117].map(x=>capsule(x,z,17,5))):[])],tone:'mid',ride,piece:'enclosure',owner:ride});
  fan(`${ride}.fan`,[72,rear?150.5:17.5,68],120,'y',ride);
 }
 const lidHoles=[7,137].flatMap(x=>[7,161].map(y=>k.circleRing(x,y,1.7,24)));
 lidHoles.push(...[-41.25,41.25].flatMap(x=>[-41.25,41.25].map(y=>k.circleRing(68+x,91+y,2.25,24))));
 prism('lid',ZF,rect(0,0,144,168),207,210,{holes:[k.circleRing(68,91,43,64),...lidHoles],tone:'mid',ride:'top',piece:'enclosure',owner:'top'});
 fan('top.fan',[68,91,192.5],92,'z','top');
 // Independent 2 mm CAD guards with closed, rounded slots and real bolt holes.
 for(const [name,F,size,pitch,aperture,s0]of [
  ['front',{...YF,o:[72,0,68]},120,105,114,3],
  ['rear',{...YF,o:[72,0,68]},120,105,114,163],
  ['top',{...ZF,o:[68,91,0]},92,82.5,86,205]]){
  const radius=aperture/2-1,holes=[];
  for(let v=-Math.floor(radius)+7;v<radius;v+=11){
   const length=2*Math.sqrt(Math.max(0,radius*radius-(Math.abs(v)+4)**2));
   if(length>14)holes.push(capsule(0,v,length,7.8));
  }
  holes.push(...[-pitch/2,pitch/2].flatMap(x=>[-pitch/2,pitch/2].map(y=>k.circleRing(x,y,2.25,24))));
  prism(`${name}.guard`,F,k.roundedPlan({x:-size/2,y:-size/2,w:size,d:size,r:5},6),s0,s0+2,
   {holes,tone:'mid',piece:'fans',ride:name,owner:`${name}.fan`});
 }
 return {R,byName,mode,thicknesses:SPEC.sata.map((_,i)=>mode==='7'?7:mode==='9.5'?9.5:(i%2?7:9.5))};
}

export const stateOf=t=>t;
