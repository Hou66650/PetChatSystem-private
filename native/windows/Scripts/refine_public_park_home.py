"""One-time orientation migration for an existing pre-release five-island home."""
import unreal
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert levels.load_level('/Game/Preview/P2_IslandHome')
items=actors.get_all_level_actors()
park=[a for a in items if 'HomePark' in [str(t) for t in a.tags]]
assert park
# Only the pre-release layout has negative park Y. Fresh imports already match Web.
if park[0].get_actor_location().y < 0:
    for actor in items:
        tags=[str(t) for t in actor.tags]
        if 'HomePark' in tags:delta=3800
        elif 'HomeSnow' in tags or 'HomeMeadow' in tags:delta=-4600
        else:continue
        actor.set_actor_location(actor.get_actor_location()+unreal.Vector(0,delta,0),False,False)
assert levels.save_current_level()
unreal.log('PAIT_HOME_WEB_ORIENTATION_SAVED')
