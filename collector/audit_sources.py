from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import urlsplit

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError('redirect or login required')

def fetch(url):
    u = urlsplit(url)
    if u.scheme != 'https' or u.netloc != 'www.youtube.com' or u.path not in ('/watch','/playlist'):
        raise ValueError('unexpected public source')
    req = Request(url,headers={'Accept-Language':'ko','User-Agent':'FamilyWorship public catalog/3.74'})
    with build_opener(NoRedirect()).open(req,timeout=15) as response:
        data = response.read(4500001)
        if len(data)>4500000: raise ValueError('source too large')
        return data.decode('utf-8-sig')
