"""Refresh Korean PeaceTV source links in this candidate. No accounts or uploads."""
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, build_opener
from audit_sources import NoRedirect
import re
import json

BASE = 'https://www.ipeacetv.com/vod/'
TITLE = re.compile(r'HJ글로벌뉴스\s*\(\d{4}년\s*\d{1,2}월\s*\d{1,2}일\)')
class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = {}
        self.title = None
        self.frames = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == 'li':
            self.title = attr.get('title', '').strip()
        if tag == 'iframe':
            self.frames.append(attr.get('src', ''))
        if tag == 'a' and TITLE.fullmatch(self.title or ''):
            url = urlsplit(urljoin(BASE, attr.get('href','')))
            query = parse_qs(url.query)
            vid = query.get('vId',[''])[0]
            if url.hostname == 'www.ipeacetv.com' and url.path == '/vod/vod_view.asp' and query.get('mId') == ['B04'] and vid.isdigit():
                self.links[vid] = self.title

    def handle_endtag(self, tag):
        if tag == 'li':
            self.title = None

    def handle_data(self, text):
        self.text.append(text.strip())

def read(url):
    request = Request(url, headers={'Cookie':'userSetLanguage=ko','User-Agent':'FamilyWorshipCatalog/3.69'})
    with build_opener(NoRedirect()).open(request, timeout=12) as response:
        if urlsplit(response.url).hostname != 'www.ipeacetv.com':
            raise ValueError('unexpected source')
        raw = response.read(2000001)
        if len(raw)>2000000:
            raise ValueError('oversized source')
        page = Page()
        page.feed(raw.decode(response.headers.get_content_charset() or 'utf-8'))
        return page

def collect():
    links = read(BASE+'vod_list.asp?mId=B04').links
    if not links:
        raise ValueError('한국어 뉴스 목록을 확인할 수 없습니다.')
    rows = []
    for vid,title in list(links.items())[:8]:
        page = read(BASE+'vod_view.asp?vId='+vid+'&page=1')
        text = ' '.join(page.text)
        published = re.search(r'등록일\s*:\s*(\d{4}-\d\d-\d\d)',text)
        frame = next((s for s in page.frames if re.fullmatch(r'https://player\.vimeo\.com/video/\d+',s)), None)
        if title not in text or not published:
            raise ValueError(f'{vid} title={title in text}, player={bool(frame)}, date={bool(published)}')
        row=dict(vodId=vid,title=title,published=date.fromisoformat(published[1]).isoformat(),player=frame)
        rows.append(row)
        # Probe only the leading broadcast; older rows remain manual or previously reviewed.
        if len(rows)==1 and frame:
            video_id=frame.rsplit('/',1)[1]
            endpoint='https://vimeo.com/api/oembed.json?url=https%3A%2F%2Fvimeo.com%2F'+video_id
            try:
                with build_opener(NoRedirect()).open(endpoint,timeout=12) as response:
                    buf=response.read(32769)
                if len(buf)>32768:continue
                evidence=json.loads(buf)
                if (str(evidence.get('video_id'))==video_id and evidence.get('provider_name')=='Vimeo'
                    and evidence.get('type')=='video' and re.search(r'src="https://player\.vimeo\.com/video/'+video_id+r'(?:[?"][^"]*)',evidence.get('html',''))):
                    row['sourceProof']={'contract':'peace-b04-vimeo-v1','category':'peace','playlist':'B04',
                                        'languageEvidence':'ko-official-edition','checked':datetime.now(timezone.utc).isoformat()}
            except (OSError,ValueError):
                pass
    return rows
