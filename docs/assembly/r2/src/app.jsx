import React,{useCallback,useEffect,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Viewer} from './scene.jsx';
import {CHAPTERS,PHASES,catalog,clamp,phaseAt,thickness,requiredActions,actionLabel,targetFor,tryInstall,resetStorage,poseOf,cameraFor,movingBay} from './lesson.mjs';
import './style.css';

const themeNames={light:'浅色',dark:'深色',blueprint:'蓝图'};
function initialTheme(){try{const t=localStorage.getItem('cybermachine-lesson-theme');return themeNames[t]?t:'light';}catch{return 'light';}}
function BrandMark(){return <svg width="29" height="34" viewBox="0 0 29 34" aria-hidden="true"><rect x=".7" y=".7" width="27.6" height="32.6" rx="3" fill="none" stroke="currentColor" strokeWidth="1.4"/>{[7,12,17,22,27].map(y=><path key={y} d={`M7 ${y}h15`} fill="none" stroke="currentColor" strokeWidth="1.4"/> )}</svg>;}
function App(){
 const [state,setState]=useState({mode:'learn',chapter:0,progress:0,playing:false,playbackRate:1,thicknessMode:'mixed',selectedBay:1,theme:initialTheme(),cutaway:false,selectedPart:null,installed:[],pickedPart:null});
 const [revision,setRevision]=useState(0),[ready,setReady]=useState(null),[message,setMessage]=useState({kind:'info',text:'选择一个零件，再点选三维视图中的安装位置；也可以把零件拖到标记上。'});
 const [reduced,setReduced]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches);
 const [inView,setInView]=useState(true),[visible,setVisible]=useState(!document.hidden);
 const stage=useRef(),current=useRef(state),motion=useRef({reduced,inView,visible});
 current.current=state;motion.current={reduced,inView,visible};
 const chapter=CHAPTERS[state.chapter],phase=phaseAt(state.chapter,state.progress);
 const active=inView&&visible;
 const onReady=useCallback(info=>setReady(info),[]);
 useEffect(()=>{document.documentElement.dataset.theme=state.theme;try{localStorage.setItem('cybermachine-lesson-theme',state.theme);}catch{}},[state.theme]);
 useEffect(()=>{
  const media=window.matchMedia('(prefers-reduced-motion: reduce)');
  const update=()=>setReduced(media.matches);media.addEventListener('change',update);
  const visibility=()=>setVisible(!document.hidden);document.addEventListener('visibilitychange',visibility);
  const observer=new IntersectionObserver(([entry])=>setInView(entry.isIntersecting),{threshold:.05});
  observer.observe(stage.current);
  return()=>{media.removeEventListener('change',update);document.removeEventListener('visibilitychange',visibility);observer.disconnect();};
 },[]);
 useEffect(()=>{
  let raf,last;
  const frame=now=>{
   const delta=last===undefined?0:Math.min((now-last)/1000,.1);last=now;
   const s=current.current,m=motion.current;
   if(s.playing&&s.mode==='learn'&&!m.reduced&&m.inView&&m.visible){
    setState(prev=>{const progress=clamp(prev.progress+delta*prev.playbackRate/CHAPTERS[prev.chapter].duration);return {...prev,progress,playing:progress<1,selectedBay:prev.chapter===4&&progress<.60?movingBay(progress):prev.selectedBay};});
   }
   raf=requestAnimationFrame(frame);
  };
  raf=requestAnimationFrame(frame);return()=>cancelAnimationFrame(raf);
 },[]);
 const goChapter=useCallback(index=>{setState(s=>({...s,mode:'learn',chapter:clamp(index,0,4),progress:0,playing:false,cutaway:false,pickedPart:null}));setRevision(r=>r+1);},[]);
 const togglePlay=useCallback(()=>setState(s=>reduced?{...s,progress:1,playing:false}:{...s,progress:s.progress===1?0:s.progress,playing:!s.playing}),[reduced]);
 const goPractice=()=>{setState(s=>({...s,mode:'practice',playing:false,selectedPart:'frame',cutaway:false,pickedPart:null}));setRevision(r=>r+1);};
 function stepLesson(direction){
  const s=current.current,phase=phaseAt(s.chapter,s.progress),phases=PHASES[s.chapter];
  if(direction>0&&phase.index===phases.length-1&&s.progress===1){if(s.chapter===4)goPractice();else goChapter(s.chapter+1);return;}
  if(direction<0&&phase.index===0&&s.progress<.002){if(s.chapter>0){goChapter(s.chapter-1);setState(prev=>({...prev,progress:1}));}return;}
  const progress=direction>0?(phase.index===phases.length-1?1:phase.end+.001):
   s.progress>phase.start+.002?phase.start:phase.index>1?phases[phase.index-2].end+.001:0;
  setState(prev=>({...prev,progress,playing:false,cutaway:false,pickedPart:null}));
 }
 useEffect(()=>{
  const keydown=e=>{
   if(e.altKey||e.metaKey||e.ctrlKey||e.target.closest('input,button,select,textarea,a,summary'))return;
   if(e.key==='Escape'){setState(s=>({...s,playing:false,pickedPart:null,selectedPart:null}));return;}
   if(current.current.mode!=='learn')return;
   if(e.code==='Space'){e.preventDefault();togglePlay();}
   if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();setState(s=>({...s,progress:clamp(s.progress+(e.key==='ArrowRight'?.04:-.04)),playing:false}));}
   if(e.key==='Home'||e.key==='End'){e.preventDefault();setState(s=>({...s,progress:e.key==='Home'?0:1,playing:false}));}
   if(/^[1-5]$/.test(e.key)){e.preventDefault();goChapter(+e.key-1);}
  };
  window.addEventListener('keydown',keydown);return()=>window.removeEventListener('keydown',keydown);
 },[togglePlay,goChapter]);
 useEffect(()=>{
  window.__assembly={getState:()=>({...current.current}),ready,
   inspect:()=>({state:current.current,phase:phaseAt(current.current.chapter,current.current.progress),camera:cameraFor(current.current),active:motion.current.inView&&motion.current.visible,reducedMotion:motion.current.reduced}),
   pose:id=>poseOf(id,current.current),anchors:catalog.anchors};
 },[ready,state]);
 function install(id,target){
  if(!id)return;
  const s=current.current,result=tryInstall(s.installed,id,target,s.thicknessMode);
  setMessage({kind:result.ok?'success':'error',text:result.reason});
  if(result.ok)setState(prev=>({...prev,installed:result.installed,pickedPart:null}));
 }
 function selectPart(id){setState(s=>({...s,selectedPart:id,pickedPart:null}));setMessage({kind:'info',text:`${actionLabel(id)}：点选对应的安装位置，或将零件拖放到标记上。`});}
 function changeThickness(mode){
  setState(s=>({...s,thicknessMode:mode,installed:resetStorage(s.installed),selectedPart:s.mode==='practice'?'drive-1':s.selectedPart,pickedPart:null}));
  setMessage({kind:'info',text:'厚度已切换。保留主板预装，重新检查各盘位的垫片、硬盘与固定件。'});
 }
 const actions=requiredActions(state.thicknessMode),complete=actions.filter(id=>state.installed.includes(id)).length;
 const pickedLabel=state.pickedPart==='taco'?'TACO V1.61 原厂模型':catalog.parts.find(p=>p.id===state.pickedPart)?.label;
 return <div className="page" data-mode={state.mode}>
  <header className="masthead">
   <a className="brand" href="../../../README.md" aria-label="CyberMachine 仓库说明"><BrandMark/><span>CYBERMACHINE<small>R2 · 装配工作台</small></span></a>
   <nav className="mode-tabs" aria-label="学习方式"><button role="tab" aria-selected={state.mode==='learn'} onClick={()=>setState(s=>({...s,mode:'learn',playing:false}))}>分步教学</button><button role="tab" aria-selected={state.mode==='practice'} onClick={goPractice}>自己装一次<span aria-hidden="true">↗</span></button></nav>
   <div className="header-actions"><a href="../../anatomy/r2/index.html">结构图 <span aria-hidden="true">↗</span></a><button className="theme-button" onClick={()=>setState(s=>({...s,theme:Object.keys(themeNames)[(Object.keys(themeNames).indexOf(s.theme)+1)%3]}))} aria-label={`切换主题，当前${themeNames[state.theme]}`}><span className="theme-swatch"/>{themeNames[state.theme]}</button></div>
  </header>

  <nav className="chapter-nav" aria-label="教学章节">{CHAPTERS.map((c,i)=><button key={c.short} aria-current={state.mode==='learn'&&state.chapter===i?'step':undefined} onClick={()=>goChapter(i)}><span className="chapter-number">{String(i+1).padStart(2,'0')}</span><span>{c.short}</span><span className="chapter-nav-line" aria-hidden="true"/></button>)}</nav>

  <main className="workbench">
   <section className="visual-column" aria-label="三维装配视图">
    <div className="stage" ref={stage} tabIndex="0" aria-label="三维工作台。拖动旋转，滚轮缩放。左右键调节进度，空格播放，数字 1 至 5 切换章节。" data-ready={!!ready}>
     <div className="stage-heading"><span>R2 / {state.mode==='practice'?'装配练习':`0${state.chapter+1} · ${chapter.short}`}</span><span>单位 mm</span></div>
     <Viewer state={state} reduced={reduced} revision={revision} onReady={onReady} active={active}
      onPick={id=>setState(s=>({...s,pickedPart:id,selectedBay:id?.startsWith('drive-')?+id.split('-')[1]:s.selectedBay}))}
      onInstall={install} onInteract={()=>setState(s=>({...s,playing:false}))}/>
     {!ready&&<div className="loading" role="status"><span className="loading-ring"/>正在准备三维零件</div>}
     <div className="stage-caption"><span className={pickedLabel?'picked':''}>{pickedLabel??(state.mode==='practice'?'选择零件后，在标记处安装':'拖动旋转 · 滚轮缩放')}</span><button onClick={()=>{setRevision(r=>r+1);setState(s=>({...s,pickedPart:null}));}} aria-label="复位视角">复位视角 <span aria-hidden="true">↺</span></button></div>
    </div>
    <div className="view-tools">
     <div className="thickness-options" aria-label="硬盘厚度">{[['mixed','混合厚度'],['9.5','全 9.5 mm'],['7','全 7 mm']].map(([mode,label])=><button key={mode} aria-pressed={state.thicknessMode===mode} onClick={()=>changeThickness(mode)}>{label}</button>)}</div>
     <button className="cutaway-button" aria-pressed={state.cutaway} onClick={()=>setState(s=>({...s,cutaway:!s.cutaway}))}><span aria-hidden="true">{state.cutaway?'◇':'▱'}</span>{state.cutaway?'显示外壳':'查看内部'}</button>
    </div>
    {(state.chapter===4||state.mode==='practice')&&<div className="bay-selector"><span>查看盘位</span><div>{[1,2,3,4,5].map(i=><button key={i} aria-label={`选择 ${i} 号盘位`} aria-pressed={state.selectedBay===i} onClick={()=>setState(s=>({...s,selectedBay:i,pickedPart:null}))}>{String(i).padStart(2,'0')}</button>)}</div><output>{String(state.selectedBay).padStart(2,'0')} · {thickness(state.thicknessMode,state.selectedBay)} mm</output></div>}
    <div className="model-note"><span className="note-mark" aria-hidden="true">i</span>R2 设计装配示意 · 原厂 TACO 模型与参数化机箱 · 实物配合仍需试装</div>
   </section>

   {state.mode==='learn'?<aside className="lesson-panel" aria-label="当前章节">
    <div className="lesson-count"><span>第 {state.chapter+1} 章，共 5 章</span><span>{String(Math.round(state.progress*100)).padStart(2,'0')}%</span></div>
    <h1>{chapter.title}</h1><p className="chapter-description">{chapter.description}</p>
    <div className="parts-caption">{chapter.parts}</div>
    <ol className="phase-list">{PHASES[state.chapter].map((p,i)=>{
     const done=state.progress>=p.end,isCurrent=i===phase.index;
     return <li key={p.title} className={`${isCurrent?'current':''} ${done?'done':''}`}><button onClick={()=>setState(s=>({...s,progress:i===0?0:PHASES[s.chapter][i-1].end+.001,playing:false,cutaway:false}))} aria-current={isCurrent?'step':undefined}><span className="phase-marker" aria-hidden="true">{done?'✓':i+1}</span><span>{p.title}</span></button></li>;
    })}</ol>
    <div className="instruction" aria-live="polite"><p>{phase.copy}</p></div>
    <div className="progress-control"><div><label htmlFor="lesson-progress">本章装配进度</label><output htmlFor="lesson-progress">{Math.round(state.progress*100)}%</output></div><input id="lesson-progress" type="range" min="0" max="1000" step="1" value={Math.round(state.progress*1000)} onChange={e=>setState(s=>({...s,progress:+e.target.value/1000,playing:false}))} aria-valuetext={`${Math.round(state.progress*100)}%，${phase.title}`}/></div>
    <div className="playback"><button className="primary" onClick={togglePlay} aria-pressed={state.playing}><span aria-hidden="true">{state.playing?'Ⅱ':'▶'}</span>{reduced?'显示本章完成状态':state.playing?'暂停演示':state.progress===1?'再次播放':'播放本章'}</button><button className="rate-button" aria-label={`播放速度，当前 ${state.playbackRate} 倍`} onClick={()=>setState(s=>({...s,playbackRate:[.5,1,2,4][([.5,1,2,4].indexOf(s.playbackRate)+1)%4]}))}>{state.playbackRate}×</button><button className="replay" onClick={()=>setState(s=>({...s,progress:reduced?1:0,playing:!reduced,cutaway:false}))} aria-label="重播本章">↺</button></div>
    <p className="practical-note">{chapter.note}</p>
    <div className="chapter-pager"><button disabled={state.chapter===0&&state.progress===0} onClick={()=>stepLesson(-1)}>← 上一步</button><button onClick={()=>stepLesson(1)}>{state.chapter===4&&state.progress===1?'开始装配练习':'下一步'} <span aria-hidden="true">→</span></button></div>
   </aside>:<aside className="practice-panel" aria-label="装配练习">
    <div className="lesson-count"><span>零件托盘</span><span>{complete} / {actions.length}</span></div><h1>现在，由你来装。</h1><p className="chapter-description">点选或拖放零件。安装位置会在三维视图中标出。</p>
    <div className={`practice-message ${message.kind}`} role={message.kind==='error'?'alert':'status'}><span aria-hidden="true">{message.kind==='success'?'✓':message.kind==='error'?'!':'↗'}</span><p>{message.text}</p></div>
    <div className="parts-tray" aria-label="零件列表">{actions.map(id=>{
     const installed=state.installed.includes(id),selected=state.selectedPart===id;
     return <button key={id} draggable={!installed} data-part={id} className={`${installed?'installed':''} ${selected?'selected':''}`} aria-pressed={selected}
      onClick={()=>selectPart(id)} onDragStart={e=>{e.dataTransfer.setData('application/x-cybermachine-part',id);e.dataTransfer.setData('text/plain',id);e.dataTransfer.effectAllowed='move';selectPart(id);}}>
      <span className="part-symbol" aria-hidden="true">{installed?'✓':id.startsWith('drive')?'▤':id.startsWith('fix')?'⊕':id==='wifi'?'▱':'◇'}</span><span>{actionLabel(id)}</span><small>{installed?'已就位':selected?'已选择':'选择'}</small>
     </button>;
    })}</div>
    <button className="reset-practice" onClick={()=>{setState(s=>({...s,installed:[],selectedPart:'frame',cutaway:false}));setMessage({kind:'info',text:'练习已重置，从开放的框架重新开始。'});setRevision(r=>r+1);}}>重新装一次 <span aria-hidden="true">↺</span></button>
   </aside>}
  </main>
  <footer className="page-footer"><span>5 × 2.5″ SATA · Radxa TACO V1.61 + CM5</span><div><a href="preview.mp4">30 秒操作预览 ↗</a><a href="README.md">装配与复现说明 ↗</a></div></footer>
  <details className="sources"><summary>模型来源与安装边界</summary><div><p>机箱使用现有 R2 参数几何，TACO 使用仓库原厂 V1.61 STEP。CM5、散热器、硬盘和通用无线模块含简化细节。原厂 STEP 未包含 E-Key 实体，教程依据 V1.61 器件位置图补绘其安装示意，连接器高度和天线形状仍需按实际型号核对。</p><p>R2 尚无对应打印项目或制造 STEP。本教程不作为 R1 打印件的装配说明，不代表已完成实物试装、温升、振动或噪声测试。天线仅展示端子与避让布线，本次未增加机壳天线孔。</p><p><a href="../../../references/radxa-taco/radxa_taco_3d_stp_v1.61.stp">TACO V1.61 STEP</a> · <a href="../../../references/radxa-taco/rad-doc-0030_radxa_taco_product_brief__revision_1.2_g4dfad65.pdf">产品简介 Rev.1.2</a> · <a href="../../../references/radxa-taco/radxa_taco_components_placement_map_v1.61.pdf">器件位置图</a></p></div></details>
 </div>;
}

createRoot(document.getElementById('root')).render(<App/>);
