import {defineConfig} from 'vite';
import {fileURLToPath} from 'node:url';
export default defineConfig({
 root:fileURLToPath(new URL('.',import.meta.url)),base:'./',
 assetsInclude:['**/*.glb','**/*.glb.gz'],
 server:{host:'127.0.0.1',port:5420,strictPort:true},
 build:{target:'es2022',modulePreload:false,cssCodeSplit:false,assetsInlineLimit:64*1024*1024,
   sourcemap:false,reportCompressedSize:false,
   rolldownOptions:{output:{codeSplitting:false}}},
});
