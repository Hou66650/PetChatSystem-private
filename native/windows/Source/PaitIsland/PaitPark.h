#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Dom/JsonObject.h"
#include "PaitPark.generated.h"
class SWidget;
class ASkeletalMeshActor;
struct FPaitParkPet {
    TArray<TWeakObjectPtr<ASkeletalMeshActor>> Parts;
    FVector Position=FVector::ZeroVector;
    float Heading=0, Height=.85f, HeadingOffset=0, Lift=0;
    FString Name, Root, Prefix, Clip;
};
UCLASS()
class PAITISLAND_API APaitPark : public AActor {
    GENERATED_BODY()
public:
    APaitPark();
    virtual void BeginPlay() override;
    virtual void Tick(float Dt) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    void MoveTo(FVector Point);
    void ShowInterface(bool Show);
private:
    void Interface();
    void Join();
    void Leave();
    void Sync();
    void Apply(TSharedPtr<FJsonObject> Data, bool Initial=false);
    void Route(FVector2D Point);
    void Action(FString Value);
    void Think();
    void Facility(FString Id);
    FVector SampleFacility(const FString& Id,float Distance,float& Heading) const;
    void Animate(FPaitParkPet& Pet,const FString& Clip);
    void ClearPets();
    void TickFixture(float Dt);
    TMap<FString,FPaitParkPet> Pets;
    TSharedPtr<FJsonObject> Navigation;
    TSharedPtr<SWidget> Widget;
    TArray<FVector2D> Path;
    FString Token, Mine, Status=TEXT("选择伙伴，登录后带它入园。"), Activity=TEXT("idle"), CurrentAction=TEXT("idle"), FacilityId, PendingFacility;
    FVector2D Self=FVector2D::ZeroVector;
    double NextSyncAt=0, LastContactAt=0;
    float PreviousFrameLimit=0;
    float Yaw=0,DecisionIn=3,ManualUntil=0,Energy=1,ActionUntil=0,Progress=0,ConfirmedProgress=0;
    int32 PetId=3,Online=0;
    uint64 Epoch=0,Session=0;
    bool Busy=false,Routing=false,Auto=true,Hidden=false,FacilityConfirmed=false,GroundSyncPending=false;
    int32 TestStep=0;
    float TestTime=0, TestHeight=0;
    bool TestBridge=false, TestTunnel=false;
};
