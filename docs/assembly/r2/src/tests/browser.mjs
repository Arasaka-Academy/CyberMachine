import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile,access} from 'node:fs/promises';
import {dirname,resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {chromium} from 'playwright';
import {requiredActions,targetFor,movingBay,poseOf,catalog} from '../lesson.mjs';

const ROOT=resolve(dirname(fileURLToPath(import.meta.url)),'../../../../..');
const shots=resolve(ROOT,'docs/images/r2');
await mkdir(shots,{recursive:true});
const checks=[],errors=[],requests=[];
const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-gpu','--ignore-gpu-blocklist','--allow-file-access-from-files']});
const context=await browser.newContext({viewport:{width:1440,height:980},offline:true,hasTouch:true});
context.on('page',p=>{p.on('pageerror',e=>errors.push(e.message));p.on('console',e=>{if(e.type()==='error')errors.push(e.text());});p.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});});
const page=await context.newPage();
let touch=false;
const state=()=>page.evaluate(()=>window.__assembly.getState());
const chapters=()=>page.getByRole('navigation',{name:'教学章节'}).getByRole('button');
async function chapter(i,p=0){await chapters().nth(i).click();await seek(p);}
async function seek(p){await page.locator('#lesson-progress').fill(String(Math.round(p*1000)));await page.waitForFunction(p=>Math.abs(window.__assembly.getState().progress-p)<.001,p);}
async function check(name,fn){await fn();checks.push(name);console.log('PASS',name);}
async function select(id){const item=page.locator(`[data-part="${id}"]`);await(touch?item.tap():item.click());await page.waitForTimeout(350);}
async function drop(id,target=targetFor(id)){await select(id);const pin=page.locator(`[data-target="${target}"]`);await(touch?pin.tap():pin.click());}
async function installed(id){await page.waitForFunction(id=>window.__assembly.getState().installed.includes(id),id);}
async function snap(name){await page.waitForTimeout(850);await page.screenshot({path:resolve(shots,`assembly-${name}.png`)});}
async function noOverflow(){assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}
try{
 await page.goto(pathToFileURL(resolve(ROOT,'docs/assembly/r2/index.html')).href);
 await page.waitForFunction(()=>window.__assembly?.ready,{timeout:60000});
 assert.equal(await page.evaluate(()=>!!window.__assembly.ready.error),false);
 await check('file URL works with all network access disabled',async()=>{assert.equal(requests.length,0);assert.equal((await page.evaluate(()=>window.__assembly.ready.nodes)),55);});
 await check('five chapters, arbitrary seeks, reverse navigation and replay',async()=>{
  for(let i=0;i<5;i++){
   for(const p of [0,.5,1]){await chapter(i,p);const s=await state();assert.equal(s.chapter,i);assert.equal(s.progress,p);}
   await seek(.5);const pose=await page.evaluate(()=>window.__assembly.pose('cm5'));
   await chapter((i+3)%5,1);await chapter(i,.5);assert.deepEqual(await page.evaluate(()=>window.__assembly.pose('cm5')),pose);
   await page.getByRole('button',{name:'重播本章',exact:true}).click();assert.ok((await state()).progress<.2);
   await page.getByRole('button',{name:'暂停演示',exact:true}).click();const p=(await state()).progress;
   await page.waitForTimeout(150);assert.equal((await state()).progress,p);
  }
  await chapter(4,.32);
  await page.getByRole('button',{name:'播放本章',exact:true}).click();
  await page.waitForTimeout(150);
  await page.getByRole('button',{name:'暂停演示',exact:true}).click();
  const paused=await state();assert.equal(paused.selectedBay,movingBay(paused.progress));
  for(const part of catalog.parts){
   assert.deepEqual(poseOf(part.id,{...paused,playing:true}),poseOf(part.id,paused),`pause keeps ${part.id} pose and emphasis`);
  }
  await seek(.73);
  await page.getByRole('button',{name:'选择 2 号盘位',exact:true}).click();
  await page.getByRole('button',{name:'播放本章',exact:true}).click();
  await page.waitForTimeout(150);
  await page.getByRole('button',{name:'暂停演示',exact:true}).click();
  const fastening=await state();assert.equal(fastening.selectedBay,2);
  for(const part of catalog.parts)assert.deepEqual(poseOf(part.id,{...fastening,playing:true}),poseOf(part.id,fastening));
 });
 await check('actual GLB mating anchors agree within 1 mm',async()=>{
  await chapter(4,1);await page.waitForTimeout(150);
  const a=await page.evaluate(()=>window.__assembly.ready.probe().anchors);
  const gap=(x,y)=>Math.hypot(...a[x].map((n,i)=>n-a[y][i]));
  for(let n=1;n<=5;n++)for(const suffix of ['', '-7'])assert.ok(gap(`anchor-sata-${n}`,`anchor-drive-${n}${suffix}`)<1);
  for(let n=1;n<=2;n++)assert.ok(gap(`anchor-cm5-${n}`,`anchor-cm5-mating-${n}`)<1);
  assert.ok(gap('anchor-wifi-1','anchor-wifi-mating')<1);
  checks.push({anchorGapsMm:[...Array.from({length:5},(_,i)=>gap(`anchor-sata-${i+1}`,`anchor-drive-${i+1}`)),gap('anchor-wifi-1','anchor-wifi-mating')]});
 });
 await check('three themes, three thickness modes, five bays and cutaway',async()=>{
  for(const name of ['深色','蓝图','浅色']){await page.getByRole('button',{name:/切换主题/}).click();assert.equal(await page.getByRole('button',{name:/切换主题/}).innerText(),name);await noOverflow();}
  for(const [label,mode]of [['全 7 mm','7'],['全 9.5 mm','9.5'],['混合厚度','mixed']]){
   await page.getByRole('button',{name:label,exact:true}).click();assert.equal((await state()).thicknessMode,mode);
   for(let n=1;n<=5;n++){await page.getByRole('button',{name:`选择 ${n} 号盘位`,exact:true}).click();assert.equal((await state()).selectedBay,n);}
  }
  await page.getByRole('button',{name:'查看内部',exact:true}).click();assert.equal((await state()).cutaway,true);
  await page.getByRole('button',{name:'显示外壳',exact:true}).click();
 });
 await check('keyboard, free orbit, reset and mesh selection',async()=>{
  await chapter(0,0);await page.getByRole('button',{name:/下一步/}).click();assert.ok((await state()).progress>.16);
  await page.getByRole('button',{name:/上一步/}).click();assert.equal((await state()).progress,0);
  await page.locator('.stage').focus();await page.keyboard.press('2');assert.equal((await state()).chapter,1);
  await page.keyboard.press('End');assert.equal((await state()).progress,1);
  await page.keyboard.press('ArrowLeft');assert.equal((await state()).progress,.96);
  await page.keyboard.press('Home');assert.equal((await state()).progress,0);
  await page.keyboard.press('Space');assert.equal((await state()).playing,true);
  await page.keyboard.press('Escape');assert.equal((await state()).playing,false);
  await chapter(1,1);await page.waitForTimeout(1000);
  const before=await page.evaluate(()=>window.__assembly.ready.probe().camera);
  const box=await page.locator('canvas').boundingBox();
  await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.64,box.y+box.height*.55,{steps:12});await page.mouse.up();
  await page.waitForTimeout(300);assert.notDeepEqual(await page.evaluate(()=>window.__assembly.ready.probe().camera),before);
  await page.getByRole('button',{name:'复位视角',exact:true}).click();await page.waitForTimeout(1000);
  const after=await page.evaluate(()=>window.__assembly.ready.probe().camera);assert.ok(Math.hypot(...before.map((n,i)=>n-after[i]))<.005);
  // Scan the projected board surface using real pointer clicks until a mesh is selected.
  for(const dx of [.5,.4,.6]){await page.mouse.click(box.x+box.width*dx,box.y+box.height*.52);if((await state()).pickedPart)break;}
  assert.ok((await state()).pickedPart);
 });
 await chapter(0,1);await snap('frame');await chapter(1,.42);await snap('cm5');await chapter(2,.65);await snap('wifi');await chapter(3,.97);await snap('taco');await chapter(4,.75);await snap('fasteners');await seek(.81);await snap('fasteners-rear');await seek(1);await snap('finished');
 await check('practice errors preserve progress; desktop drag and drop works',async()=>{
  await page.getByRole('tab',{name:/自己装一次/}).click();
  await drop('close');assert.match(await page.locator('.practice-message').innerText(),/请先安装/);assert.equal((await state()).installed.length,0);
  await drop('wifi','m-key');assert.match(await page.locator('.practice-message').innerText(),/M-Key/);assert.equal((await state()).installed.length,0);
  await drop('antennas');assert.match(await page.locator('.practice-message').innerText(),/网卡/);
  await drop('taco');assert.match(await page.locator('.practice-message').innerText(),/请先安装/);
  await select('frame');await page.waitForTimeout(700);
  const source=await page.locator('[data-part="frame"]').boundingBox(),target=await page.locator('[data-target="frame"]').boundingBox();
  await page.mouse.move(source.x+source.width/2,source.y+source.height/2);await page.mouse.down();
  await page.mouse.move(source.x+source.width/2-15,source.y+source.height/2,{steps:4});
  await page.mouse.move(target.x+target.width/2,target.y+target.height/2,{steps:24});
  await page.mouse.move(target.x+target.width/2+1,target.y+target.height/2,{steps:2});await page.mouse.up();
  await installed('frame');
  for(const id of ['cm5','wifi','antennas','taco']){await drop(id);await installed(id);}
  await drop('drive-2');assert.match(await page.locator('.practice-message').innerText(),/垫片/);assert.equal((await state()).installed.length,5);
  for(const id of requiredActions('mixed').filter(id=>!['close','fix-3'].includes(id))){if(!(await state()).installed.includes(id)){await drop(id);await installed(id);}}
  await drop('close');assert.match(await page.locator('.practice-message').innerText(),/3 号盘/);assert.equal((await state()).installed.includes('close'),false);
  await drop('fix-3');await installed('fix-3');await drop('close');await installed('close');
  await snap('practice');
 });
 await check('complete practice in all thickness modes and safely change thickness',async()=>{
  for(const [label,mode]of [['全 7 mm','7'],['全 9.5 mm','9.5']]){
   await page.getByRole('button',{name:label,exact:true}).click();assert.deepEqual((await state()).installed,['frame','cm5','wifi','antennas','taco']);
   for(const id of requiredActions(mode).slice(5)){await drop(id);await installed(id);}
   assert.equal((await state()).installed.length,requiredActions(mode).length);
  }
 });
 await check('390 px layout and mobile tap installation',async()=>{
  touch=true;
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button',{name:/重新装一次/}).click();await page.getByRole('button',{name:'混合厚度',exact:true}).click();
  for(const id of ['frame','cm5','wifi','antennas','taco','shim-2','drive-2','fix-2']){await drop(id);await installed(id);await noOverflow();}
  await page.locator('.stage').scrollIntoViewIfNeeded();await snap('mobile-practice');
  await chapter(2,.55);await page.locator('.stage').scrollIntoViewIfNeeded();await snap('mobile');await noOverflow();
 });
 await check('offscreen pause resumes without jumping',async()=>{
  await chapter(0,.2);await page.locator('.stage').scrollIntoViewIfNeeded();await page.locator('.stage').focus();await page.keyboard.press('Space');
  await page.waitForTimeout(180);assert.equal((await state()).playing,true);
  await page.evaluate(()=>scrollTo(0,document.body.scrollHeight));await page.waitForFunction(()=>!window.__assembly.inspect().active);
  const paused=(await state()).progress;await page.waitForTimeout(350);assert.equal((await state()).progress,paused);
  await page.locator('.stage').scrollIntoViewIfNeeded();await page.waitForFunction(()=>window.__assembly.inspect().active);await page.waitForTimeout(200);assert.ok((await state()).progress>paused);
  await page.keyboard.press('Escape');
 });
 await check('visibility change pauses and restores the lesson clock',async()=>{
  // Headless tabs do not always become hidden: exercise the browser event contract explicitly.
  await page.locator('.stage').focus();await page.keyboard.press('Space');
  await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});
  await page.waitForTimeout(80);const p=(await state()).progress;await page.waitForTimeout(200);assert.equal((await state()).progress,p);
  await page.evaluate(()=>{delete document.hidden;document.dispatchEvent(new Event('visibilitychange'));});await page.waitForTimeout(180);assert.ok((await state()).progress>p);await page.keyboard.press('Escape');
 });
 await check('reduced motion completes immediately and keeps replay static',async()=>{
  await page.emulateMedia({reducedMotion:'reduce'});await chapter(1,0);await page.getByRole('button',{name:'显示本章完成状态',exact:true}).click();assert.equal((await state()).progress,1);assert.equal((await state()).playing,false);
  await page.getByRole('button',{name:'重播本章',exact:true}).click();assert.equal((await state()).progress,1);assert.equal((await state()).playing,false);
 });
 await page.emulateMedia({reducedMotion:'no-preference'});await page.setViewportSize({width:1440,height:980});await chapter(4,1);await page.locator('.stage').scrollIntoViewIfNeeded();
 await check('all runtime document and media links resolve locally',async()=>{
  const links=await page.locator('a[href]').evaluateAll(nodes=>nodes.map(n=>n.href));
  for(const link of links)if(link.startsWith('file:'))await access(fileURLToPath(link));
 });
 const perf=await page.evaluate(()=>new Promise(resolve=>{const times=[];const step=t=>{times.push(t);if(times.length===61){const canvas=document.querySelector('canvas');const gl=canvas.getContext('webgl2');const info=gl.getExtension('WEBGL_debug_renderer_info');resolve({fps:60000/(times.at(-1)-times[0]),renderer:info?gl.getParameter(info.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER)});}else requestAnimationFrame(step);};requestAnimationFrame(step);}));
 assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);await noOverflow();
 const hash=async file=>createHash('sha256').update(await readFile(resolve(ROOT,file))).digest('hex');
 const report={date:'2026-11-06',browser:browser.version(),checks,errors,networkRequests:requests,performance:perf,viewports:[[1440,980],[390,844]],offline:true,visibilityTest:'visibilitychange event contract; document.hidden overridden because headless background tabs vary',htmlSha256:await hash('docs/assembly/r2/index.html'),modelSha256:await hash('docs/assembly/r2/assets/assembly.glb'),physicalTesting:false};
 await writeFile(resolve(ROOT,'validation/r2/assembly-browser.json'),JSON.stringify(report,null,2)+'\n');
 console.log(`PASS ${checks.filter(check=>typeof check==='string').length} browser checks; ${perf.fps.toFixed(1)} FPS; zero page errors, zero network dependencies.`);
}catch(error){
 await mkdir(resolve(ROOT,'work/assembly-r2'),{recursive:true});await page.screenshot({path:resolve(ROOT,'work/assembly-r2/browser-failure.png'),fullPage:true});
 console.error('State:',await state());throw error;
}finally{await browser.close();}
