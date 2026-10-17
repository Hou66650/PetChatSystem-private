"""Restore GLB vertex-colored coat fibres in the isolated P0 cat only.

The public GLB supplies COLOR_0 on Reference_fur, with no base-color texture.
Keep the source and imported material untouched; bind a dedicated runtime material.
"""
import json
import hashlib
from pathlib import Path
import unreal

MESH = "/Game/Imported/P0Cat/cat/SkeletalMeshes/Reference_fur"
MATERIAL = "/Game/Qualification/Materials/M_P0_CatFurVertexColor"
source = Path(unreal.Paths.project_dir()).resolve().parents[1] / "static/models/petchat-cat-v3/cat.glb"
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
if source_hash != "dca73dc58ffd5e3aa4b52a86eeefeebd6621d30a3e695fe540d5892250e901db":
    raise RuntimeError("Standard-cat source changed; review material assumptions first")
mesh = unreal.load_asset(MESH)
if not isinstance(mesh, unreal.SkeletalMesh):
    raise RuntimeError("Expected isolated standard-cat fur skeletal mesh")
slots = mesh.get_editor_property("materials")
if len(slots) != 1:
    raise RuntimeError("Unexpected fur material slots; refusing broad replacement")
previous = slots[0].get_editor_property("material_interface")
if previous is None:
    raise RuntimeError("Original material is missing")
if not (previous.get_path_name().startswith("/Game/Imported/P0Cat/") or previous.get_path_name() == MATERIAL + ".M_P0_CatFurVertexColor"):
    raise RuntimeError("Unexpected material source")

library = unreal.MaterialEditingLibrary
original_parameters = {}
if isinstance(previous, unreal.MaterialInstanceConstant):
    for name in library.get_scalar_parameter_names(previous):
        original_parameters[str(name)] = library.get_material_instance_scalar_parameter_value(previous, name)
material = unreal.load_asset(MATERIAL) if unreal.EditorAssetLibrary.does_asset_exist(MATERIAL) else None
if material is not None:
    base = library.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
    if not isinstance(base, unreal.MaterialExpressionVertexColor):
        raise RuntimeError("Existing repair material has unexpected graph; refusing to overwrite")
else:
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_P0_CatFurVertexColor", "/Game/Qualification/Materials", unreal.Material, unreal.MaterialFactoryNew())
    if material is None:
        raise RuntimeError("Could not create isolated coat material")
    material.set_editor_property("two_sided", True)
    material.set_editor_property("used_with_skeletal_mesh", True)
    color = library.create_material_expression(material, unreal.MaterialExpressionVertexColor, -400, 0)
    roughness = library.create_material_expression(material, unreal.MaterialExpressionConstant, -400, 160)
    roughness.set_editor_property("r", 0.93)
    specular = library.create_material_expression(material, unreal.MaterialExpressionConstant, -400, 280)
    specular.set_editor_property("r", 0.25)
    for node, output, property_name in [
        (color, "", unreal.MaterialProperty.MP_BASE_COLOR),
        (roughness, "", unreal.MaterialProperty.MP_ROUGHNESS),
        (specular, "", unreal.MaterialProperty.MP_SPECULAR),
    ]:
        if not library.connect_material_property(node, output, property_name):
            raise RuntimeError("Could not connect coat material property: " + str(property_name))
    library.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False):
        raise RuntimeError("Material save failed")
# Unreal Array indexing returns a struct value; write the changed value back.
slot = slots[0]
slot.set_editor_property("material_interface", material)
slots[0] = slot
mesh.set_editor_property("materials", slots)
if mesh.get_editor_property("materials")[0].get_editor_property("material_interface") != material:
    raise RuntimeError("Fur material assignment did not reach mesh")
if not unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False):
    raise RuntimeError("Mesh material assignment save failed")
report = {
    "status": "saved_requires_cook_and_visual_review",
    "mesh": MESH,
    "previous_material": previous.get_path_name(),
    "previous_scalar_parameters": original_parameters,
    "replacement_material": MATERIAL,
    "base_color": "GLB COLOR_0 vertex RGB",
    "roughness": 0.93,
    "specular": 0.25,
    "source_glb_modified": False,
    "source_sha256": source_hash,
}
out = Path(unreal.Paths.project_dir()) / "Saved/Qualification/fur-material-repair.json"
out.write_text(json.dumps(report, indent=2), encoding="utf-8")
