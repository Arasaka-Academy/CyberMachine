/**
 * [INPUT]: 已构建的离线 HTML、同批 CAD 元数据与本机浏览器。
 * [OUTPUT]: 154mm外宽、五盘7mm、水平6mm通风横带及锁盖检查记录。
 * [POS]: 审阅数字模型绑定与浏览器行为；不判断实物装配。
 * [PROTOCOL]: Update this header on change, then check AGENTS.md
 */
import assert from 'node:assert/strict';
import {mkdir,writeFile,access,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {resolve,dirname} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {chromium} from 'playwright';
const here=dirname(fileURLToPath(import.meta.url));
const root=resolve(here,'../../../..');
const out=resolve(root,'work/redesign-r3/ui-review');
await mkdir(out,{recursive:true});
const htmlSha256=createHash('sha256').update(await readFile(resolve(here,'../index.html'))).digest('hex');
const buildReport=JSON.parse(await readFile(resolve(root,'work/redesign-r3/ui-build.json'),'utf8'));
const {modelSha256,metadataSha256}=buildReport;
const sourceMetadata=JSON.parse(await readFile(resolve(dirname(buildReport.modelSource),'metadata.json'),'utf8'));
const expectedPortIds=sourceMetadata.ports.map(port=>port.id);
assert.ok(expectedPortIds.length>0,'CAD export must include I/O metadata for this review');
const topFanBoundsMm=sourceMetadata.topFan?.actualCompoundBoundsMm??sourceMetadata.topFan?.boundsMm;
assert.ok(topFanBoundsMm,'CAD export must include the complete top-fan bounds');
const lidFastenerBoundsMm=sourceMetadata.lidClosure?.actualCompoundBoundsMm??sourceMetadata.lidClosure?.boundsMm;
assert.ok(lidFastenerBoundsMm,'CAD export must include the four lid fastener bounds');
const worldBounds=([lo,hi])=>[[lo[0]/1000,lo[2]/1000,-hi[1]/1000],[hi[0]/1000,hi[2]/1000,-lo[1]/1000]];
function closeBounds(actual,expected){for(let side=0;side<2;side++)for(let axis=0;axis<3;axis++)assert.ok(Math.abs(actual[side][axis]-expected[side][axis])<.00003,'GLB bounds differ from CAD metadata');}
const systemChrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
let executablePath=process.env.CHROME_PATH;
if(!executablePath){try{await access(systemChrome);executablePath=systemChrome;}catch{}}
const browser=await chromium.launch({headless:true,...(executablePath?{executablePath}:{}),args:['--enable-gpu','--ignore-gpu-blocklist','--allow-file-access-from-files']});
const errors=[],requests=[],checks=[],measurements=[],interactions=[],ventPhotos=[];
const context=await browser.newContext({viewport:{width:1440,height:1100},offline:true});
const page=await context.newPage();
page.on('pageerror',e=>errors.push(e.message));
page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
const state=()=>page.evaluate(()=>({...window.__r3.state}));
async function snap(name){await page.waitForTimeout(850);const metrics=await page.evaluate(()=>window.__r3.metrics());assert.ok(metrics.subject.every(subject=>!subject.outside),`主体裁切: ${name}`);assert.ok(metrics.subject[0].heightPixels>=40,`主体过小: ${name}`);await page.screenshot({path:resolve(out,name+'.png'),fullPage:true});measurements.push({name,...metrics});}
async function check(name,fn){await fn();checks.push(name);console.log('PASS',name);}
async function view(mode){await page.locator(`[data-view="${mode}"]`).click();await page.waitForTimeout(850);}
async function noOverflow(){assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}
try{
 await page.goto(pathToFileURL(resolve(here,'../index.html')).href);
 await page.waitForFunction(()=>window.__r3?.state.ready||window.__r3?.state.error,{timeout:60000});
 assert.equal((await state()).error,undefined);
 await check('offline file URL loads actual CAD and no network resources',async()=>{
  assert.equal(requests.length,0);assert.equal(await page.evaluate(()=>window.__r3.metrics().nodes.length),20);
  assert.equal(sourceMetadata.printPieceCount,9);
  assert.equal(sourceMetadata.printParts.reduce((sum,part)=>sum+part.quantity,0),9);
  const size=await page.evaluate(()=>window.__r3.metrics().enclosure.dimensionsMm);
  for(let axis=0;axis<3;axis++)assert.ok(Math.abs(size[axis]-[154,144,194][axis])<.03,'enclosure must use the authorized 154 × 144 × 194 mm envelope');
  assert.equal(await page.locator('#view-detail').textContent(),'154 × 144 × 194 mm');
  assert.equal(await page.locator('.count-row:last-of-type b').textContent(),'9');await noOverflow();
 });
 await check('front and rear main slots share a straight horizontal 6 mm band',async()=>{
  const ventilation=await page.evaluate(()=>window.__r3.metrics().ventilation);
  assert.deepEqual(ventilation,sourceMetadata.ventilation,'embedded page ventilation must match the exported CAD metadata');
  for(const name of ['frontLower','rearLower']){
   const zone=ventilation[name];
   assert.equal(zone.middleBandPattern,'horizontal-straight');
   assert.equal(zone.middleBandCenterZMm,70);
   assert.deepEqual(zone.middleBandZMm,[67,73]);
   assert.equal(zone.nominalMinimumCrossWebMm,6);
   const slots=zone.slotsXBottomTopMm;
   assert.equal(slots.length,30,'each main zone must retain 30 round-end slots');
   const columns=[...new Set(slots.map(slot=>slot[0]))].sort((a,b)=>a-b);
   assert.equal(columns.length,15,'each main zone must retain 15 columns');
   for(const x of columns){
    const pair=slots.filter(slot=>slot[0]===x).sort((a,b)=>a[1]-b[1]);
    assert.equal(pair.length,2);
    assert.ok(Math.abs(pair[0][2]-67)<1e-6,'lower slots must end on one horizontal line');
    assert.ok(Math.abs(pair[1][1]-73)<1e-6,'upper slots must start on one horizontal line');
    assert.ok(Math.abs(pair[1][1]-pair[0][2]-6)<1e-6,'all columns must retain the same 6 mm band');
   }
  }
  assert.deepEqual(ventilation.frontLower.slotsXBottomTopMm,ventilation.rearLower.slotsXBottomTopMm,'front and rear slot profiles must match');
  await page.locator('#rear-view').click();await page.waitForTimeout(850);
  assert.ok((await page.locator('#note-copy').textContent()).includes('水平横带'));
  assert.ok((await page.locator('#note-facts').textContent()).includes('水平等宽 6 mm'));
  await page.locator('#rear-view').click();await page.waitForTimeout(850);
 });
 await check('separate rear frame matches CAD and moves with the rear fan',async()=>{
  await view('appearance');
  const assembled=await page.evaluate(()=>({frame:window.__r3.metrics().rearFrame,fan:window.__r3.metrics().rearFan}));
  closeBounds(assembled.frame.bounds,worldBounds(sourceMetadata.parts.find(part=>part.name==='rear-fan-frame').boundsMm));
  assert.equal(assembled.frame.visible,true);assert.equal(assembled.fan.visible,true);
  await view('exploded');
  for(const value of [0,37,100,12]){
   await page.locator('#explode').fill(String(value));
   const moved=await page.evaluate(()=>({frame:window.__r3.metrics().rearFrame,fan:window.__r3.metrics().rearFan}));
   for(const name of ['frame','fan'])for(let axis=0;axis<3;axis++)assert.ok(Math.abs(moved[name].position[axis]-assembled[name].position[axis]-(axis===2?-.075*value/100:0))<1e-6,'rear frame and fan must use the same rearward displacement');
  }
  await view('clearance');assert.equal(await page.evaluate(()=>window.__r3.metrics().rearFrame.visible),false);
  await view('bench');assert.equal(await page.evaluate(()=>window.__r3.metrics().rearFrame.visible),true);
  await view('appearance');
 });
 await snap('desktop-appearance');
 await check('top fan and four closure screws match CAD and follow the lid',async()=>{
  const assembled=await page.evaluate(()=>window.__r3.metrics().coverParts);
  closeBounds(assembled.fan.bounds,worldBounds(topFanBoundsMm));
  closeBounds(assembled.lid.bounds,worldBounds(sourceMetadata.parts.find(part=>part.name==='lid').boundsMm));
  closeBounds(assembled.fasteners.bounds,worldBounds(lidFastenerBoundsMm));
  const closure=sourceMetadata.lidClosure;
  assert.equal(closure.semanticNode,'lid-fasteners');assert.equal(closure.movesWith,'lid');assert.equal(closure.fastenerCount,4);
  const closurePoints=closure.mountingHolesXYmm;
  assert.equal(closurePoints.length,4);
  const xCoordinates=[...new Set(closurePoints.map(point=>point[0]))].sort((a,b)=>a-b),yCoordinates=[...new Set(closurePoints.map(point=>point[1]))].sort((a,b)=>a-b);
  assert.equal(xCoordinates.length,2);assert.equal(yCoordinates.length,2);
  assert.ok(Math.abs(xCoordinates[0]+xCoordinates[1]-2*72)<.03,'closure axes must be symmetric around X72');
  assert.ok(Math.abs(yCoordinates[0]+yCoordinates[1]-2*100)<.03,'closure axes must be symmetric around Y100');
  assert.equal(assembled.fasteners.members.length,4,'CAD must provide four separate closure screw solids');
  const matchedPoints=new Set();
  for(const member of assembled.fasteners.members){
   const center=[(member.bounds[0][0]+member.bounds[1][0])*500,-(member.bounds[0][2]+member.bounds[1][2])*500];
   const index=closurePoints.findIndex(point=>point.every((value,axis)=>Math.abs(center[axis]-value)<.03));
   assert.ok(index>=0&&!matchedPoints.has(index),'each modeled closure screw must match one unique CAD mounting point');matchedPoints.add(index);
  }
  assert.ok(assembled.fasteners.bounds[1][1]<assembled.lid.bounds[1][1],'closure screw heads must stay below the top plane');
  assert.ok(Math.abs(assembled.fasteners.bounds[1][1]*1000-closure.screwHeadTopZmm)<.03,'closure head top must match CAD metadata');
  for(const axis of [0,2])assert.ok(Math.abs((assembled.fan.bounds[0][axis]+assembled.fan.bounds[1][axis])-(assembled.lid.bounds[0][axis]+assembled.lid.bounds[1][axis]))<.00006,'fan center must match the lid center in plan');
  assert.deepEqual(sourceMetadata.topFan.centerMm,[72,100]);
  for(const [axis,margin] of [[0,31],[2,26]])for(const side of [0,1])assert.ok(Math.abs(Math.abs(assembled.fan.bounds[side][axis]-assembled.lid.bounds[side][axis])*1000-margin)<.03,'centered fan must preserve the 31 mm side and 26 mm front/rear margins');
  assert.ok(Math.abs(assembled.lid.bounds[1][1]*1000-sourceMetadata.topFan.grilleTopZ)<.03,'appearance must include the actual lid top plane');
  for(let side=0;side<2;side++)for(let axis=0;axis<3;axis++)assert.ok(side?assembled.fan.bounds[side][axis]<=assembled.lid.bounds[side][axis]+.00003:assembled.fan.bounds[side][axis]>=assembled.lid.bounds[side][axis]-.00003,'lid measurement must include the complete top-fan assembly');
  await view('exploded');
  for(const value of [0,37,100,12]){
   await page.locator('#explode').fill(String(value));
   const moved=await page.evaluate(()=>window.__r3.metrics().coverParts);
   for(const name of ['lid','fan','fasteners'])for(let axis=0;axis<3;axis++)assert.ok(Math.abs(moved[name].position[axis]-assembled[name].position[axis]-(axis===1?.14*value/100:0))<1e-6,'lid, fan and closure screws must use the same world displacement');
  }
  for(const name of ['clearance','bench']){await view(name);const cover=await page.evaluate(()=>window.__r3.metrics().coverParts);assert.equal(cover.fan.visible,false);assert.equal(cover.fasteners.visible,false);}
  await view('appearance');await page.locator('#top-view').click();assert.equal((await state()).topView,true);await snap('desktop-top');
  assert.ok((await page.locator('#note-facts').textContent()).includes('4 颗 M3×25'));
  assert.ok((await page.locator('#note-facts').textContent()).includes('31 / 26 mm'));
  await page.locator('#top-view').click();assert.equal((await state()).topView,false);
 });
 await check('front, top and rear cameras stay exclusive and preserve the CAD assembly',async()=>{
  const original=await page.evaluate(()=>window.__r3.metrics().coverParts);
  await page.locator('#rear-view').click();assert.equal((await state()).rearView,true);assert.equal((await state()).topView,false);await snap('desktop-rear');
  assert.deepEqual(await page.evaluate(()=>window.__r3.metrics().coverParts),original);
  await page.locator('#top-view').click();assert.equal((await state()).topView,true);assert.equal((await state()).rearView,false);
  await page.locator('#rear-view').click();assert.equal((await state()).rearView,true);assert.equal((await state()).topView,false);
  await page.locator('#io-detail').click();assert.equal((await state()).io,true);assert.equal((await state()).rearView,false);assert.equal(await page.locator('#rear-view').isVisible(),false);
  await page.locator('#io-detail').click();assert.equal((await state()).io,false);assert.equal((await state()).rearView,false);
 });
 await check('all CAD I/O profiles bind to native connectors and can be selected',async()=>{
  const ports=await page.evaluate(()=>window.__r3.metrics().io.ports);
  assert.deepEqual(ports.map(port=>port.id),expectedPortIds);assert.ok(ports.every(p=>p.nativeMatched>0&&p.sections>=1),JSON.stringify(ports.map(({id,nativeMatched,sections})=>({id,nativeMatched,sections}))));
  await page.locator('#io-detail').click();assert.equal((await state()).io,true);await snap('desktop-io-all');
  for(const port of ports){
   await page.locator(`[data-port="${port.id}"]`).click();await page.waitForTimeout(700);
   assert.equal((await state()).port,port.id);
   const current=await page.evaluate(()=>window.__r3.metrics());
   assert.ok(current.io.ports.find(p=>p.id===port.id).highlightedNative>0);
   assert.ok(current.io.ports.filter(p=>p.id!==port.id).every(p=>p.highlightedNative===0));
   assert.equal(current.subject[0].outside,false);
  }
  await snap('desktop-io-selected');
  for(const port of ports){
   for(let i=0;i<port.outerProfiles;i++){
    await page.locator('[data-port=""]').click();await page.waitForTimeout(800);
    const target=await page.evaluate(id=>window.__r3.metrics().io.ports.find(port=>port.id===id),port.id);
    const rect=await page.locator('#stage').boundingBox(),pixel=target.pickPixels[i];
    await page.mouse.click(rect.x+pixel[0],rect.y+pixel[1]);
    assert.equal((await state()).port,target.id,'clicking each CAD opening selects its native entity');
   }
  }
  const selected=(await state()).port;
  await page.locator('#stage').focus();await page.keyboard.press('ArrowRight');assert.notEqual((await state()).port,selected);
  await page.keyboard.press('Escape');assert.equal((await state()).port,null);
  await page.locator('#io-detail').click();assert.equal((await state()).io,false);
 });
 await check('four view presets and both board sides',async()=>{
  for(const name of ['exploded','clearance','bench','appearance']){await view(name);assert.equal((await state()).view,name);}
  await view('clearance');await snap('desktop-clearance-top');
  await page.locator('#board-side').click();await page.waitForTimeout(800);assert.equal((await state()).side,'bottom');await snap('desktop-clearance-bottom');
 });
 await check('deterministic explode slider and arbitrary return',async()=>{
  await view('exploded');await page.locator('#explode').fill('73');
  const first=await page.evaluate(()=>window.__r3.metrics().driveBounds);
  await view('bench');await view('exploded');await page.locator('#explode').fill('12');await page.locator('#explode').fill('73');
  assert.deepEqual(await page.evaluate(()=>window.__r3.metrics().driveBounds),first);await snap('desktop-exploded');
 });
 await check('five native 7 mm CAD drives preserve the SATA X datum and bay selections',async()=>{
  assert.equal(sourceMetadata.driveThicknessMm,7);
  assert.equal(sourceMetadata.driveSpecification.count,5);
  assert.equal(sourceMetadata.driveSpecification.thicknessMm,7);
  assert.equal(sourceMetadata.driveSpecification.datum,'negative-X');
  assert.deepEqual(sourceMetadata.driveSpecification.sataXmm,[29,50.5,72,93.5,115]);
  assert.equal(await page.locator('[data-thickness]').count(),0);
  assert.equal(await page.locator('.fixed-spec').textContent(),'5 × 7 mm');
  await view('bench');
  const original=await page.evaluate(()=>window.__r3.metrics().driveBounds);
  assert.equal(original.length,5);
  for(const mode of ['appearance','bench']){
   await view(mode);
   const current=await page.evaluate(()=>window.__r3.metrics().driveBounds);
   for(const drive of current){
    const bay=Number(drive.name.split('-')[1]);
    const datum=sourceMetadata.driveSpecification.sataXmm[bay-1]-2.7;
    const expected=sourceMetadata.driveSpecification.bayEnvelopes.find(entry=>entry.bay===bay);
    assert.ok(expected,`missing CAD bounds for bay ${bay}`);
    closeBounds([drive.min,drive.max],worldBounds(expected.boundsMm));
    assert.ok(Math.abs(drive.min[0]*1000-datum)<.02,'negative-X SATA datum changed');
    assert.ok(Math.abs((drive.max[0]-drive.min[0])*1000-7)<.02,'drive must use a native 7 mm CAD envelope');
   }
  }
  assert.deepEqual(await page.evaluate(()=>window.__r3.metrics().driveBounds),original);
  for(let bay=1;bay<=5;bay++){await page.locator(`[data-bay="${bay}"]`).click();assert.equal((await state()).bay,bay);}
  await snap('desktop-bench');
 });
 await check('skeleton-only view exposes both structural CAD parts and restores the assembly',async()=>{
  await view('bench');await page.locator('#bones').click();assert.equal((await state()).bonesOnly,true);assert.equal((await state()).bay,0);
  assert.deepEqual((await page.evaluate(()=>window.__r3.metrics().visibleParts)).sort(),['rear-fan-frame','spine']);
  closeBounds(await page.evaluate(()=>window.__r3.metrics().spine.bounds),worldBounds(sourceMetadata.parts.find(part=>part.name==='spine').boundsMm));
  closeBounds(await page.evaluate(()=>window.__r3.metrics().rearFrame.bounds),worldBounds(sourceMetadata.parts.find(part=>part.name==='rear-fan-frame').boundsMm));
  assert.deepEqual((await page.evaluate(()=>window.__r3.metrics().subject)).map(subject=>subject.name).sort(),['rear-fan-frame','spine']);
  const frame=sourceMetadata.frameReinforcement;
  assert.ok(frame,'CAD export must include the frame reinforcement specification');
  assert.ok((await page.locator('#note-facts').textContent()).includes(`${frame.longitudinalWebThicknessMm} / ${frame.diagonalWidthMm} mm`));
  assert.ok((await page.locator('#note-facts').textContent()).includes(`${frame.baseHeightMm} / ${frame.rearFanUprightThicknessMm} mm`));
  await snap('desktop-spine');
  const beforeOrbit=await page.evaluate(()=>window.__r3.metrics().cameraPose);
  const rect=await page.locator('#stage').boundingBox();
  await page.mouse.move(rect.x+rect.width*.5-rect.height*.1,rect.y+rect.height*.55);await page.mouse.down();
  await page.mouse.move(rect.x+rect.width*.5+rect.height*.1,rect.y+rect.height*.55,{steps:24});await page.mouse.up();
  await page.waitForTimeout(850);
  const afterOrbit=await page.evaluate(()=>window.__r3.metrics().cameraPose);
  assert.deepEqual(afterOrbit.target,beforeOrbit.target,'orbit must retain the skeleton target');
  const orbitTravel=Math.hypot(...afterOrbit.position.map((value,axis)=>value-beforeOrbit.position[axis]));
  assert.ok(orbitTravel>.01,`dragging the actual canvas must move the camera: ${JSON.stringify({beforeOrbit,afterOrbit})}`);
  interactions.push({name:'skeleton canvas orbit',before:beforeOrbit,after:afterOrbit,cameraTravelMetres:orbitTravel});
  await page.locator('#reset').click();await page.waitForTimeout(850);
  await page.locator('[data-bay="2"]').click();await page.waitForTimeout(850);
  assert.equal((await state()).bonesOnly,false);assert.equal((await state()).bay,2);
  assert.ok((await page.evaluate(()=>window.__r3.metrics().subject)).every(subject=>!subject.outside),'restored assembly must fit the viewport');
  await page.locator('#bones').click();assert.equal((await state()).bonesOnly,true);
  await page.locator('#bones').click();assert.equal((await state()).bonesOnly,false);
  assert.ok((await page.evaluate(()=>window.__r3.metrics().visibleParts)).includes('taco'));
 });
 await check('keyboard scopes to the scene and reset works',async()=>{
  await page.locator('#stage').focus();await page.keyboard.press('3');assert.equal((await state()).view,'clearance');
  await page.keyboard.press('Escape');assert.equal((await state()).bay,0);
  await page.keyboard.press('ArrowRight');assert.equal((await state()).bay,2);
  await page.keyboard.press('ArrowLeft');assert.equal((await state()).bay,1);
  await page.keyboard.press('Home');await page.keyboard.press('1');assert.equal((await state()).view,'appearance');
 });
 await check('dark theme and free orbit render',async()=>{
  await page.locator('#theme').click();assert.equal((await state()).theme,'dark');
  const rect=await page.locator('#stage').boundingBox();
  await page.mouse.move(rect.x+rect.width*.5,rect.y+rect.height*.5);await page.mouse.down();await page.mouse.move(rect.x+rect.width*.65,rect.y+rect.height*.48,{steps:12});await page.mouse.up();
  await page.locator('#reset').click();await snap('desktop-dark');await page.locator('#theme').click();
 });
 await check('390px layout and every view remain usable',async()=>{
  await page.setViewportSize({width:390,height:844});
  await view('appearance');await noOverflow();await snap('mobile-appearance');
  await page.locator('#top-view').click();await noOverflow();await snap('mobile-top');await page.locator('#top-view').click();
  await page.locator('#rear-view').click();await noOverflow();await snap('mobile-rear');await page.locator('#rear-view').click();
  await page.locator('#io-detail').click();await noOverflow();await snap('mobile-io-all');
  const ports=await page.evaluate(()=>window.__r3.metrics().io.ports);
  for(const port of ports){await page.locator(`[data-port="${port.id}"]`).click();await page.waitForTimeout(500);assert.equal((await state()).port,port.id);await noOverflow();}
  await snap('mobile-io-selected');
  for(const name of ['exploded','clearance','bench']){
   await view(name);await noOverflow();await snap('mobile-'+name);
   if(name==='clearance'){await page.locator('#board-side').click();await snap('mobile-clearance-bottom');}
  }
  await view('bench');await page.locator('#bones').click();await snap('mobile-spine');await page.locator('#bones').click();
  await page.locator('[data-bay="3"]').click();assert.equal((await state()).bay,3);
 });
 await check('reduced motion and offscreen render pause',async()=>{
  await page.emulateMedia({reducedMotion:'reduce'});await view('appearance');
  await page.evaluate(()=>window.__r3.resetCamera());await page.waitForTimeout(150);
  await page.evaluate(()=>scrollTo(0,document.documentElement.scrollHeight));await page.waitForTimeout(250);
  assert.equal(await page.evaluate(()=>window.__r3.metrics().visible),false);
  assert.equal(await page.evaluate(()=>window.__r3.metrics().rafActive),false);
  await page.locator('#stage').scrollIntoViewIfNeeded();await page.waitForTimeout(250);assert.equal(await page.evaluate(()=>window.__r3.metrics().visible),true);
 });
 assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
 const fallbackContext=await browser.newContext({viewport:{width:390,height:844},offline:true});
 const fallbackPage=await fallbackContext.newPage();
 await fallbackPage.addInitScript(()=>{HTMLCanvasElement.prototype.getContext=function(){return null;};});
 await fallbackPage.goto(pathToFileURL(resolve(here,'../index.html')).href);
 await fallbackPage.waitForSelector('#fallback:not([hidden])');checks.push('WebGL fallback retains design facts');
 await fallbackContext.close();
 const photoContext=await browser.newContext({viewport:{width:1920,height:1500},deviceScaleFactor:1,offline:true});
 try{
  const photoPage=await photoContext.newPage();
  photoPage.on('pageerror',e=>errors.push(e.message));
  await photoPage.goto(pathToFileURL(resolve(here,'../index.html')).href);
  await photoPage.waitForFunction(()=>window.__r3?.state.ready,{timeout:60000});
  await photoPage.addStyleTag({content:'#stage{height:1040px}'});await photoPage.waitForTimeout(500);
  const photoOut=resolve(root,'work/straight-vents-r3');await mkdir(photoOut,{recursive:true});
  for(const rear of [true,false]){
   await photoPage.locator('#rear-view').click();await photoPage.waitForTimeout(1200);
   assert.equal(await photoPage.evaluate(()=>window.__r3.state.rearView),rear);
   const metrics=await photoPage.evaluate(()=>window.__r3.metrics());
   assert.ok(metrics.subject.every(subject=>!subject.outside),'ventilation photography must retain the complete enclosure');
   const name=rear?'after-rear':'after-front';
   await photoPage.locator('#stage').screenshot({path:resolve(photoOut,name+'.png')});
   ventPhotos.push({name,viewport:{width:1920,height:1500},stageHeight:1040,camera:metrics.cameraPose});
  }
  await writeFile(resolve(photoOut,'after-camera.json'),JSON.stringify({htmlSha256,modelSha256,metadataSha256,photos:ventPhotos},null,2)+'\n');
 }finally{await photoContext.close();}
 assert.deepEqual(errors,[]);
 const report={checkedAt:new Date().toISOString(),browser:await browser.version(),htmlSha256,modelSha256,metadataSha256,checks,errors,runtimeNetworkRequests:requests,measurements,interactions,ventPhotos,boundary:'Browser checks only. CAD interference, physical fits, slicing, thermal and tool access require separate evidence.'};
 await writeFile(resolve(out,'report.json'),JSON.stringify(report,null,2)+'\n');
 console.log('All browser checks passed; screenshots and report:',out);
}finally{await browser.close();}
