import {readFileSync,readdirSync,existsSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const here=dirname(fileURLToPath(import.meta.url));
const lock=JSON.parse(readFileSync(resolve(here,'package-lock.json'),'utf8'));
const direct=new Set(Object.keys(lock.packages[''].devDependencies??{}).map(n=>`node_modules/${n}`));
const texts=[];
for(const [name,meta]of Object.entries(lock.packages).sort(([a],[b])=>a.localeCompare(b,'en'))){
 if(!name||meta.dev&&!direct.has(name))continue;
 const directory=resolve(here,name);
 if(!existsSync(directory))throw new Error(`Install locked dependency before building: ${name}`);
 const licenses=readdirSync(directory).filter(n=>/^(licen[cs]e|copying|notice)(\.|$)/i.test(n)).sort();
 texts.push(`${name.replace(/^node_modules\//,'')} ${meta.version}\nDeclared license: ${meta.license??'see package'}\n`+
  licenses.map(n=>`${n}\n${readFileSync(resolve(directory,n),'utf8').trim()}`).join('\n\n'));
}
const out=resolve(here,'../assets');mkdirSync(out,{recursive:true});
const text=texts.join('\n\n'+'='.repeat(72)+'\n\n')+'\n';
writeFileSync(resolve(out,'third-party-licenses.txt'),text.replace(/\r\n?/g,'\n'));
