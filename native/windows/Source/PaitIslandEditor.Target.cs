using UnrealBuildTool;
using System.Collections.Generic;

public class PaitIslandEditorTarget : TargetRules
{
    public PaitIslandEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("PaitIsland");
    }
}
