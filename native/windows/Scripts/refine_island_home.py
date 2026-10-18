"""Adjust home-only cloud frequency; preserve the four source island levels."""
import unreal
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assets=unreal.EditorAssetLibrary
assert levels.load_level('/Game/Preview/P2_IslandHome')
path='/Game/Preview/Materials/MI_HomeCloudSea'
material=assets.load_asset(path) if assets.does_asset_exist(path) else assets.duplicate_asset('/Game/Preview/Materials/MI_MeadowCloudSea',path)
assert material
for key,value in [('Cloud_GlobalCoverage',.42),('Cloud_GlobalDensity',.045),('Layout_CloudGlobalScale',.8)]:
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(material,key,value)
unreal.MaterialEditingLibrary.update_material_instance(material)
assets.save_loaded_asset(material,only_if_is_dirty=False)
for actor in actors.get_all_level_actors():
    if isinstance(actor,unreal.VolumetricCloud):
        c=actor.get_component_by_class(unreal.VolumetricCloudComponent)
        c.set_editor_property('material',material)
        c.set_editor_property('view_sample_count_scale',2.)
assert levels.save_current_level()
unreal.log('PAIT_HOME_CLOUD_REFINED')
