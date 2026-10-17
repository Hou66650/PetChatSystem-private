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
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    bool RequestMove(const FVector& Destination, bool FromAgent = false);
    void Greet();
    bool Care(const FString& Kind, bool FromAgent = false);
    FString GetCareSummary() const;
    bool CareAt(const FVector& Hit);
    FString CareHint(const FVector& Hit) const;
    void Refill();
    void Pet();
    void Rest();
    void ToggleAutonomy();
    FString GetAgentSummary() const;
    FString GetLastEvent() const;
    const FString& GetStatus() const { return Status; }
private:
    void InitializeCare();
    void TickCareTest(float Dt);
    void FinishCareTest(const FString& Error);
    mutable FString LastGroundIssue;
    FString LastRouteIssue;
    FString PendingCare;
    FString CareStageName;
    FVector CareFacing = FVector::ZeroVector;
    TMap<FString,FVector> Stations;
    TMap<FString,FVector> Approaches;
    float Food = 100.f, Water = 100.f, Fullness = .8f, Hydration = .8f;
    int32 Meals = 0, Drinks = 0, HomeRests = 0, Plays = 0, CareTestStage = 0;
    bool bCareTest = false;
    FString PetRoot, PetPrefix, IslandMap;
    bool bSakura = false;
    bool InitializeGrounding();
    bool GroundAt(const FVector& Point, FVector& Surface) const;
    void SetClip(UAnimSequence* Clip, bool Loop = true);
    void ApplyPose(const FVector& Position, float Yaw);
    void TickInteractionTest(float DeltaSeconds);
    void FinishTest(const FString& Error);
    void InitializeAgent();
    void TickAgent(float DeltaSeconds);
    void TickAgentTest(float DeltaSeconds);
    void FinishAgentTest(const FString& Error);
    void InterruptAction(const FString& Reason);
    void StartAction(const FString& Action, bool FromAgent);
    void TickAction(float DeltaSeconds);
    void Arrived();
    void Blocked();
    void Remember(const FString& Action, const FString& Outcome);
    void SaveMemory() const;
    FString PlaceAt(const FVector& Point) const;
    FString CellAt(const FVector& Point) const;
    UPROPERTY() TArray<TObjectPtr<ASkeletalMeshActor>> Cats;
    UPROPERTY() TObjectPtr<UAnimSequence> Idle;
    UPROPERTY() TObjectPtr<UAnimSequence> Walk;
    UPROPERTY() TObjectPtr<UAnimSequence> Greeting;
    UPROPERTY() TObjectPtr<ACameraActor> TestCamera;
    UPROPERTY() TObjectPtr<UAnimSequence> CurrentClip;
    UPROPERTY() TMap<FString,TObjectPtr<UAnimSequence>> AgentClips;
    struct FActionStep { FString Clip; float Seconds; bool Loop; };
    TArray<FActionStep> ActionSteps;
    TArray<TSharedPtr<class FJsonValue>> AgentEvents;
    TMap<FString,int32> Visits;
    TMap<FString,float> BlockedCells;
    FRandomStream AgentRandom;
    FString ActiveAction;
    FString TargetCell;
    FString LastCell;
    FString AgentReason = TEXT("Getting to know this island");
    FString MemoryFile;
    float Energy = .8f;
    float Curiosity = .7f;
    float AgentClock = 0.f;
    float NextDecision = 5.f;
    float PlayerLeaseUntil = 0.f;
    float ActionStepRemaining = 0.f;
    float AgentTestStageStarted = 0.f;
    float RestEnergyBefore = 0.f;
    int32 ActionStep = 0;
    int32 CompletedExplorations = 0;
    int32 CompletedRests = 0;
    int32 CompletedPets = 0;
    int32 AgentTestStage = 0;
    bool bAutonomy = true;
    bool bAgentAction = false;
    bool bAgentRoute = false;
    bool bAgentTest = false;
    bool bPlayerPriorityVerified = false;
    bool bPauseVerified = false;
    bool bMemoryVerified = false;
    FVector AgentTestPausePosition = FVector::ZeroVector;
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
