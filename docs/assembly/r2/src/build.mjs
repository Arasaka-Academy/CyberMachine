import {build} from 'vite';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import './collect-licenses.mjs';
const here=dirname(fileURLToPath(import.meta.url));
const result=await build({configFile:resolve(here,'vite.config.mjs'),build:{write:false}});
const outputs=(Array.isArray(result)?result:[result]).flatMap(r=>r.output);
let html=outputs.find(o=>o.fileName==='index.html')?.source;
if(typeof html!=='string')throw new Error('Vite did not produce index.html');
const files=new Map(outputs.map(o=>[o.fileName,o]));
html=html.replace(/<script\b[^>]*\bsrc="([^"]+)"[^>]*><\/script>/g,(tag,url)=>{
 const entry=files.get(url.replace(/^\.\//,''));
 return entry?.type==='chunk'?`<script type="module">${entry.code.replace(/<\/script/gi,'<\\/script')}</script>`:tag;
});
html=html.replace(/<link\b[^>]*\bhref="([^"]+)"[^>]*>/g,(tag,url)=>{
 const entry=files.get(url.replace(/^\.\//,''));
 return entry?.fileName.endsWith('.css')?`<style>${entry.source}</style>`:tag;
});
if(/<(?:script|link)\b[^>]*(?:src|href)="(?:\.\/)?assets\//.test(html))throw new Error('Offline build retained external assets');
const out=resolve(here,'../index.html');
writeFileSync(out,html);
const report={htmlBytes:Buffer.byteLength(html),externalRuntimeAssets:0,buildTool:'Vite',generated:new Date().toISOString()};
mkdirSync(resolve(here,'../../../../work/assembly-r2'),{recursive:true});
writeFileSync(resolve(here,'../../../../work/assembly-r2/build-report.json'),JSON.stringify(report,null,2)+'\n');
console.log(`Standalone offline lesson: ${out} (${(report.htmlBytes/1024/1024).toFixed(2)} MiB)`);
