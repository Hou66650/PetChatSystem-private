"""Send this project's authoring code through the real MCP stdio server.

Run with: uvx --from mcp-for-blender python scripts/blender/paw_mcp_client.py SCRIPT
The Blender addon must already listen on loopback:9876 in an isolated instance.
"""
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    env = dict(os.environ, DISABLE_TELEMETRY='true', BLENDER_HOST='127.0.0.1', BLENDER_PORT='9876')
    server = StdioServerParameters(command=shutil.which('mcp-for-blender'), env=env)
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            if len(sys.argv) > 1:
                path = Path(sys.argv[1]).resolve()
                # A timer lets long builds finish without the MCP command timing out.
                code = ('import bpy, builtins\n'
                        'def paw_build_job():\n'
                        f'    exec(compile(open({str(path)!r}, encoding="utf-8").read(), {str(path)!r}, "exec"), '
                        f'{{"__file__": {str(path)!r}, "__name__": "__main__"}})\n'
                        '    return None\n'
                        'if bpy.app.background and hasattr(builtins, "_paw_jobs"):\n'
                        '    builtins._paw_jobs.append(paw_build_job)\n'
                        'else:\n'
                        '    bpy.app.timers.register(paw_build_job, first_interval=1.0)\n'
                        'print("Paw detailed build scheduled through MCP")')
                result = await session.call_tool('execute_blender_code', {'code': code, 'user_prompt': 'Build detailed Paw Commons from approved project concept references.'})
            else:
                result = await session.call_tool('get_scene_info', {})
            print(json.dumps(result.model_dump(), ensure_ascii=False))
            if result.isError or any(getattr(c, 'text', '').startswith('Error') for c in result.content):
                raise RuntimeError('Blender MCP returned an error')


if __name__ == '__main__':
    asyncio.run(main())
