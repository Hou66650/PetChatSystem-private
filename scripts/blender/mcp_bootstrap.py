"""Start the user-requested Blender addon in this isolated authoring session only."""
import importlib.util, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('petchat_blender_mcp',ROOT/'uploads/blender-mcp/addon.py')
addon=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=addon
spec.loader.exec_module(addon)
addon.register()
import bpy
bpy.context.scene.blendermcp_auto_start_server=False
bpy.types.blendermcp_server=addon.BlenderMCPServer(host='127.0.0.1',port=9876)
bpy.types.blendermcp_server.start()
print('PetChat Blender authoring bridge ready on loopback:9876',flush=True)
