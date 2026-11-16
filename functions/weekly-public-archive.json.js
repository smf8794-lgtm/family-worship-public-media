// Copy to the existing Pages project's functions/ directory.
export async function onRequest({request,env,next}) {
  if (!['GET','HEAD'].includes(request.method)) return new Response(null,{status:405,headers:{Allow:'GET, HEAD'}});
  try {
    const response=await env.MEDIA_READER.fetch(new Request('https://catalog.internal/weekly-public-archive.json',{method:request.method}));
    if (response.ok) return response;
  } catch {}
  return next(); // Existing Pages static archive when the binding is unavailable.
}
