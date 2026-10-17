#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Dom/JsonObject.h"
#include "PaitGarden.generated.h"
class UInstancedStaticMeshComponent;
struct FStreamableHandle;
UCLASS()
class PAITISLAND_API APaitGarden : public AActor
{
    GENERATED_BODY()
public:
    APaitGarden();
    virtual void BeginPlay() override;
    virtual void Tick(float Dt) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    bool Click(const FVector& Point);
    TSharedRef<FJsonObject> Diagnostics() const;
private:
    void Refresh(TSharedPtr<FJsonObject> State);
    void ClearModels();
    FString Owner, Signature;
    float PollAfter=0;
    bool Fetching=false;
    uint64 Generation=0;
    uint64 AccountRevision=MAX_uint64;
    TSharedPtr<FJsonObject> Catalog;
    TSharedPtr<FStreamableHandle> Handle;
    UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> Plants;
    TArray<TWeakObjectPtr<AActor>> DemonstrationPlants;
};
