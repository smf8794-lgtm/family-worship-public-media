import json
from unittest.mock import patch
from build import ROOT, build
import weekly_collect as w
seed=json.loads((ROOT/'seed.json').read_text('utf8'))
prior=seed['sources']['hymns']
def mock(k,rows):
    if k=='peace': raise ValueError('login required')
    if k=='hymns':
        item={**rows[0],'id':'MockItem0001'}
        return [item],dict(expected=4,listed=3,remaining=2,continuation=False,issues={'a':'http_429'})
    return rows
state=build(None,mock)
assert state['previous']==seed
assert state['current']['sources']['peace']['items']==seed['sources']['peace']['items']
h=state['current']['sources']['hymns']
assert h['status']=='partial' and len(h['items'])==len(prior['items'])+1
assert h['lastSuccess']==prior['lastSuccess']
assert state['current']['sources']['our-songs']['status']=='failed'
assert state['current']['praiseReviews']==seed['praiseReviews']
second=build(state,mock)
assert second['revision']==2 and second['previous']==state['current']
def fail(*args):raise ValueError('offline')
try:build(state,fail)
except RuntimeError:pass
else:raise AssertionError('all failed publication')
for reason,code in [('로그인이 필요합니다','login_required'),('봇','bot_check')]:
    with patch.object(w,'fetch',return_value=''),patch.object(w,'initial',return_value={'playabilityStatus':{'status':'LOGIN_REQUIRED','reason':reason}}):
        try:w.video('v','owner')
        except ValueError as e:assert str(e)==code
        else:raise AssertionError()
print('PASS partial/429/login/bot, unchanged reviews, last good, two revisions, total failure')
