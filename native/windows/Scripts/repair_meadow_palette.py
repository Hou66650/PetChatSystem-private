"""Restore V2 base palette that procedural Blender node graphs omit from glTF."""
import json
import re
from pathlib import Path
import unreal

project = Path(unreal.Paths.project_dir())
source = json.loads((project/'Qualification/meadow-v2-palette.json').read_text(encoding='utf-8'))
palette = {re.sub(r'[^A-Za-z0-9_]', '_', m['name']): m['base_color']
           for m in source['materials'] if m['name'].startswith('V2 ') and m['color_linked'] and m['base_color']}
assets = unreal.EditorAssetLibrary
lib = unreal.MaterialEditingLibrary
records=[]
for path in assets.list_assets('/Game/Imported/P1MeadowV2_Conventional', recursive=True):
    name=path.split('.')[-1]
    if name not in palette:
        continue
    m=assets.load_asset(path)
    if isinstance(m, unreal.Material):
        nodes = lib.get_material_expressions(m)
        node = next((n for n in nodes if isinstance(n, unreal.MaterialExpressionConstant3Vector)
                     and n.get_editor_property('desc') == 'V2 frozen base palette'), None)
        if node is None:
            node = lib.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -500, -300)
            node.set_editor_property('desc', 'V2 frozen base palette')
        node.set_editor_property('constant', unreal.LinearColor(*palette[name]))
        lib.connect_material_property(node, '', unreal.MaterialProperty.MP_BASE_COLOR)
        lib.recompile_material(m)
        key = 'BaseColor'
    elif isinstance(m,unreal.MaterialInstanceConstant):
        parameters=[str(n) for n in lib.get_vector_parameter_names(m)]
        key=next((n for n in ('BaseColorFactor','BaseColor') if n in parameters),None)
        if key is None:
            raise RuntimeError('Unknown palette parameter: '+path+' '+repr(parameters))
        lib.set_material_instance_vector_parameter_value(m,key,unreal.LinearColor(*palette[name]))
        lib.update_material_instance(m)
    else:
        continue
    if not assets.save_loaded_asset(m,only_if_is_dirty=False):
        raise RuntimeError('Palette material not saved')
    records.append({'path':path,'parameter':key,'linear_rgba':palette[name]})
if len(records)<5:
    raise RuntimeError('Expected V2 wood/roof/enamel material replacements')
(project/'Saved/Qualification/meadow-palette-repair.json').write_text(json.dumps({'status':'saved_requires_runtime_review','materials':records},indent=2),encoding='utf-8')
