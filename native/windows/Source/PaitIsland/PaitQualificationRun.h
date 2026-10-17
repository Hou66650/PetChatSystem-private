#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PaitQualificationRun.generated.h"

class ASkeletalMeshActor;
class ACameraActor;
class UAnimSequence;
class FJsonObject;
class FJsonValue;

// Explicit opt-in P0 diagnostic, never spawned during ordinary play.
UCLASS()
class APaitQualificationRun : public AActor
{
    GENERATED_BODY()
public:
    APaitQualificationRun();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
private:
    void EnterShot(int32 Index);
    void SamplePose();
    void Capture(const FString& Suffix);
    void Finish(const FString& Failure = FString());
    UPROPERTY() TArray<TObjectPtr<ASkeletalMeshActor>> Cats;
    UPROPERTY() TArray<TObjectPtr<UAnimSequence>> Clips;
    UPROPERTY() TObjectPtr<ACameraActor> Camera;
    TArray<TSharedPtr<FJsonValue>> Samples;
    TArray<FTransform> PreviousPose;
    TArray<FString> Captures;
    FString EvidenceDir;
    FVector OriginalCatPosition;
    FVector GreenhouseCenter;
    double Started = 0;
    double ShotStarted = 0;
    double LastSample = 0;
    double Duration = 300;
    uint64 Frames = 0;
    int32 Shot = -1;
    int32 ChangedSamples = 0;
    bool bFirstCapture = false;
    bool bSecondCapture = false;
    bool bFinished = false;
};
