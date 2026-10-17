"""P0 daylight and thin-glass candidate; preserve imported source materials."""
import json
from pathlib import Path
import unreal

levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assets=unreal.EditorAssetLibrary
if not levels.load_level('/Game/Qualification/P0_Lighting'):
    raise RuntimeError('P0 fixture missing')
glass_path='/Game/Qualification/Materials/MI_P0_ClearGlass'
changes=[]
for actor in actors.get_all_level_actors():
    label=actor.get_actor_label()
    if label=='P0 movable sunlight':
        actor.set_actor_rotation(unreal.Rotator(pitch=-35,yaw=-35,roll=0),False)
        actor.light_component.set_editor_property('light_source_angle',1.5)
        changes.append({'sun_lux':50000,'source_angle':1.5,'rotation':{'pitch':-35,'yaw':-35,'roll':0}})
    elif label=='P0 sky capture':
        actor.light_component.set_editor_property('lower_hemisphere_is_black',False)
        actor.light_component.set_editor_property('intensity',1.5)
        changes.append({'skylight_intensity':1.5,'lower_hemisphere_is_black':False})
    elif label=='P0 sky atmosphere':
        c=actor.get_component_by_class(unreal.SkyAtmosphereComponent)
        c.set_editor_property('transform_mode',unreal.SkyAtmosphereTransformMode.PLANET_TOP_AT_COMPONENT_TRANSFORM)
        actor.set_actor_location(unreal.Vector(0,0,-200000),False,False)
        changes.append({'atmosphere_planet_top_z_cm':-200000})
    elif isinstance(actor,unreal.StaticMeshActor):
        c=actor.static_mesh_component
        if c.static_mesh and c.static_mesh.get_name().startswith('Individual_glazing'):
            if not c.static_mesh.get_path_name().startswith('/Game/Imported/P0Architecture/'):
                raise RuntimeError('Unexpected glazing fixture')
            old=c.get_material(0)
            if not old.get_path_name().startswith(('/Game/Imported/P0Architecture/','/Game/Qualification/Materials/MI_P0_ClearGlass.','/Game/Qualification/Materials/M_P0_ThinGlass.')):
                raise RuntimeError('Unexpected glass material')
            material=unreal.load_asset(glass_path) if assets.does_asset_exist(glass_path) else assets.duplicate_asset(old.get_path_name(),glass_path)
            if not isinstance(material,unreal.MaterialInstanceConstant):
                raise RuntimeError('Expected glass instance')
            # UE 5.8's setter returns false even after assigning; verify the readback.
            unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(material,'RefractionDepth',0.4)
            if abs(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(material,'RefractionDepth')-0.4)>1e-5:
                raise RuntimeError('Glass refraction assignment failed')
            unreal.MaterialEditingLibrary.update_material_instance(material)
            assets.save_loaded_asset(material,only_if_is_dirty=False)
            c.set_material(0,material)
            changes.append({'glass_material':material.get_path_name(),'refraction_depth':0.4,'source_material_preserved':old.get_path_name()})
if len(changes)!=4 or not levels.save_current_level():
    raise RuntimeError('Expected four fixture adjustments and saved map')
out=Path(unreal.Paths.project_dir())/'Saved/Qualification/lighting-repair.json'
out.write_text(json.dumps({'status':'candidate_saved_requires_runtime_review','changes':changes},indent=2),encoding='utf-8')
