"""Small local transport for the ahujasid Blender addon JSON command protocol."""
import argparse,json,socket
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('script',nargs='?');args=p.parse_args()
command={'type':'get_scene_info','params':{}}
if args.script:
    path=Path(args.script).resolve()
    command={'type':'execute_code','params':{'code':f'exec(compile(open({str(path)!r}, encoding="utf-8").read(), {str(path)!r}, "exec"), {{"__file__":{str(path)!r}, "__name__":"__main__"}})'}}
with socket.create_connection(('127.0.0.1',9876),timeout=10) as conn:
    conn.settimeout(900);conn.sendall(json.dumps(command).encode());data=b''
    while True:
        chunk=conn.recv(65536)
        if not chunk:raise RuntimeError('Blender disconnected before a complete response')
        data+=chunk
        try:result=json.loads(data);break
        except (json.JSONDecodeError,UnicodeDecodeError):pass
print(json.dumps(result,ensure_ascii=False))
if result.get('status')=='error':raise SystemExit(1)
