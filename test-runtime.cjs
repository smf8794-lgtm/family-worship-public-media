// Supply the local Miniflare module directory; no Cloudflare account is used.
const {Miniflare}=require(process.argv[2] || 'miniflare');
const fs=require('node:fs'), assert=require('node:assert/strict');
const seed=JSON.parse(fs.readFileSync('seed.json'));
const source=fs.readFileSync('worker.mjs','utf8').replace(/^import seed .*?;$/m,()=> 'const seed='+JSON.stringify(seed)+';');
(async()=>{
  let status=200;
  const mf=new Miniflare({modules:true,script:source,compatibilityDate:'2026-06-01',
    kvNamespaces:['MEDIA_CATALOG'],bindings:{CATALOG_REPO:'test/catalog'},port:0,host:'127.0.0.1',
    outboundService:async req=>{
      assert.equal(req.url,'https://raw.githubusercontent.com/test/catalog/catalog-state/archive.json');
      return new Response(JSON.stringify({revision:1,current:seed,previous:seed}),{status});
    }});
  try{
    const w=await mf.getWorker();
    const read=()=>mf.dispatchFetch('http://localhost/weekly-public-archive.json');
    assert.equal((await read()).headers.get('X-Catalog-State'),'seed');
    assert.equal((await w.scheduled()).outcome,'ok');
    assert.equal((await read()).headers.get('X-Catalog-State'),'current');
    const kv=await mf.getKVNamespace('MEDIA_CATALOG'),pair=await kv.get('catalog-pair-v1','json');
    status=429;
    try{await w.scheduled()}catch{}
    assert.deepEqual(await kv.get('catalog-pair-v1','json'),pair);
    pair.current.hash='broken';
    await kv.put('catalog-pair-v1',JSON.stringify(pair));
    assert.equal((await read()).headers.get('X-Catalog-State'),'previous');
    console.log('PASS workerd Cron, local KV, HTTP handler, 429 retention, previous revision fallback');
  }finally{await mf.dispose()}
})().catch(e=>{console.error(e);process.exitCode=1});
