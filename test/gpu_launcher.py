"""Windows integration check: same launch flags, real Chrome + island WebGL.

Uses a temporary browser profile and closes only this test's Chrome instance.
Run with the local service on :5002. Requires websocket-client.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
import websocket

ROOT = Path(__file__).resolve().parents[1]


class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=20, suppress_origin=True)
        self.seq = 0

    def call(self, method, params=None):
        self.seq += 1
        self.ws.send(json.dumps(dict(id=self.seq, method=method, params=params or {})))
        while True:
            reply = json.loads(self.ws.recv())
            if reply.get('id') == self.seq:
                if 'error' in reply:
                    raise RuntimeError(reply['error'])
                return reply.get('result', {})

    def close(self):
        self.ws.close()


def main():
    assert os.name == 'nt', 'This test exercises Windows DXGI.'
    proc = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                           '-Command', "[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); & './scripts/start-island.ps1' -Inspect"],
                          cwd=ROOT, capture_output=True, encoding='utf-8', check=True)
    plan = json.loads(proc.stdout)
    adapter = plan['Selected']
    assert adapter['VideoMemory'] == max(a['VideoMemory'] for a in plan['Adapters'])
    assert '--use-adapter-luid=' + adapter['Luid'] in plan['Arguments']
    assert '--force_high_performance_gpu' in plan['Arguments']
    assert not any('--remote-debugging' in arg for arg in plan['Arguments'])
    # Do not open or modify the user's dedicated profile during the check.
    with tempfile.TemporaryDirectory(prefix='pait-gpu-check-') as profile:
        args = [arg for arg in plan['Arguments'] if not arg.startswith(('--user-data-dir=', 'http:'))]
        args += ['--user-data-dir=' + profile, '--remote-debugging-port=0', '--headless=new', 'about:blank']
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        chrome = subprocess.Popen([plan['Chrome'], *args], startupinfo=startup,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        browser = page = None
        try:
            port_file = Path(profile) / 'DevToolsActivePort'
            for _ in range(100):
                if port_file.exists() and len(port_file.read_text().splitlines()) >= 2:
                    break
                time.sleep(.2)
            port, endpoint = port_file.read_text().splitlines()[:2]
            browser = CDP('ws://127.0.0.1:' + port + endpoint)
            info = browser.call('SystemInfo.getInfo')['gpu']
            renderer = info['auxAttributes']['glRenderer']
            assert adapter['Name'].lower() in renderer.lower(), (adapter, renderer)
            with urllib.request.urlopen('http://127.0.0.1:' + port + '/json/list') as response:
                tabs = json.load(response)
            tab = next(t for t in tabs if t['type'] == 'page')
            page = CDP(tab['webSocketDebuggerUrl'])
            page.call('Page.navigate', {'url': 'http://127.0.0.1:5002/den?pet=1&scene=day'})
            expression = """(() => {
                const canvas=document.getElementById('den-canvas');
                if (!canvas || !window.__denAnimDebug) return null;
                document.getElementById('btn-render-settings')?.click();
                const actual=document.getElementById('render-device')?.textContent;
                const gl=canvas.getContext('webgl2') || canvas.getContext('webgl');
                const ext=gl?.getExtension('WEBGL_debug_renderer_info');
                return {actual, renderer:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):'',
                        lost:gl.isContextLost(), width:canvas.width, height:canvas.height,
                        preference:gl.getContextAttributes().powerPreference};
            })()"""
            result = None
            for _ in range(100):
                result = page.call('Runtime.evaluate', {'expression': expression, 'returnByValue': True}).get('result', {}).get('value')
                if result:
                    break
                time.sleep(.5)
            assert result and not result['lost'] and result['width'] > 0, result
            assert adapter['Name'].lower() in result['renderer'].lower(), result
            assert result['preference'] == 'high-performance', result
            print(json.dumps({'selected': adapter, 'chromeRenderer': renderer, 'island': result, 'passed': True}, ensure_ascii=False))
        finally:
            if page:
                page.close()
            if browser:
                try:
                    browser.call('Browser.close')
                except Exception:
                    pass
                browser.close()
            try:
                chrome.wait(timeout=15)
            except subprocess.TimeoutExpired:
                chrome.terminate()
                chrome.wait(timeout=10)
            time.sleep(1)


if __name__ == '__main__':
    main()
