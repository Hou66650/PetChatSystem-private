import json
from pathlib import Path
import unreal

assets = unreal.EditorAssetLibrary
lib = unreal.MaterialEditingLibrary
records = []
paths = list(assets.list_assets('/Game/Imported/P1MeadowV2_Conventional', recursive=True))
paths += ['/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst']
for path in paths:
    if not any(n in path for n in ['V2_forest_green_roof', 'V2_aged_oak_longitudinal_grain', 'V2_aged_conservatory_enamel', 'm_SimpleVolumetricCloud_Inst']):
        continue
    m = assets.load_asset(path)
    if not isinstance(m, unreal.MaterialInstanceConstant):
        records.append({'path':path, 'class':m.get_class().get_name() if m else None})
        continue
    records.append({'path':m.get_path_name(), 'parent':m.parent.get_path_name(),
                    'scalars':{str(n):lib.get_material_instance_scalar_parameter_value(m,n) for n in lib.get_scalar_parameter_names(m)},
                    'vectors':{str(n):str(lib.get_material_instance_vector_parameter_value(m,n)) for n in lib.get_vector_parameter_names(m)}})
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Preview/P1_MeadowV2')
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if isinstance(a, (unreal.SkyAtmosphere, unreal.VolumetricCloud)):
        p=a.get_actor_location()
        records.append({'actor':a.get_actor_label(),'location':[p.x,p.y,p.z]})
(Path(unreal.Paths.project_dir())/'Saved/Qualification/meadow-material-inspection.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
