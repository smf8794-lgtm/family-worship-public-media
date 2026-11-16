"""Local weekly collector. Only public allowlisted source metadata is stored."""
import argparse
import json
import os
import re
import sqlite3
import tempfile
import time
from urllib.error import HTTPError
from datetime import datetime, timezone, timedelta
from pathlib import Path
from audit_sources import fetch
import peacetv_source

ROOT=Path(__file__).resolve().parent
CHANNEL='UC6GBnJvC5NiQmirEyzPY7mQ'
PLAYLISTS={
    'life-course':('PLT0wBjA8IDEYb4qdr8Hn-ZrouC95kqIw4',CHANNEL,'키즈 참부모님 생애노정'),
    'kids-principle':('PLT0wBjA8IDEZ3sUnomRapQDs7PfjMtF5G',CHANNEL,'키즈 원리'),
    'hyodong-worship':('PLT0wBjA8IDEausec_S7FdsP6ZDDnwcNy-',CHANNEL,'효동예배 말씀 영상'),
    'hymns':('PL184Y8ZQNfw10xm4z3OsU_U91xvJGXP5S','UCA553nohoMqf5UW2YDM6dpA','성가'),
    'our-songs':('PL184Y8ZQNfw06mgW85EysHnEPWgqW813M','UCA553nohoMqf5UW2YDM6dpA','가정연합 음악, 우리노래'),
    'cheonsimwon':('PLbbi9lbBAkkQysOeywegjQ20Z2RcbSuEQ','UC4OYb7odqXWQW2g2tF5HrqQ','CheonShim Won Music'),
    'newspick-community':('PLXrKI5D7hMOw','UCA553nohoMqf5UW2YDM6dpA','가정연합 뉴스픽'),
    'hyodong':('PLT0wBjA8IDEZ99t72AVOj6nDyPjXwdDM_',CHANNEL,'효동예배 동요＆율동 영상'),
    'preschool':('PLMUyAUzT5nrs',CHANNEL,'(유치) 효동예배 말씀 영상'),
    'primary':('PLdFcKzxgz4hM',CHANNEL,'(유년) 효동예배 말씀 영상'),
    'elementary':('PLDQ2326v1wf8',CHANNEL,'(초등) 효동예배 말씀 영상'),
}
def nodes(obj,key):
    if isinstance(obj,dict):
        if key in obj: yield obj[key]
        for value in obj.values(): yield from nodes(value,key)
    if isinstance(obj,list):
        for value in obj: yield from nodes(value,key)
def initial(body,symbol):
    marker=re.search(r'(?:var )?'+symbol+r'\s*=\s*',body)
    if not marker: raise ValueError('public page data unavailable')
    return json.JSONDecoder().raw_decode(body,marker.end())[0]
def members(pid,owner,title):
    data=initial(fetch('https://www.youtube.com/playlist?list='+pid),'ytInitialData')
    head=data['header']
    if owner not in nodes(head,'browseId') or pid not in nodes(head,'playlistId') or data['metadata']['playlistMetadataRenderer']['title']!=title:
        raise ValueError('source identity mismatch')
    counts=[int(m[1].replace(',','')) for v in nodes(head,'content') if isinstance(v,str) and (m:=re.fullmatch(r'동영상 ([0-9,]+)개',v))]
    rows={}
    for v in nodes(data['contents'],'lockupViewModel'):
        vid=v.get('contentId')
        if re.fullmatch(r'[\w-]{11}',vid or '') and any(w.get('playlistId')==pid and w.get('videoId')==vid for w in nodes(v,'watchEndpoint')):
            rows[vid]=True
    expected=counts[0] if len(set(counts))==1 else None
    if not rows and expected!=0: raise ValueError('listing unreadable')
    info={'listed':len(rows),'expected':expected,'hiddenNotice':any('사용할 수 없는 동영상' in t for t in nodes(data,'content') if isinstance(t,str)),
          'continuation':bool(list(nodes(data['contents'],'continuationItemRenderer')))}
    return list(rows),info
def video(vid,owner,category=None):
    data=initial(fetch('https://www.youtube.com/watch?v='+vid),'ytInitialPlayerResponse')
    status=data.get('playabilityStatus',{})
    if status.get('status')!='OK':
        reason=str(status.get('reason','')).lower()
        if '봇' in reason or 'bot' in reason:raise ValueError('bot_check')
        if '삭제' in reason or 'removed' in reason or 'deleted' in reason:raise ValueError('removed')
        if '비공개' in reason or 'private' in reason:raise ValueError('private')
        raise ValueError('login_required' if status.get('status')=='LOGIN_REQUIRED' else 'unavailable')
    v=data['videoDetails'];meta=data['microformat']['playerMicroformatRenderer']
    if v['videoId']!=vid or meta['externalVideoId']!=vid or meta['externalChannelId']!=v['channelId']:
        raise ValueError('video identity mismatch')
    if v.get('isPrivate') or meta.get('isUnlisted'):raise ValueError('private_or_unlisted')
    published=meta['publishDate']
    if datetime.fromisoformat(published).tzinfo is None:raise ValueError('publication time unavailable')
    row=dict(id=vid,title=v['title'],published=published,channel=v['channelId'],playlistOwner=owner,duration=int(v['lengthSeconds']),embedReported=status.get('playableInEmbed') is True)
    suffix={'hyodong':'율동','preschool':'유치부 말씀 영상','primary':'유년부 말씀 영상','elementary':'초등부 말씀 영상'}.get(category)
    tracks=data.get('captions',{}).get('playerCaptionsTracklistRenderer',{}).get('captionTracks',[])
    korean=any(t.get('languageCode')=='ko' and t.get('kind')=='asr' for t in tracks)
    if (suffix and owner==CHANNEL==v['channelId'] and row['embedReported'] and korean
        and row['duration']>0 and v.get('isPrivate') is False and meta.get('isUnlisted') is False
        and not v.get('isLiveContent') and re.search(r'[|｜]\s*효동예배\s+'+suffix+r'\s*$',v['title'])):
        row['sourceProof']={'contract':'hyodong-list-watch-v1','category':category,'playlist':PLAYLISTS[category][0],
                            'languageEvidence':'ko-asr','checked':stamp()}
    return row
def collect(key,known,previous_issues=None):
    if key=='peace':
        rows=[dict(id=r['vodId'],title=r['title'],published=r['published'],player=r['player'],
                     **({'sourceProof':r['sourceProof']} if 'sourceProof' in r else {})) for r in peacetv_source.collect()]
        return rows,dict(expected=len(rows),listed=len(rows),remaining=0,continuation=False,listedIds=[r['id'] for r in rows])
    pid,owner,title=PLAYLISTS[key]
    ids,info=members(pid,owner,title)
    cached={row['id']:row for row in known};rows=[];issues={};reads=0
    # Limit new detail requests per source. Already archived publication dates are stable.
    anchors={'hymns':'OWmBIYCFb6A','our-songs':'XIXpxsA3yKs','newspick-community':'avW4vxMiXXA','cheonsimwon':'1qk33te5GMI'}
    ids.sort(key=lambda i:(i in (previous_issues or {}), i!=anchors.get(key)))
    for vid in ids:
        if vid in cached:rows.append(cached[vid]);continue
        if reads>=5:continue
        reads+=1
        try:rows.append(video(vid,owner,key))
        except HTTPError as e:
            issues[vid]='http_'+str(e.code)
            if e.code==429:break
        except Exception as e:issues[vid]=str(e)[:100] if isinstance(e,ValueError) else type(e).__name__
    info.update(issues=issues,verified=len(rows),remaining=len(ids)-len(rows),listedIds=ids)
    return rows,info

def db_open(path):
    db=sqlite3.connect(path,timeout=30)
    db.execute('CREATE TABLE IF NOT EXISTS revisions(id INTEGER PRIMARY KEY,stamp TEXT,body TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS active(singleton INTEGER PRIMARY KEY CHECK(singleton=1),revision INTEGER REFERENCES revisions(id))')
    db.commit()
    return db
def current(db):
    row=db.execute('SELECT body FROM revisions JOIN active ON revisions.id=active.revision').fetchone()
    return json.loads(row[0]) if row else {}
def published_time(value):
    parsed=datetime.fromisoformat(value)
    if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=timezone(timedelta(hours=9)))
    return parsed.timestamp()

def stamp():
    return datetime.now(timezone.utc).isoformat()
def update(db,loader=collect):
    db.execute('BEGIN IMMEDIATE')
    try:
        sources=current(db);now=stamp();youtube_limited=False
        for key in ['peace',*PLAYLISTS]:
            prior=sources.get(key,{})
            try:
                if youtube_limited and key!='peace':raise ValueError('YouTube rate limit; deferred')
                result=collect(key,prior.get('items',[]),prior.get('observation',{}).get('issues')) if loader is collect else loader(key,prior.get('items',[]))
                rows,info=result if isinstance(result,tuple) else (result,{})
                youtube_limited='http_429' in info.get('issues',{}).values()
                partial=bool(info and (info['expected']!=len(rows) or info['continuation'] or info['remaining']))
                archive={r['id']:r for r in prior.get('items',[])}
                archive.update({r['id']:r for r in rows})
                sources[key]=dict(status='partial' if partial else ('ok' if rows else 'empty'),checked=now,lastSuccess=prior.get('lastSuccess') if partial else now,observation=info,
                    items=sorted(archive.values(),key=lambda r:published_time(r['published']),reverse=True))
            except Exception as e:
                if isinstance(e,HTTPError) and e.code==429:youtube_limited=True
                problem=f'HTTP {e.code}' if isinstance(e,HTTPError) else str(e)[:160] if isinstance(e,ValueError) else type(e).__name__
                sources[key]={**prior,'status':'failed','checked':now,'error':problem,'items':prior.get('items',[])}
        revision=db.execute('INSERT INTO revisions(stamp,body) VALUES (?,?)',(now,json.dumps(sources,ensure_ascii=False))).lastrowid
        db.execute('INSERT OR REPLACE INTO active VALUES (1,?)',(revision,));db.commit()
        return sources
    except BaseException:
        db.rollback();raise
