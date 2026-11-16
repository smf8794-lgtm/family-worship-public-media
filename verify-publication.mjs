import {readFile} from 'node:fs/promises';
import {refresh} from './worker.mjs';
const bytes=await readFile(process.argv[2]);
let accepted=false;
await refresh({CATALOG_REPO:'offline/catalog',MEDIA_CATALOG:{
  get:async()=>null,put:async()=>{accepted=true}
}},async()=>new Response(bytes));
if(!accepted)throw Error('candidate was not accepted');
console.log('Publication satisfies Worker contract');
