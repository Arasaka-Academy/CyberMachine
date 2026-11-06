// Export the exact lesson poses consumed by both the renderer and OCCT audit.
import {writeFileSync,mkdirSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {catalog,PHASES,poseOf} from './lesson.mjs';
import {CatmullRomCurve3,Vector3} from 'three';
const out=resolve(dirname(fileURLToPath(import.meta.url)),'../../../../work/assembly-r2');
mkdirSync(out,{recursive:true});
const ids=[...catalog.parts.map(p=>p.id),'taco'];
const snapshots=[];
for(const thicknessMode of ['mixed','7','9.5'])for(let chapter=0;chapter<5;chapter++){
 const samples=new Set(Array.from({length:101},(_,i)=>i/100));
 for(const phase of PHASES[chapter])samples.add(phase.end);
 for(const progress of [...samples].sort((a,b)=>a-b)){
  const state={mode:'learn',chapter,progress,thicknessMode,selectedBay:1,installed:[],playing:false};
  snapshots.push({chapter,progress,thicknessMode,poses:Object.fromEntries(ids.map(id=>[id,poseOf(id,state)]))});
 }
}
writeFileSync(resolve(out,'poses.json'),JSON.stringify(snapshots));
const cables=[];
for(let lift=0;lift<=9;lift++)for(let id=0;id<2;id++){
 const route=structuredClone(catalog.antennaRoutes[id]);route[0][2]+=lift;
 const curve=new CatmullRomCurve3(route.map(p=>new Vector3(...p)));
 cables.push({id,lift,points:curve.getPoints(200).map(p=>p.toArray())});
}
writeFileSync(resolve(out,'cables.json'),JSON.stringify(cables));
console.log(`Exported ${snapshots.length} lesson states for exact-solid motion checks.`);
