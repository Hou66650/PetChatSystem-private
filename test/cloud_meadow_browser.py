"""Actual Chrome/GPU loading and walking, disposable account and model double."""
import base64,json,os,subprocess,tempfile,threading,time,urllib.request
from pathlib import Path
from werkzeug.serving import make_server,WSGIRequestHandler
from test_companion import CompanionTests
from gpu_launcher import CDP,ROOT

class Quiet(WSGIRequestHandler):
    def log(self,*args,**kwargs):pass

fixture=CompanionTests();fixture.setUp()
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
            wait("window.__denLocomotionDebug?.()?.radius>20 && (()=>{let found=false;window.__den?.scene.traverse(o=>{if(o.userData.meadow_extension)found=true});return found})()")
            js("if(document.getElementById('btn-roam').getAttribute('aria-pressed')==='true')document.getElementById('btn-roam').click()")
            wait("['idle','walk','trot','run'].includes(window.__denLocomotionDebug().animation)")
            resources=js("performance.getEntriesByType('resource').map(r=>r.name)")
            assert any('petchat-meadow-v1/mistwood-meadow.glb' in r for r in resources)
            assert not any('petchat-realistic-islands-v1' in r for r in resources),'unselected islands must not load'
            for x,z in [(10,8),(15.3,.6),(0,4.4)]:
                wait(f'window.__denMoveTo({x},{z})',15)
                wait(f'Math.hypot(window.__den.petModel.position.x-{x},window.__den.petModel.position.z-{z})<.1',60)
                assert js('window.__denLocomotionDebug().legal')
            out=ROOT/'art/cloud-meadow-v1/browser-overview.png'
            out.write_bytes(base64.b64decode(page.call('Page.captureScreenshot',{'format':'png'})['data']))
            performance_result=js("new Promise(resolve=>{let first=performance.now(),frames=0;function tick(){if(++frames===90){const c=document.getElementById('den-canvas'),gl=c.getContext('webgl2')||c.getContext('webgl'),e=gl.getExtension('WEBGL_debug_renderer_info');resolve({fps:Math.round(frames*1000/(performance.now()-first)),renderer:gl.getParameter(e.UNMASKED_RENDERER_WEBGL),lost:gl.isContextLost()});}else requestAnimationFrame(tick)}requestAnimationFrame(tick)})",True)
            assert not performance_result['lost']
            assert plan['Selected']['Name'].lower() in performance_result['renderer'].lower()
            # Full-page layout still parses and re-frames after a narrow-screen resize.
            page.call('Emulation.setDeviceMetricsOverride',{'width':420,'height':900,'deviceScaleFactor':1,'mobile':True})
            js("document.getElementById('btn-stage-view').click()")
            time.sleep(1)
            assert js('document.documentElement.scrollWidth<=innerWidth+1')
            page.call('Emulation.setDeviceMetricsOverride',{'width':1500,'height':1000,'deviceScaleFactor':1,'mobile':False})
            page.call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/'})
            wait("document.querySelectorAll('.island-world-label:not([hidden])').length===4")
            js("document.querySelector('.island-choice[data-theme=room]').click()")
            time.sleep(2)
            assert js("document.querySelector('.island-home').classList.contains('is-focused')")
            (ROOT/'art/cloud-meadow-v1/browser-home.png').write_bytes(base64.b64decode(page.call('Page.captureScreenshot',{'format':'png'})['data']))
            print(json.dumps({'passed':True,'journeys':'old island -> meadow -> woodland -> bridge','gpu':performance_result,'screenshot':str(out)},ensure_ascii=False))
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
