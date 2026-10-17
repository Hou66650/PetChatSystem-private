"""UE Editor: add native cloud sea below the isolated V2 preview island."""
import json
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if not levels.load_level('/Game/Preview/P1_MeadowV2'):
    raise RuntimeError('Import the complete P1 island first')
material = unreal.load_asset('/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst')
if not material:
    raise RuntimeError('Engine cloud material missing')
assets = unreal.EditorAssetLibrary
local_material = '/Game/Preview/Materials/MI_MeadowCloudSea'
material = (assets.load_asset(local_material) if assets.does_asset_exist(local_material)
            else assets.duplicate_asset(material.get_path_name(), local_material))
if not material:
    raise RuntimeError('Could not create isolated cloud material')
lib = unreal.MaterialEditingLibrary
lib.set_material_instance_scalar_parameter_value(material, 'Cloud_GlobalCoverage', .12)
lib.set_material_instance_scalar_parameter_value(material, 'Cloud_GlobalDensity', .012)
lib.set_material_instance_scalar_parameter_value(material, 'Layout_CloudGlobalScale', 32.0)
lib.update_material_instance(material)
assets.save_loaded_asset(material, only_if_is_dirty=False)
existing = [a for a in actors.get_all_level_actors() if a.get_actor_label() == 'P1 cloud sea']
if len(existing) > 1:
    raise RuntimeError('Unexpected duplicate cloud actors')
cloud = existing[0] if existing else actors.spawn_actor_from_class(unreal.VolumetricCloud, unreal.Vector())
cloud.set_actor_label('P1 cloud sea')
c = cloud.get_component_by_class(unreal.VolumetricCloudComponent)
c.set_editor_property('material', material)
# P0 atmosphere planet top is 2 km below the island. This layer occupies
# -1.2 km to -0.3 km, so the player looks down onto clouds instead of through fog.
c.set_editor_property('layer_bottom_altitude', .8)
c.set_editor_property('layer_height', .9)
if not levels.save_current_level():
    raise RuntimeError('Cloud sea map save failed')
(Path(unreal.Paths.project_dir()) / 'Saved/Qualification/meadow-clouds.json').write_text(
    json.dumps({'status':'saved_requires_runtime_review','layer_bottom_km':.8,'layer_height_km':.9,
                'coverage':.12,'density':.012,'global_scale':32.0,
                'material':material.get_path_name()},indent=2),encoding='utf-8')
