#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "PaitPreviewPawn.generated.h"

class USpringArmComponent;
class UCameraComponent;

UCLASS()
class PAITISLAND_API APaitPreviewPawn : public APawn
{
    GENERATED_BODY()
public:
    APaitPreviewPawn();
    virtual void BeginPlay() override;
    virtual void SetupPlayerInputComponent(UInputComponent* Input) override;
    virtual void Tick(float DeltaSeconds) override;
    FString LoadingIsland;
private:
    UPROPERTY(VisibleAnywhere) TObjectPtr<USpringArmComponent> Arm;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UCameraComponent> Camera;
    void Horizontal(float Value);
    void Vertical(float Value);
    void Zoom(float Value);
    void StartOrbit();
    void StopOrbit();
    void StartPan();
    void StopPan();
    void ResetView();
    void UpdateCursor();
    void FocusPet();
    void ToggleInterface();
    void MovePetToCursor();
    void GreetPet();
    void PetCat();
    void RestPet();
    void ToggleAgent();
    void Eat(); void Drink(); void GoHome(); void Play(); void FillBowls();
    void Meadow(); void Sakura();
    float IslandLoadDelay = 0.f;
    bool bOrbit = false;
    bool bPan = false;
    float TargetDistance = 2200.f;
    float Yaw = -45.f;
    float Pitch = -28.f;
};
