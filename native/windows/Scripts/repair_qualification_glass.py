"""Dedicated thin-pane material for P0 only; leave imported glTF material intact."""
import json
from pathlib import Path
import unreal

PATH = '/Game/Qualification/Materials/M_P0_ThinGlass'
assets = unreal.EditorAssetLibrary
library = unreal.MaterialEditingLibrary
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if not levels.load_level('/Game/Qualification/P0_Lighting'):
    raise RuntimeError('Missing isolated P0 map')
material = unreal.load_asset(PATH) if assets.does_asset_exist(PATH) else None
if material is None:
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        'M_P0_ThinGlass', '/Game/Qualification/Materials', unreal.Material,
        unreal.MaterialFactoryNew())
    if not material:
        raise RuntimeError('Material creation failed')
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_THIN_TRANSLUCENT)
    material.set_editor_property('translucency_lighting_mode', unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    material.set_editor_property('two_sided', True)
    # Flat thin panes: Fresnel highlights with tinted transmission, no screen-space
    # refraction displacement. This is a candidate, not final V2 asset acceptance.
    for value, prop, y in [(.045, unreal.MaterialProperty.MP_ROUGHNESS, 0),
                            (.5, unreal.MaterialProperty.MP_SPECULAR, 120),
                            (0., unreal.MaterialProperty.MP_OPACITY, 240)]:
        node = library.create_material_expression(material, unreal.MaterialExpressionConstant, -400, y)
        node.set_editor_property('r', value)
        if not library.connect_material_property(node, '', prop):
            raise RuntimeError('Material property connection failed: ' + str(prop))
    color = library.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, -400, 400)
    color.set_editor_property('constant', unreal.LinearColor(.96, .99, .97, 1))
    output = library.create_material_expression(material, unreal.MaterialExpressionThinTranslucentMaterialOutput, 0, 400)
    if not library.connect_material_expressions(color, '', output, 'TransmittanceColor'):
        raise RuntimeError('Thin transmission connection failed')
    library.recompile_material(material)
    if not assets.save_loaded_asset(material, only_if_is_dirty=False):
        raise RuntimeError('Material save failed')
if material.get_editor_property('shading_model') != unreal.MaterialShadingModel.MSM_THIN_TRANSLUCENT:
    raise RuntimeError('Unexpected existing material; refusing replacement')
changed = []
for actor in actors.get_all_level_actors():
    if not isinstance(actor, unreal.StaticMeshActor):
        continue
    component = actor.static_mesh_component
    mesh = component.static_mesh
    if mesh and mesh.get_name().startswith('Individual_glazing'):
        if not mesh.get_path_name().startswith('/Game/Imported/P0Architecture/'):
            raise RuntimeError('Unexpected glazing source')
        old = component.get_material(0)
        component.set_material(0, material)
        changed.append({'actor': actor.get_actor_label(), 'previous': old.get_path_name(),
                        'material': material.get_path_name()})
if len(changed) != 1 or not levels.save_current_level():
    raise RuntimeError('Expected one glazing component and saved P0 map')
(Path(unreal.Paths.project_dir()) / 'Saved/Qualification/thin-glass-repair.json').write_text(
    json.dumps({'status': 'saved_requires_cook_and_visual_review', 'changes': changed,
                'source_mesh_and_material_unchanged': True}, indent=2), encoding='utf-8')
