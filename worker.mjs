import seed from './seed.json' with {type:'json'};
const key='catalog-pair-v1', maxBytes=512*1024;
const known=Object.keys(seed.sources);
const allowedItem=new Set(['id','title','published','player','channel','duration','embedReported','playlistOwner','sourceProof']);
const feeds={hyodong:'PLT0wBjA8IDEZ99t72AVOj6nDyPjXwdDM_',preschool:'PLMUyAUzT5nrs',primary:'PLdFcKzxgz4hM',elementary:'PLDQ2326v1wf8',peace:'B04'};
function proofOK(k,i){
  const p=i.sourceProof;
  if(p===undefined)return true;
  return p&&Object.hasOwn(feeds,k)&&Object.keys(p).length===5&&p.category===k&&p.playlist===feeds[k]&&Number.isFinite(Date.parse(p.checked))&&
    (k==='peace'?p.contract==='peace-b04-vimeo-v1'&&p.languageEvidence==='ko-official-edition'&&Boolean(i.player):
    p.contract==='hyodong-list-watch-v1'&&p.languageEvidence==='ko-asr'&&i.embedReported===true&&
    i.channel==='UC6GBnJvC5NiQmirEyzPY7mQ'&&i.playlistOwner===i.channel);
}
function valid(a) {
  if(a?.schema!==1 || Object.keys(a).some(k=>!['schema','sources','praiseReviews'].includes(k)) ||
     !a.sources || Object.keys(a.sources).length!==known.length ||
     JSON.stringify(a.praiseReviews)!==JSON.stringify(seed.praiseReviews)) return false;
  return known.every(k=>{
    const s=a.sources[k];
    return ['ok','partial','empty','failed'].includes(s?.status) &&
      Object.keys(s).every(f=>['status','checked','lastSuccess','observation','items','error'].includes(f)) &&
      Object.keys(s.observation||{}).every(f=>['expected','remaining','issues','continuation','listed','listedIds','hiddenNotice','verified'].includes(f)) &&
      Array.isArray(s.items) &&
      s.items.every(i=>i && proofOK(k,i) && Object.keys(i).every(f=>allowedItem.has(f)) && typeof i.title==='string' &&
      i.title.length<=500 && Number.isFinite(Date.parse(i.published)) &&
      (k==='peace'? /^\d+$/.test(i.id) && (!i.player || /^https:\/\/player\.vimeo\.com\/video\/\d+$/.test(i.player)):
        /^[\w-]{11}$/.test(i.id) && /^UC[\w-]{22}$/.test(i.channel)));
  });
}
async function wrap(archive) {
  const body=JSON.stringify(archive);
  const bytes=new TextEncoder().encode(body);
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
  return {hash,body};
}
async function verified(record) {
  if (!record?.body) return false;
  try {
    const a=JSON.parse(record.body);
    return valid(a) && (await wrap(a)).hash===record.hash;
  } catch {return false}
}
export async function refresh(env,fetcher=fetch) {
  if (!/^[\w.-]+\/[\w.-]+$/.test(env.CATALOG_REPO)||env.CATALOG_REPO.startsWith('OWNER/')) throw Error('configure metadata repository');
  const url='https://raw.githubusercontent.com/'+env.CATALOG_REPO+'/catalog-state/archive.json';
  const r=await fetcher(url,{redirect:'manual',signal:AbortSignal.timeout(15000)});
  if (!r.ok) throw Error('metadata source HTTP '+r.status);
  const reader=r.body.getReader(), chunks=[];let size=0;
  for (;;) {
    const {value,done}=await reader.read();if(done)break;
    size+=value.length;if(size>maxBytes){await reader.cancel();throw Error('catalog size limit')}
    chunks.push(value);
  }
  const data=await new Response(new Blob(chunks)).json();
  if (!Number.isSafeInteger(data.revision)||data.revision<1||!valid(data.current)||!valid(data.previous)) throw Error('invalid catalog');
  const old=await env.MEDIA_CATALOG.get(key,'json');
  if(old?.revision>data.revision)return;
  if(old?.revision===data.revision && await verified(old.current) && await verified(old.previous))return;
  const pair={revision:data.revision,current:await wrap(data.current),previous:await wrap(data.previous)};
  await env.MEDIA_CATALOG.put(key,JSON.stringify(pair));
}
export default {
  async scheduled(event,env){
    try{await refresh(env)}catch(error){console.error('Catalog refresh failed:',error.message);throw error}
  },
  async fetch(req,env){
    if(new URL(req.url).pathname!=='/weekly-public-archive.json')return new Response(null,{status:404});
    if(!['GET','HEAD'].includes(req.method))return new Response(null,{status:405,headers:{Allow:'GET, HEAD'}});
    let record,version='seed';
    try {
      const pair=await env.MEDIA_CATALOG.get(key,'json');
      for(const slot of ['current','previous']) if(await verified(pair?.[slot])){record=pair[slot];version=slot;break}
    } catch {}
    record??=await wrap(seed);
    return new Response(req.method==='HEAD'?null:record.body,{headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-cache','X-Catalog-State':version,'ETag':'"'+record.hash+'"','X-Content-Type-Options':'nosniff'}});
  }
};
