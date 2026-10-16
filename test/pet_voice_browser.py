"""Real Chrome upload/preview/apply workflow against a disposable app and fake voice provider."""
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
        chrome=subprocess.Popen([plan['Chrome'],'--headless=new','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--use-angle=d3d11','--use-adapter-luid='+plan['Selected']['Luid'],'--user-data-dir='+tmp,'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
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
            url=f'http://127.0.0.1:{server.server_port}/gpt'
            page.call('Network.setCookie',{'name':'session','value':fixture.a.get_cookie('session').value,'url':url})
            page.call('Page.navigate',{'url':url})
            wait('!!window.PetProfile');js("PetProfile.openDialog({petId:1,petName:'球球'});[...document.querySelectorAll('#pet-profile-dialog button')].find(b=>b.textContent.includes('专属声音')).click()")
            wait("document.querySelector('#pet-voice-dialog[open] [data-hint]')?.textContent.includes('智谱')")
            js("document.querySelector('[data-name]').value='清新的测试声音';document.querySelector('[data-consent]').click()")
            sample=Path(tmp)/'reference.wav';sample.write_bytes(fixture.audio)
            root=page.call('DOM.getDocument')['root']['nodeId'];node=page.call('DOM.querySelector',{'nodeId':root,'selector':'#pet-voice-dialog [data-file]'})['nodeId']
            page.call('DOM.setFileInputFiles',{'nodeId':node,'files':[str(sample)]})
            wait("!document.querySelector('[data-create]').disabled")
            assert js("document.querySelector('[data-source]').duration>=3")
            js("document.querySelector('[data-create]').click()")
            wait("[...document.querySelectorAll('[data-list] button')].some(b=>b.textContent==='试听新声音')")
            assert js("document.querySelector('[data-current]').textContent.includes('默认')")
            js("[...document.querySelectorAll('[data-list] button')].find(b=>b.textContent==='试听新声音').click()")
            wait("document.querySelector('[data-preview]').src.startsWith('blob:')")
            js("[...document.querySelectorAll('[data-list] button')].find(b=>b.textContent==='应用给球球').click()")
            wait("document.querySelector('[data-current]').textContent.includes('专属音色')")
            assert js("document.querySelector('[data-list]').textContent.includes('当前使用')")
            js("document.querySelector('[data-close]').click();PetVoiceUI.open(2,'雪球')")
            wait("document.querySelector('[data-list]').textContent.includes('还没有')")
            assert js("document.querySelector('[data-current]').textContent.includes('默认')")
            js("document.querySelector('[data-close]').click();PetVoiceUI.open(1,'球球')")
            wait("document.querySelector('[data-current]').textContent.includes('专属音色')")
            page.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            time.sleep(.3)
            assert js("document.querySelector('#pet-voice-dialog').scrollWidth<=document.querySelector('#pet-voice-dialog').clientWidth+1")
            image=page.call('Page.captureScreenshot',{'format':'png'})['data'];out=Path(os.environ['TEMP'])/'pait-pet-voice-ui.png';out.write_bytes(base64.b64decode(image))
            js("document.querySelector('[data-reset]').click()")
            wait("document.querySelector('[data-current]').textContent.includes('默认')")
            js("[...document.querySelectorAll('[data-list] button')].find(b=>b.textContent==='删除').click()")
            wait("document.querySelector('[data-list]').textContent.includes('还没有')")
            print(json.dumps({'passed':True,'checks':['real WAV decode/upload','original preview','cloud preview playback URL','explicit apply','per-pet isolation','reopen persistence','mobile width','restore default','delete'],'screenshot':str(out)},ensure_ascii=False))
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
