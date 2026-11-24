/**
 * [INPUT]: 候选 GLB、接口 metadata、credits.md 与 Vite。
 * [OUTPUT]: 内嵌模型、脚本、样式及许可，并重定位文档链接的离线页面。
 * [POS]: 从src目录生成父目录页面的构建边界，保持两处导航目标一致。
 * [PROTOCOL]: Update this header on change, then check AGENTS.md
 */
import {build} from 'vite';
import {readFileSync,writeFileSync,existsSync,mkdirSync} from 'node:fs';
import {resolve,dirname,relative,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {gzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
const here=dirname(fileURLToPath(import.meta.url));
const root=resolve(here,'../../../..');
const input=process.argv.find(a=>a.startsWith('--model='))?.slice(8);
const modelPath=input?resolve(input):['preview.glb','assembly.glb'].map(n=>resolve(root,'outputs/redesign-r3',n)).find(existsSync);
if(!modelPath)throw new Error('先生成 outputs/redesign-r3/preview.glb 或用 --model=/absolute/model.glb 指定候选。');
const modelBytes=readFileSync(modelPath);
const modelSha256=createHash('sha256').update(modelBytes).digest('hex');
const model64=gzipSync(modelBytes,{level:9,mtime:0}).toString('base64');
const metadataPath=resolve(dirname(modelPath),'metadata.json');
const metadataBytes=existsSync(metadataPath)?readFileSync(metadataPath):null;
const metadata=metadataBytes?JSON.parse(metadataBytes):{};
if(metadata.previewGlbSha256&&metadata.previewGlbSha256!==modelSha256)throw new Error('metadata 与候选 GLB 的 SHA256 不一致；先完成同一批导出。');
const virtual={'virtual:r3-model':model64,'virtual:r3-metadata':metadata};
const result=await build({configFile:false,root:here,base:'./',plugins:[{name:'inline-r3-cad',resolveId:id=>Object.hasOwn(virtual,id)?'\0'+id:null,load:id=>id.startsWith('\0virtual:r3-')?`export default ${JSON.stringify(virtual[id.slice(1)])};`:null}],build:{write:false,target:'es2022',modulePreload:false,cssCodeSplit:false,reportCompressedSize:false,sourcemap:false,rolldownOptions:{output:{codeSplitting:false}}}});
const output=(Array.isArray(result)?result:[result]).flatMap(r=>r.output);
const files=new Map(output.map(o=>[o.fileName,o]));
let html=output.find(o=>o.fileName==='index.html').source;
html=html.replace(/(<a\b[^>]*\bhref=")([^"]+)"/g,(tag,prefix,url)=>
 /^(?:[a-z][a-z\d+.-]*:|\/|#)/i.test(url)?tag:
 `${prefix}${relative(resolve(here,'..'),resolve(here,url)).split(sep).join('/')}"`);
const credits=readFileSync(resolve(here,'../credits.md'),'utf8');
const licenses=[...credits.matchAll(/```text\n([\s\S]*?)```/g)].map(m=>m[1].trim()).join('\n\n');
html=html.replace('</head>',`<script type="text/plain" id="third-party-licenses">${licenses}</script></head>`);
html=html.replace(/<script\b[^>]*\bsrc="([^"]+)"[^>]*><\/script>/g,(tag,url)=>{const x=files.get(url.replace(/^\.\//,''));return x?.type==='chunk'?`<script type="module">${x.code.replace(/<\/script/gi,'<\\/script')}</script>`:tag;});
html=html.replace(/<link\b[^>]*\bhref="([^"]+)"[^>]*>/g,(tag,url)=>{const x=files.get(url.replace(/^\.\//,''));return x?.fileName.endsWith('.css')?`<style>${x.source}</style>`:tag;});
if(/<(?:script|link)\b[^>]*(?:src|href)="(?:\.\/)?assets\//.test(html))throw new Error('离线构建仍引用外部资源。');
const out=resolve(here,'../index.html');
writeFileSync(out,html);
mkdirSync(resolve(root,'work/redesign-r3'),{recursive:true});
writeFileSync(resolve(root,'work/redesign-r3/ui-build.json'),JSON.stringify({modelSource:modelPath,modelSha256,metadataSha256:metadataBytes?createHash('sha256').update(metadataBytes).digest('hex'):null,htmlBytes:Buffer.byteLength(html),runtimeNetworkResources:0},null,2)+'\n');
console.log(`R3 offline design: ${out} (${(Buffer.byteLength(html)/1048576).toFixed(2)} MiB)`);
