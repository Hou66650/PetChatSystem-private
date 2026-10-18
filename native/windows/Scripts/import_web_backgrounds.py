"""Import unchanged Web images and composite them behind native scene geometry."""
import json
from pathlib import Path
import unreal as u

root=Path(u.Paths.project_dir()); folder='/Game/Preview/WebBackground'
a=u.EditorAssetLibrary; lib=u.MaterialEditingLibrary
textures={}
for name in ('Cloud','Mountain','Sakura','Snow'):
    task=u.AssetImportTask(); task.filename=str(root/'Saved/Art/WebBackground'/f'{name}.png')
    task.destination_path=folder; task.destination_name='T_'+name; task.automated=True; task.replace_existing=True; task.save=True
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture=a.load_asset(folder+'/T_'+name); assert texture
    texture.set_editor_property('srgb',True); texture.set_editor_property('never_stream',True)
    a.save_loaded_asset(texture); textures[name]=texture

path=folder+'/M_WebBackground'
material=a.load_asset(path) if a.does_asset_exist(path) else u.AssetToolsHelpers.get_asset_tools().create_asset('M_WebBackground',folder,u.Material,u.MaterialFactoryNew())
lib.delete_all_material_expressions(material)
material.set_editor_property('material_domain',u.MaterialDomain.MD_POST_PROCESS)
material.set_editor_property('blendable_location',u.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)
def node(kind,x,y): return lib.create_material_expression(material,kind,x,y)
uv=node(u.MaterialExpressionScreenPosition,-900,0)
cover=node(u.MaterialExpressionCustom,-650,0); cover.set_editor_property('output_type',u.CustomMaterialOutputType.CMOT_FLOAT2)
inp=u.CustomInput(); inp.set_editor_property('input_name','UV'); cover.set_editor_property('inputs',[inp])
cover.set_editor_property('code','float a = View.ViewSizeAndInvSize.x / View.ViewSizeAndInvSize.y; float ia = 1672.0 / 941.0; float2 scale = float2(min(1.0,a/ia),min(1.0,ia/a)); return (UV-.5)*scale+.5;')
assert lib.connect_material_expressions(uv,'ViewportUV',cover,'UV')
image=node(u.MaterialExpressionTextureSampleParameter2D,-400,0); image.set_editor_property('parameter_name','Background'); image.set_editor_property('texture',textures['Cloud'])
assert lib.connect_material_expressions(cover,'',image,'UVs')
display=node(u.MaterialExpressionCustom,-150,0); display.set_editor_property('output_type',u.CustomMaterialOutputType.CMOT_FLOAT3)
color=u.CustomInput(); color.set_editor_property('input_name','C'); display.set_editor_property('inputs',[color])
# Texture sampling decodes sRGB; the after-tonemapper scene input is display encoded.
# Encode only the image, leaving native scene color untouched.
display.set_editor_property('code','return lerp(12.92*C,1.055*pow(max(C,0.0),1.0/2.4)-0.055,step(0.0031308,C));')
assert lib.connect_material_expressions(image,'RGB',display,'C')
scene=node(u.MaterialExpressionSceneTexture,-400,250); scene.set_editor_property('scene_texture_id',u.SceneTextureId.PPI_POST_PROCESS_INPUT0)
scene_rgb=node(u.MaterialExpressionComponentMask,-200,250)
for channel in ('r','g','b'): scene_rgb.set_editor_property(channel,True)
scene_rgb.set_editor_property('a',False)
assert lib.connect_material_expressions(scene,'Color',scene_rgb,'')
depth=node(u.MaterialExpressionSceneDepth,-400,-250)
limit=node(u.MaterialExpressionConstant,-400,-400); limit.set_editor_property('r',50000.)
select=node(u.MaterialExpressionIf,0,0)
for source,output,pin in ((depth,'','A'),(limit,'','B'),(display,'','A > B'),(display,'','A == B'),(scene_rgb,'','A < B')):
    assert lib.connect_material_expressions(source,output,select,pin),pin
assert lib.connect_material_property(select,'',u.MaterialProperty.MP_EMISSIVE_COLOR)
lib.recompile_material(material); a.save_loaded_asset(material,False)
for name,texture in textures.items():
    path=folder+'/MI_'+name
    instance=a.load_asset(path) if a.does_asset_exist(path) else u.AssetToolsHelpers.get_asset_tools().create_asset('MI_'+name,folder,u.MaterialInstanceConstant,u.MaterialInstanceConstantFactoryNew())
    lib.set_material_instance_parent(instance,material)
    lib.set_material_instance_texture_parameter_value(instance,'Background',texture)
    lib.update_material_instance(instance); a.save_loaded_asset(instance,False)
(root/'Saved/Qualification/web-background-import.json').write_text(json.dumps({'images':list(textures),'material':material.get_path_name(),'cover_crop':True,'scene_depth_cutoff_cm':50000,'source_images_edited':False}),encoding='utf-8')
u.log('PAIT_WEB_BACKGROUNDS_IMPORTED')
