"""Actual cat -> telemetry -> observatory decision evidence, isolated account and model."""
import base64,json,os,subprocess,tempfile,threading,time,urllib.request
from pathlib import Path
from werkzeug.serving import make_server,WSGIRequestHandler
from test_companion import CompanionTests
from gpu_launcher import CDP,ROOT

class Quiet(WSGIRequestHandler):
    def log(self,*args,**kwargs):pass

fixture=CompanionTests();fixture.setUp()
fixture.model.plan_once=lambda messages: '{"target":"bridge","action":"observe"}'
server=make_server('127.0.0.1',0,fixture.app,threaded=True,request_handler=Quiet)
threading.Thread(target=server.serve_forever,daemon=True).start()
browser=page=None
try:
    with tempfile.TemporaryDirectory(prefix='pait-meadow-browser-') as tmp:
        plan=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/start-island.ps1'),'-Inspect'],text=True,encoding='utf-8'))
        chrome=subprocess.Popen([plan['Chrome'],'--headless=new','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--use-angle=d3d11','--use-adapter-luid='+plan['Selected']['Luid'],'--user-data-dir='+tmp,'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            pf=Path(tmp)/'DevToolsActivePort'
            for _ in range(100):
                if pf.exists():break
                time.sleep(.2)
            port,endpoint=pf.read_text().splitlines()[:2];browser=CDP('ws://127.0.0.1:'+port+endpoint)
            tabs=json.load(urllib.request.urlopen('http://127.0.0.1:'+port+'/json/list'));page=CDP(next(t for t in tabs if t['type']=='page')['webSocketDebuggerUrl'])
            page.call('Page.enable');page.call('Runtime.enable')
            page.call('Emulation.setDeviceMetricsOverride',{'width':1500,'height':1000,'deviceScaleFactor':1,'mobile':False})
            def js(code,awaited=False):
                r=page.call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':awaited})
                if r.get('exceptionDetails'):raise AssertionError(r['exceptionDetails'])
                return r.get('result',{}).get('value')
            def wait(code,seconds=60):
                for _ in range(int(seconds*2)):
                    result=js(code)
                    if result:return result
                    time.sleep(.5)
                raise AssertionError('Timed out: '+code+'; '+str(js('window.__denLocomotionDebug?.()')))
            url=f'http://127.0.0.1:{server.server_port}/den?pet=3&scene=day'
            page.call('Network.setCookie',{'name':'session','value':fixture.a.get_cookie('session').value,'url':url})
            page.call('Page.navigate',{'url':url})
            wait("window.__denLocomotionDebug?.()?.radius>20")
            js("if(document.getElementById('btn-roam').getAttribute('aria-pressed')!=='true')document.getElementById('btn-roam').click()")
            selected=None
            for _ in range(100):
                state=fixture.a.get('/api/cat-agent/monitor').json
                selected=next((s for s in state['streams'] if s['snapshot'].get('decision',{} ) and s['snapshot']['decision'].get('selection')),None)
                if selected:break
                time.sleep(.5)
            assert selected, 'actual cat telemetry never reached monitor'
            decision=selected['snapshot']['decision']
            assert decision['candidateCount']>0 and decision['ranked']
            assert 'thirst' in decision['needs']
            assert decision['selection']['source'] in ('local','model')
            assert fixture.b.get('/api/cat-agent/monitor').json['streams']==[], 'account leak'
            page.call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/cat-agent-monitor'})
            wait("document.getElementById('decision-ranking')?.children.length>0")
            assert js("document.getElementById('decision-choice').textContent.includes('→')")
            assert js("document.getElementById('decision-needs').textContent.includes('口渴')")
            out=Path(tempfile.gettempdir())/'pait-decision-live.png'
            out.write_bytes(base64.b64decode(page.call('Page.captureScreenshot',{'format':'png'})['data']))
            print(json.dumps({'passed':True,'actualDecision':decision['selection'],'candidates':decision['candidateCount'],'screenshot':str(out)},ensure_ascii=False))
        finally:
            if page:page.close()
            if browser:
                try:browser.call('Browser.close')
                except Exception:pass
                browser.close()
            try:chrome.wait(timeout=15)
            except subprocess.TimeoutExpired:chrome.terminate();chrome.wait(timeout=10)
            time.sleep(.5)
finally:
    server.shutdown();server.server_close();fixture.tearDown()
