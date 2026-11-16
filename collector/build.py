"""Construct the next public state using an ephemeral in-memory DB."""
import json
from pathlib import Path
import sys
import weekly_collect as w

ROOT = Path(__file__).resolve().parents[1]

def build(previous, loader=w.collect):
    seed=json.loads((ROOT/'seed.json').read_text('utf8'))
    old=previous['current'] if previous else seed
    if old['sources'].keys()!=seed['sources'].keys(): raise ValueError('invalid previous state')
    db=w.db_open(':memory:')
    try:
        with db:
            rev=db.execute('INSERT INTO revisions(stamp,body) VALUES (?,?)',(w.stamp(),json.dumps(old['sources']))).lastrowid
            db.execute('INSERT INTO active VALUES (1,?)',(rev,))
        sources=w.update(db,loader)
    finally: db.close()
    if all(s['status']=='failed' for s in sources.values()): raise RuntimeError('all sources failed; retain publication')
    current={'schema':1,'sources':sources,'praiseReviews':seed['praiseReviews']}
    return {'revision':previous['revision']+1 if previous else 1,'current':current,'previous':old}

if __name__=='__main__':
    old=Path(sys.argv[1])
    state=build(json.loads(old.read_text('utf8')) if old.exists() else None)
    Path(sys.argv[2]).write_text(json.dumps(state,ensure_ascii=False,separators=(',',':')),'utf8')
