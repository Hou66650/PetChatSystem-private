#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PaitMeadowPet.generated.h"

class ASkeletalMeshActor;
class UAnimSequence;
class ACameraActor;

/** Isolated local interaction driver; no production Agent or account requests. */
UCLASS()
class PAITISLAND_API APaitMeadowPet : public AActor
{
    GENERATED_BODY()
public:
    APaitMeadowPet();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    bool RequestMove(const FVector& Destination);
    void Greet();
    const FString& GetStatus() const { return Status; }
private:
    bool InitializeGrounding();
    bool GroundAt(const FVector& Point, FVector& Surface) const;
    void SetClip(UAnimSequence* Clip, bool Loop = true);
    void ApplyPose(const FVector& Position, float Yaw);
    void TickInteractionTest(float DeltaSeconds);
    void FinishTest(const FString& Error);
    UPROPERTY() TArray<TObjectPtr<ASkeletalMeshActor>> Cats;
    UPROPERTY() TObjectPtr<UAnimSequence> Idle;
    UPROPERTY() TObjectPtr<UAnimSequence> Walk;
    UPROPERTY() TObjectPtr<UAnimSequence> Greeting;
    UPROPERTY() TObjectPtr<ACameraActor> TestCamera;
    UPROPERTY() TObjectPtr<UAnimSequence> CurrentClip;
    TArray<FVector> Route;
    FVector Feet = FVector::ZeroVector;
    FVector TestStart = FVector::ZeroVector;
    FVector TestDestination = FVector::ZeroVector;
    float RootLift = 0.f;
    float HeadingOffset = 0.f;
    float CurrentYaw = 0.f;
    float GreetingRemaining = 0.f;
    float RetryIn = 0.f;
    float TravelCm = 0.f;
    float TestElapsed = 0.f;
    float MaxGroundErrorCm = 0.f;
    int32 RouteIndex = 0;
    int32 TestStage = 0;
    bool bReady = false;
    bool bTest = false;
    bool bTestFinished = false;
    bool bOutsideRejected = false;
    bool bWalkingCaptured = false;
    bool bArrivalCaptured = false;
    FString EvidenceDir;
    FString Status = TEXT("Preparing island paths...");
};
