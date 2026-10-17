"""Keep the official addon's main-thread queue alive in headless Blender.

Used only for this isolated art session. Stop this process after authoring.
"""
import builtins,runpy,time,traceback,socket,threading
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('mcp_bootstrap.py')))
import bpy
server=bpy.types.blendermcp_server
# The upstream start() rejects background mode because bpy timers do not run.
# This adapter supplies that missing main-thread pump explicitly, retaining the
# upstream listener, protocol, command handlers, and stop lifecycle.
if not server.running:
    server.socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    server.socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    server.socket.bind(('127.0.0.1',9876));server.socket.listen(5)
    server.running=True
    server.server_thread=threading.Thread(target=server._server_loop,daemon=True)
    server.server_thread.start()
    print('Paw headless MCP main-thread adapter ready',flush=True)
builtins._paw_jobs=[]
try:
    while server.running:
        server._drain_command_queue()
        if builtins._paw_jobs:
            job=builtins._paw_jobs.pop(0)
            try:job()
            except Exception:traceback.print_exc()
        time.sleep(.05)
finally:server.stop()
