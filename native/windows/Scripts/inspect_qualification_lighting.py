"""Read the isolated P0 light and glass settings without changing assets."""
import json
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if not levels.load_level('/Game/Qualification/P0_Lighting'):
    raise RuntimeError('Missing isolated fixture')
records = []
for a in actors.get_all_level_actors():
    label = a.get_actor_label()
    if isinstance(a, (unreal.DirectionalLight, unreal.SkyLight, unreal.SkyAtmosphere)):
        component = a.get_component_by_class(unreal.SkyAtmosphereComponent) if isinstance(a, unreal.SkyAtmosphere) else a.light_component
        fields = ('intensity', 'real_time_capture', 'lower_hemisphere_is_black', 'light_source_angle', 'atmosphere_sun_light', 'ground_radius', 'transform_mode')
        values = {}
        for field in fields:
            try: values[field] = str(component.get_editor_property(field))
            except Exception: pass
        position, rotation = a.get_actor_location(), a.get_actor_rotation()
        records.append({'actor':label, 'location':[position.x,position.y,position.z], 'rotation':{'pitch':rotation.pitch,'yaw':rotation.yaw,'roll':rotation.roll}, 'settings':values})
    if isinstance(a, unreal.StaticMeshActor):
        c = a.static_mesh_component
        if c.static_mesh and c.static_mesh.get_name().startswith('Individual_glazing'):
            materials=[]
            for i in range(c.get_num_materials()):
                m=c.get_material(i)
                r={'path':m.get_path_name()}
                if isinstance(m,unreal.Material):
                    r['shading_model']=str(m.get_editor_property('shading_model'))
                    r['blend_mode']=str(m.get_editor_property('blend_mode'))
                    r['lighting_mode']=str(m.get_editor_property('translucency_lighting_mode'))
                if isinstance(m,unreal.MaterialInstanceConstant):
                    r['parent']=m.get_editor_property('parent').get_path_name()
                    r['scalars']={str(n):unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(m,n) for n in unreal.MaterialEditingLibrary.get_scalar_parameter_names(m)}
                materials.append(r)
            origin,extent=a.get_actor_bounds(False)
            records.append({'actor':label,'mesh':c.static_mesh.get_path_name(),'bounds':{'origin':[origin.x,origin.y,origin.z],'extent':[extent.x,extent.y,extent.z]},'materials':materials})
out=Path(unreal.Paths.project_dir())/'Saved/Qualification/lighting-inspection.json'
out.write_text(json.dumps(records,indent=2),encoding='utf-8')
