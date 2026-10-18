#include "PaitDaylight.h"
#include "EngineUtils.h"
#include "Engine/PostProcessVolume.h"
#include "Components/VolumetricCloudComponent.h"
#include "Materials/MaterialInterface.h"

void ApplyPaitDaylight(UWorld* World)
{
    if (!World) return;
    const FString Map = World->GetMapName();
    if (!(Map.StartsWith(TEXT("P1_")) || Map.StartsWith(TEXT("P2_")))) return;
    const TCHAR* Theme = Map.Contains(TEXT("Sakura")) ? TEXT("Sakura") :
        Map.Contains(TEXT("Snow")) ? TEXT("Snow") :
        (Map.Contains(TEXT("Meadow")) || Map.Contains(TEXT("Camp"))) ? TEXT("Mountain") : TEXT("Cloud");
    const FString Asset = FString::Printf(TEXT("/Game/Preview/WebBackground/MI_%s.MI_%s"), Theme, Theme);
    UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr, *Asset);
    if (!Material) { UE_LOG(LogTemp, Error, TEXT("Web background missing: %s"), *Asset); return; }
    auto* Background = World->SpawnActor<APostProcessVolume>();
    Background->bUnbound = true;
    Background->Priority = 100.f;
    Background->AddOrUpdateBlendable(Material, 1.f);
    // Keep authored sunlight and sky capture; replace only pixels behind the 3D scene.
    for (TActorIterator<AVolumetricCloud> It(World); It; ++It)
        if (auto* Cloud = It->FindComponentByClass<UVolumetricCloudComponent>())
            Cloud->SetVisibility(false);
}
