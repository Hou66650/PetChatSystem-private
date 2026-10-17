using UnrealBuildTool;

public class PaitIsland : ModuleRules
{
    public PaitIsland(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[] {
            "Core", "CoreUObject", "Engine", "InputCore"
        });
        PrivateDependencyModuleNames.AddRange(new string[] { "RHI", "Json", "NavigationSystem", "HTTP", "Slate", "SlateCore", "AudioCaptureCore", "AudioMixer" });
    }
}
