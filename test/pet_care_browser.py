"""Chrome care settings, real MP4 audio extraction and island comfort integration."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import urllib.request
from unittest.mock import patch
from werkzeug.serving import make_server, WSGIRequestHandler
from test_pet_voice import PetVoiceTests
from gpu_launcher import CDP, ROOT
from app.services import pet_voice_service as voice


class Quiet(WSGIRequestHandler):
    def log(self, *args, **kwargs):pass


fixture=PetVoiceTests();fixture.setUp()

server=make_server('127.0.0.1',0,fixture.app,threaded=True,request_handler=Quiet)
threading.Thread(target=server.serve_forever,daemon=True).start()
browser=page=None
try:
    with patch.object(voice,'provider',side_effect=fixture.provider), tempfile.TemporaryDirectory(prefix='pait-voice-ui-') as tmp:
        plan=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/start-island.ps1'),'-Inspect'],text=True,encoding='utf-8'))
        mic_sample=Path(tmp)/'microphone.wav';mic_sample.write_bytes(fixture.audio)
        chrome=subprocess.Popen([plan['Chrome'],'--headless=new','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--use-file-for-fake-audio-capture='+str(mic_sample),'--autoplay-policy=no-user-gesture-required','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--use-angle=d3d11','--use-adapter-luid='+plan['Selected']['Luid'],'--user-data-dir='+tmp,'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            port_file=Path(tmp)/'DevToolsActivePort'
            for _ in range(100):
                if port_file.exists():break
                time.sleep(.1)
            port,endpoint=port_file.read_text().splitlines()[:2];browser=CDP('ws://127.0.0.1:'+port+endpoint)
            with urllib.request.urlopen('http://127.0.0.1:'+port+'/json/list') as response:tabs=json.load(response)
            page=CDP(next(t for t in tabs if t['type']=='page')['webSocketDebuggerUrl'])
            def js(code):
                result=page.call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
                if result.get('exceptionDetails'):raise AssertionError(result['exceptionDetails'])
                return result.get('result',{}).get('value')
            def wait(code):
                for _ in range(100):
                    result=js(code)
                    if result:return result
                    time.sleep(.15)
                raise AssertionError('Timed out: '+code)
            from test_pet_care import audio_sample
            import imageio_ffmpeg
            sample=Path(tmp)/'original.wav';sample.write_bytes(audio_sample())
            video=Path(tmp)/'pet.mp4'
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-nostdin','-loglevel','error','-f','lavfi','-i','color=c=green:s=64x64:r=10','-i',str(sample),'-t','3','-c:v','libx264','-c:a','aac','-y',str(video)],check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            url=f'http://127.0.0.1:{server.server_port}/gpt'
            page.call('Network.setCookie',{'name':'session','value':fixture.a.get_cookie('session').value,'url':url})
            page.call('Page.navigate',{'url':url})
            wait('!!window.PetProfile')
            js("PetProfile.openDialog({petId:3,petName:'团子'});[...document.querySelectorAll('#pet-profile-dialog button')].find(b=>b.textContent.includes('主动关怀')).click()")
            wait("document.querySelector('.pet-care-dialog[open] [data-status]')?.textContent.includes('计划需要')")
            js("document.querySelector('[data-title]').value='测试面试';const utc8=t=>new Date(t+8*3600000).toISOString().slice(0,16);document.querySelector('[data-event-time]').value=utc8(Date.now()+7200000);document.querySelector('[data-remind-time]').value=utc8(Date.now()+3600000);document.querySelector('[data-event-form]').requestSubmit()")
            wait("document.querySelector('[data-events]').textContent.includes('等待提醒')&&!document.querySelector('[data-save-settings]').disabled")
            js("document.querySelector('[data-tab-calls]').click()")
            root=page.call('DOM.getDocument')['root']['nodeId'];node=page.call('DOM.querySelector',{'nodeId':root,'selector':'.pet-care-dialog [data-media]'})['nodeId']
            page.call('DOM.setFileInputFiles',{'nodeId':node,'files':[str(video)]})
            js("document.querySelector('[data-consent]').click();document.querySelector('[data-extract]').click()")
            wait("!document.querySelector('[data-editor]').hidden&&!document.querySelector('[data-save-clip]').disabled")
            assert js("document.querySelector('[data-source-player]').src.startsWith('blob:')&&document.querySelector('[data-candidates]').children.length>0")
            js("document.querySelector('[data-start]').value='0.25';document.querySelector('[data-end]').value='1.75';document.querySelector('[data-confirmed]').click();document.querySelector('[data-clip-name]').value='熟悉的一声';document.querySelector('[data-save-clip]').click()")
            wait("document.querySelector('[data-clips]').textContent.includes('熟悉的一声')&&!document.querySelector('[data-save-clip]').disabled")
            js("document.querySelector('[data-call-enabled]').click();document.querySelector('[data-save-call-settings]').click()")
            wait("!document.querySelector('[data-save-call-settings]').disabled")
            js("document.querySelector('[data-close]').click();PetCareUI.open(1,'球球')")
            wait("document.querySelector('[data-status]').textContent.includes('计划需要')")
            assert js("!document.querySelector('[data-events]').textContent.includes('测试面试')&&!document.querySelector('[data-clips]').textContent.includes('熟悉的一声')")
            js("document.querySelector('[data-close]').click();PetCareUI.open(3,'团子')")
            wait("document.querySelector('[data-clips]').textContent.includes('熟悉的一声')")
            assert js("document.querySelector('[data-call-enabled]').checked")
            page.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            time.sleep(.25)
            assert js("document.querySelector('.pet-care-dialog').scrollWidth<=document.querySelector('.pet-care-dialog').clientWidth+1")
            out=Path(os.environ['TEMP'])/'pait-pet-care-ui.png';out.write_bytes(base64.b64decode(page.call('Page.captureScreenshot',{'format':'png'})['data']))
            page.call('Emulation.clearDeviceMetricsOverride')
            page.call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/den?pet=3'})
            wait('!!window.__denLocomotionDebug?.()')
            result=js("typeof window.__denCareDebug==='function'&&!!document.getElementById('btn-pet-care')")
            assert result,'island integration must initialize'
            # Exercise the actual navigation/action adapter, without cloud inference.
            wait('window.__denCareDebug().ready&&window.__denCareDebug().available')
            js("document.getElementById('btn-chat').click();document.getElementById('chat-input').value='我今天有点难过';document.getElementById('chat-form').requestSubmit()")
            wait('window.__denCareDebug().comfort')
            assert js("window.__denDialogue.debug().active||window.__denDialogue.debug().held")
            js("document.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));")
            assert js('!window.__denCareDebug().comfort&&!window.__denDialogue.debug().active'),'manual input must cancel comfort'
            headers={'X-Profile-Scope':fixture.a.get('/api/pet-care?petId=3').json['scope']}
            fixture.a.patch('/api/pet-care?petId=3',headers=headers,json={'quiet_start':0,'quiet_end':0})
            due=fixture.a.post('/api/pet-care/events?petId=3',headers=headers,json={'title':'即将开始的面试','event_at':time.time()+600,'remind_at':time.time()})
            assert due.status_code==200,due.json
            wait("document.querySelector('.pet-care-nudge')?.textContent.includes('即将开始的面试')")
            assert fixture.a.post('/api/pet-care/claim?petId=3',headers=headers,json={}).json['notice'] is None
            print(json.dumps({'passed':True,'checks':['confirmed timed event','real MP4 extraction and clip save','original sound switch persistence','pet isolation','mobile layout','real island adapter initialization','safe comfort navigation starts','manual interaction cancels comfort','due reminder appears once'],'screenshot':str(out)},ensure_ascii=False))
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
