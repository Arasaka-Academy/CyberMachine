import test from 'node:test';
import assert from 'node:assert/strict';
import {thickness,requiredActions,tryInstall,targetFor,poseOf,phaseAt,cameraFor,resetStorage,catalog} from '../lesson.mjs';

const base={mode:'learn',chapter:0,progress:0,playing:false,thicknessMode:'mixed',selectedBay:1,installed:[],selectedPart:null};
function installAll(mode){let installed=[];for(const id of requiredActions(mode)){const result=tryInstall(installed,id,targetFor(id),mode);assert.equal(result.ok,true,`${mode}: ${id}: ${result.reason}`);installed=result.installed;}return installed;}

test('all thickness modes complete with exactly their required shims',()=>{
 for(const mode of ['mixed','7','9.5']){
  const installed=installAll(mode);
  assert.equal(installed.filter(id=>id.startsWith('drive-')).length,5);
  assert.equal(installed.filter(id=>id.startsWith('fix-')).length,5);
  assert.equal(installed.filter(id=>id.startsWith('shim-')).length,mode==='mixed'?2:mode==='7'?5:0);
  assert.ok(installed.includes('close'));
 }
 assert.deepEqual([1,2,3,4,5].map(n=>thickness('mixed',n)),[9.5,7,9.5,7,9.5]);
});
test('wrong slot and missing prerequisites preserve the exercise state',()=>{
 const installed=['frame','cm5'];
 for(const [id,target,fragment]of [['wifi','m-key','M-Key'],['antennas','antenna','网卡'],['taco','board-mount','网卡'],['close','enclosure','网卡']]){
  const result=tryInstall(installed,id,target,'mixed');
  assert.equal(result.ok,false);assert.equal(result.installed,installed);assert.match(result.reason,new RegExp(fragment));
 }
 assert.deepEqual(installed,['frame','cm5']);
});
test('a thin disk requires its own shims, and each bay needs fastening before closure',()=>{
 const mounted=['frame','cm5','wifi','antennas','taco'];
 let result=tryInstall(mounted,'drive-2','bay-2','mixed');
 assert.equal(result.ok,false);assert.match(result.reason,/2 号盘 · 两条垫片/);
 assert.equal(tryInstall([...mounted,'shim-4'],'drive-2','bay-2','mixed').ok,false);
 assert.equal(tryInstall([...mounted,'shim-2'],'drive-2','bay-2','mixed').ok,true);
 const complete=installAll('mixed');
 result=tryInstall(complete.filter(id=>!['fix-3','close'].includes(id)),'close','enclosure','mixed');
 assert.equal(result.ok,false);assert.match(result.reason,/3 号盘/);
});
test('duplicate installation and wrong bays do not count as completion',()=>{
 const installed=installAll('9.5');
 assert.equal(tryInstall(installed,'drive-1','bay-1','9.5').installed,installed);
 assert.equal(tryInstall(installed.filter(id=>id!=='drive-1'),'drive-1','bay-2','9.5').ok,false);
 assert.equal(tryInstall([], 'shim-1','bay-1','9.5').ok,false);
 assert.deepEqual(resetStorage(installAll('mixed')),['frame','cm5','wifi','antennas','taco']);
});
test('arbitrary seeks and reverse navigation produce identical deterministic poses',()=>{
 const names=[...catalog.parts.map(p=>p.id),'taco','antennas'];
 for(let chapter=0;chapter<5;chapter++){
  for(const progress of [0,.18,.5,.78,1,.18]){
   const state={...base,chapter,progress};
   const first=names.map(id=>poseOf(id,state));
   names.forEach(id=>poseOf(id,{...state,progress:1-progress}));
   assert.deepEqual(names.map(id=>poseOf(id,state)),first);
   for(const pose of first){assert.ok(pose.offset.every(Number.isFinite));assert.ok(Number.isFinite(pose.angle));}
   assert.ok(phaseAt(chapter,progress).copy);
   assert.ok(cameraFor(state).position.every(Number.isFinite));
  }
 }
});
test('final mating anchors coincide and no final pose carries residual motion',()=>{
 for(let i=0;i<5;i++)assert.ok(Math.hypot(...catalog.anchors.sata[i].map((n,j)=>n-catalog.anchors.drive[i][j]))<1);
 for(const id of [...catalog.parts.map(p=>p.id),'taco','antennas']){
  const pose=poseOf(id,{...base,chapter:4,progress:1});
  assert.ok(Math.hypot(...pose.offset)<1e-9,id);assert.equal(Math.abs(pose.angle),0);
 }
 const before=poseOf('wifi',{...base,chapter:2,progress:.2});
 assert.ok(before.angle<0);assert.ok(before.offset[1]<0);
 const after=poseOf('wifi',{...base,chapter:2,progress:1});
 assert.equal(Math.abs(after.angle),0);assert.equal(Math.abs(after.offset[1]),0);
});
test('play and pause preserve every pose, opacity and highlight at the same state',()=>{
 for(const chapter of [0,1,2,3,4])for(const progress of [.12,.32,.73,.81,1])for(const selectedBay of [1,3,5]){
  const state={...base,chapter,progress,selectedBay};
  for(const part of catalog.parts)assert.deepEqual(poseOf(part.id,{...state,playing:true}),poseOf(part.id,state),part.id);
 }
});
