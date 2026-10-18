"""Second real presence for isolated native render checks. Never production."""
import json
import time
import urllib.request
import sys
base='http://127.0.0.1:'+str(int(sys.argv[1]))+'/api/native/v1/'
auth=None
def call(path,data=None):
    headers={'Content-Type':'application/json'}
    if auth:headers['Authorization']='Bearer '+auth
    req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
    return json.load(urllib.request.urlopen(req,timeout=5))
assert call('bootstrap')['fixture'] is True
auth=call('session',dict(username='native-check-b',password='native-isolated-check'))['token']
joined=call('park/join',dict(pet=1));token=joined['token'];pet=next(p for p in joined['players'] if p['mine'])
try:
    for _ in range(500):
        time.sleep(.6)
        call('park/sync',dict(token=token,x=pet['x'],z=pet['z'],yaw=0,action='sniff'))
finally:
    call('park/leave',dict(token=token))
