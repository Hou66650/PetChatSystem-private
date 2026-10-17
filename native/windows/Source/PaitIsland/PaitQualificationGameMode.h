#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "PaitQualificationGameMode.generated.h"

UCLASS()
class PAITISLAND_API APaitQualificationHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
};
UCLASS()
class PAITISLAND_API APaitQualificationGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    APaitQualificationGameMode();
    virtual void BeginPlay() override;
};
