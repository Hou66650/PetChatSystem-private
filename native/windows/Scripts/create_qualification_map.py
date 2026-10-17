"""Run only inside Unreal Editor Python after compiling the editor module.
Not modeling work: these engine primitives are diagnostic fixtures, not island assets.
"""
import unreal

MAP = "/Game/Qualification/P0_Lighting"
assets = unreal.EditorAssetLibrary
if assets.does_asset_exist(MAP):
    raise RuntimeError("Map exists; refusing to overwrite authored work: " + MAP)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if not levels.new_level(MAP):
    raise RuntimeError("Could not create qualification level")

def spawn(kind, label, xyz, rotation=None):
    actor = actors.spawn_actor_from_class(kind, unreal.Vector(*xyz),
                                          rotation or unreal.Rotator())
    if actor is None:
        raise RuntimeError("Spawn failed: " + label)
    actor.set_actor_label(label)
    return actor

floor = spawn(unreal.StaticMeshActor, "P0 diagnostic floor (not final art)", (0, 0, -25))
mesh = unreal.load_asset("/Engine/BasicShapes/Cube")
if mesh is None:
    raise RuntimeError("Engine cube missing")
floor.static_mesh_component.set_static_mesh(mesh)
floor.set_actor_scale3d(unreal.Vector(60, 60, .5))
for index, xyz in enumerate([(-1400, 0, 100), (-1400, 300, 75), (-1400, -300, 150)]):
    fixture = spawn(unreal.StaticMeshActor, "P0 shadow fixture " + str(index), xyz)
    fixture.static_mesh_component.set_static_mesh(mesh)
    fixture.set_actor_scale3d(unreal.Vector(1.5, 1.5, (xyz[2] * 2) / 100))
sun = spawn(unreal.DirectionalLight, "P0 movable sunlight", (0, 0, 1500),
            unreal.Rotator(-35, -35, 0))
sun.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
sun.light_component.set_editor_property("intensity", 50000.0)
sun.light_component.set_editor_property("atmosphere_sun_light", True)
sky = spawn(unreal.SkyLight, "P0 sky capture", (0, 0, 1000))
sky.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
sky.light_component.set_editor_property("real_time_capture", True)
spawn(unreal.SkyAtmosphere, "P0 sky atmosphere", (0, 0, 0))
# Fixed EV100 avoids the legacy narrow auto-exposure range clipping a lux-based sun.
post = spawn(unreal.PostProcessVolume, "P0 fixed daylight exposure", (0, 0, 0))
post.set_editor_property("unbound", True)
settings = post.get_editor_property("settings")
settings.set_editor_property("override_auto_exposure_min_brightness", True)
settings.set_editor_property("override_auto_exposure_max_brightness", True)
settings.set_editor_property("override_auto_exposure_bias", True)
settings.set_editor_property("auto_exposure_min_brightness", 13.0)
settings.set_editor_property("auto_exposure_max_brightness", 13.0)
settings.set_editor_property("auto_exposure_bias", 0.0)
post.set_editor_property("settings", settings)
spawn(unreal.PlayerStart, "P0 orbit pivot", (0, 0, 150))
if not levels.save_current_level():
    raise RuntimeError("Map save failed")
unreal.log("PAIT_P0_MAP_SAVED " + MAP)
