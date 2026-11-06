// Deterministic 30 s preview of the real, offline lesson UI. No scene mutations.
import {chromium} from 'playwright';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {findFaults} from './frame-guard.mjs';
import {movingBay,thickness} from './lesson.mjs';

const ROOT=resolve(dirname(fileURLToPath(import.meta.url)),'../../../..');
const WORK=resolve(ROOT,'work/assembly-r2/film');
await mkdir(resolve(WORK,'frames'),{recursive:true});
const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-gpu','--ignore-gpu-blocklist','--allow-file-access-from-files']});
const page=await browser.newPage({viewport:{width:1280,height:800},deviceScaleFactor:1});
const events=[],errors=[],frameLog=[];
page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>{
 let time=0,next=1;const pending=new Map(),epoch=Date.now();
 Object.defineProperty(performance,'now',{value:()=>time});
 Date.now=()=>epoch+time;
 window.requestAnimationFrame=fn=>{const id=next++;pending.set(id,fn);return id;};
 window.cancelAnimationFrame=id=>pending.delete(id);
 window.__filmClock={get now(){return time;},step:ms=>{
  time+=ms;const callbacks=[...pending.values()];pending.clear();for(const fn of callbacks)fn(time);
  for(const animation of document.getAnimations())animation.currentTime=time;
 }};
 document.addEventListener('DOMContentLoaded',()=>{
  const cursor=document.createElement('div');cursor.id='film-cursor';
  Object.assign(cursor.style,{position:'fixed',left:'-40px',top:'-40px',width:'14px',height:'18px',zIndex:9999,pointerEvents:'none',filter:'drop-shadow(0 1px 2px #0006)',clipPath:'polygon(0 0,0 100%,32% 73%,60% 100%,77% 88%,50% 60%,90% 60%)',background:'#fff',border:'1px solid #172c22'});
  document.body.append(cursor);document.addEventListener('pointermove',e=>{cursor.style.left=e.clientX+'px';cursor.style.top=e.clientY+'px';});
 });
});
const step=ms=>page.evaluate(ms=>window.__filmClock.step(ms),ms);
const chapterButtons=()=>page.getByRole('navigation',{name:'教学章节'}).getByRole('button');
let frame=0,orbitOrigin;
async function click(locator,label){
 const b=await locator.boundingBox();if(!b)throw new Error(`Missing ${label}`);
 await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.click(b.x+b.width/2,b.y+b.height/2);
 events.push({frame,kind:'click',target:label});
}
const beats=[{start:0,end:120,chapter:0},{start:120,end:270,chapter:1},{start:270,end:420,chapter:2},{start:420,end:540,chapter:3},{start:540,end:750,chapter:4}];
const orbits=[[242,268],[392,418],[527,538],[736,748],[799,843],[889,899]];
try{
 await page.goto(pathToFileURL(resolve(ROOT,'docs/assembly/r2/index.html')).href);
 // Poll in wall time while RAF callbacks run at a zero-delta virtual clock.
 for(let n=0;!await page.evaluate(()=>!!window.__assembly?.ready);n++){
  if(n>=600)throw new Error('Model loading exceeded 60 seconds');
  await step(0);await page.waitForTimeout(100);
 }
 if(await page.evaluate(()=>window.__assembly.ready.error))throw new Error('WebGL model did not load');
 // Keep the clock still while assets load; pre-roll exactly two simulated seconds.
 for(let n=0;n<60;n++)await step(1000/30);
 const firstClock=await page.evaluate(()=>window.__filmClock.now);
 await click(page.getByRole('button',{name:/播放速度/}),'2× 播放速度');
 await click(page.getByRole('button',{name:/播放速度/}),'4× 播放速度');
 for(frame=0;frame<900;frame++){
  const beat=beats.find(b=>frame>=b.start&&frame<b.end);
  if(beat){
   if(frame===beat.start){await click(chapterButtons().nth(beat.chapter),`第 ${beat.chapter+1} 章`);await click(page.getByRole('button',{name:'播放本章',exact:true}),'播放本章');}
  }else{
   if(frame===750)await click(page.getByRole('tab',{name:/自己装一次/}),'装配练习');
   if(frame===765)await click(page.locator('[data-part="wifi"]'),'选择 E-Key 网卡');
   if(frame===795)await click(page.locator('[data-target="m-key"]'),'尝试错误 M-Key');
   if(frame===845)await click(page.locator('[data-target="e-key"]'),'安装到 E-Key');
   if(frame===860)await click(page.locator('[data-part="antennas"]'),'选择天线');
   if(frame===885)await click(page.locator('[data-target="antenna"]'),'扣合天线');
  }
  const orbit=orbits.find(([a,b])=>frame>=a&&frame<=b);
  if(orbit){
   if(frame===orbit[0]){
    const box=await page.locator('canvas').boundingBox();orbitOrigin=[box.x+box.width*.55,box.y+box.height*.55];
    await page.mouse.move(...orbitOrigin);await page.mouse.down();events.push({frame,kind:'orbit',target:'三维工作台'});
   }else await page.mouse.move(orbitOrigin[0]+(frame-orbit[0])*1.1,orbitOrigin[1]-(frame-orbit[0])*.12);
   if(frame===orbit[1])await page.mouse.up();
  }
  await step(1000/30);
  const sample=await page.evaluate(()=>({state:window.__assembly.getState(),probe:window.__assembly.ready.probe()}));
  const bay=movingBay(sample.state.progress),variant=thickness(sample.state.thicknessMode,bay)===7?'7':'95';
  const focus=sample.state.mode==='practice'?'wifi':sample.state.chapter===0?'base':sample.state.chapter===1?'cm5':sample.state.chapter===2?'wifi':sample.state.chapter===3?'taco':sample.state.progress<.84?`drive-${bay}-${variant}`:'base';
  frameLog.push({time:frame/30,report:sample.probe.subjects.filter(s=>s.name===focus)});
  await page.screenshot({path:resolve(WORK,`frames/${String(frame).padStart(5,'0')}.png`)});
  if(frame%90===0)console.log(`Recorded ${frame}/900 frames (${(frame/30).toFixed(1)} s)`);
 }
 if(errors.length)throw new Error(errors.join('\n'));
 await writeFile(resolve(WORK,'input-events.json'),JSON.stringify(events,null,2)+'\n');
 await writeFile(resolve(WORK,'frame-metrics.json'),JSON.stringify(frameLog)+'\n');
 const allowed=[{name:'cm5',from:4,to:4.9},{name:'wifi',from:9,to:9.8},{name:'drive-1-95',from:18,to:18.7}];
 const framingFaults=beats.flatMap(beat=>findFaults(frameLog.filter(f=>f.time>=beat.start/30&&f.time<beat.end/30),{minHeightPixels:40,graceSeconds:.3,allowed}));
 framingFaults.push(...findFaults(frameLog.filter(f=>f.time>=27.5),{minHeightPixels:40,graceSeconds:.3}));
 const out=resolve(ROOT,'docs/assembly/r2/preview.mp4');
 await new Promise((resolveJob,reject)=>{
  const job=spawn('ffmpeg',['-hide_banner','-loglevel','warning','-y','-framerate','30','-i',resolve(WORK,'frames/%05d.png'),'-vf','scale=960:600:flags=lanczos','-frames:v','900','-c:v','libx264','-preset','fast','-crf','28','-pix_fmt','yuv420p','-movflags','+faststart',out],{stdio:'inherit'});
  job.on('error',reject);job.on('exit',code=>code===0?resolveJob():reject(new Error(`ffmpeg exited ${code}`)));
 });
 const duplicateLog=await new Promise((resolveJob,reject)=>{
  let log='';const job=spawn('ffmpeg',['-hide_banner','-loglevel','info','-i',out,'-vf','mpdecimate,showinfo','-an','-f','null','-']);
  job.stderr.on('data',chunk=>{log+=chunk;});job.on('error',reject);
  job.on('exit',code=>code===0?resolveJob(log):reject(new Error(`Frame check exited ${code}`)));
 });
 await writeFile(resolve(WORK,'duplicate-check.log'),duplicateLog);
 const retained=[...duplicateLog.matchAll(/pts_time:([\d.]+)/g)].map(m=>+m[1]);
 const duplicateCheck={retainedFrames:retained.length,maxRetainedFrameGapSeconds:Math.max(...retained.slice(1).map((t,i)=>t-retained[i]))};
 const hash=buffer=>createHash('sha256').update(buffer).digest('hex');
 const report={date:'2026-11-06',durationSeconds:30,frames:900,fps:30,size:[960,600],audio:'silent UI preview',firstClockMs:firstClock,
  capture:'offline HTML; actual Playwright clicks, 4x playback and small orbits; virtual RAF/performance/Date clock; 2 s pre-roll',events,errors,
  framingFaults,duplicateCheck,htmlSha256:hash(await readFile(resolve(ROOT,'docs/assembly/r2/index.html'))),videoSha256:hash(await readFile(out)),browser:browser.version()};
 await writeFile(resolve(ROOT,'validation/r2/assembly-film.json'),JSON.stringify(report,null,2)+'\n');
 console.log('Recorded and encoded 900 frames / 30 seconds:',out);
 if(framingFaults.length||duplicateCheck.maxRetainedFrameGapSeconds>.2)throw new Error('Preview needs framing or static-hold review; see assembly-film.json');
}finally{await browser.close();}
