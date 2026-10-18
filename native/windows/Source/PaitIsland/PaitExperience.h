#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PaitExperience.generated.h"
class SWidget;
UCLASS()
class PAITISLAND_API APaitExperience : public AActor
{
    GENERATED_BODY()
public:
    APaitExperience();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void Tick(float Dt) override;
    void Select(int32 Index);
    void Enter();
    void Overview();
    void ReturnHome();
    bool Click(AActor* Target);
    bool IsHome() const;
private:
    void BuildInterface();
    void Travel(const FString& Map);
    void Account();
    TSharedPtr<SWidget> Interface;
    int32 Selected=INDEX_NONE;
    float Flight=0,Elapsed=0;
    bool AutoOrbit=false;
    FString Destination;
    double LastClick=0;
};
