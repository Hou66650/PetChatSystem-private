#include "PaitGarden.h"
#include "PaitAccountSubsystem.h"
#include "Engine/GameInstance.h"
#include "Engine/AssetManager.h"
#include "Engine/StreamableManager.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "EngineUtils.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"

namespace {
FString S(const TSharedPtr<FJsonObject>& O,const TCHAR* K){FString V;if(O)O->TryGetStringField(K,V);return V;}
double N(const TSharedPtr<FJsonObject>& O,const TCHAR* K){double V=0;if(O)O->TryGetNumberField(K,V);return V;}
TArray<TSharedPtr<FJsonValue>> A(const TSharedPtr<FJsonObject>& O,const TCHAR* K){const TArray<TSharedPtr<FJsonValue>>* V=nullptr;return O&&O->TryGetArrayField(K,V)?*V:TArray<TSharedPtr<FJsonValue>>();}
}
APaitGarden::APaitGarden(){PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.TickInterval=.25f;RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("Garden"));}
void APaitGarden::BeginPlay()
{
    Super::BeginPlay();FString Json;
    if(FFileHelper::LoadFileToString(Json,*(FPaths::ProjectContentDir()/TEXT("PaitData/garden-models.json"))))FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),Catalog);
    for(TActorIterator<AStaticMeshActor> It(GetWorld());It;++It){const UStaticMesh* Mesh=It->GetStaticMeshComponent()->GetStaticMesh();if(Mesh && Mesh->GetPathName().StartsWith(TEXT("/Game/Imported/P1MeadowV2_Conventional/")) && Mesh->GetName().Contains(TEXT("_stage_")))DemonstrationPlants.Add(*It);}
}
void APaitGarden::ClearModels(){for(auto C:Plants)if(C)C->DestroyComponent();Plants.Empty();}
void APaitGarden::EndPlay(const EEndPlayReason::Type Reason){++Generation;if(Handle)Handle->CancelHandle();Handle.Reset();ClearModels();Super::EndPlay(Reason);}
void APaitGarden::Tick(float Dt)
{
    Super::Tick(Dt);auto* Account=GetGameInstance()->GetSubsystem<UPaitAccountSubsystem>();if(!Account)return;
    const FString Current=Account->IsLoggedIn()?Account->Username:TEXT("");
    if(Owner!=Current || AccountRevision!=Account->GetSessionRevision()){++Generation;if(Handle)Handle->CancelHandle();Handle.Reset();ClearModels();Signature.Empty();Owner=Current;Fetching=false;PollAfter=0;AccountRevision=Account->GetSessionRevision();Account->GardenLoading=false;for(auto Actor:DemonstrationPlants)if(Actor.IsValid())Actor->SetActorHiddenInGame(!Current.IsEmpty());}
    if(Owner.IsEmpty())return;
    PollAfter-=Dt;
    if(PollAfter<=0 && !Fetching){Fetching=true;PollAfter=15.f;TWeakObjectPtr<APaitGarden> Weak(this);const FString Name=Owner;
        Account->Call(TEXT("GET"),TEXT("farm"),nullptr,[Weak,Name](bool Ok,TSharedPtr<FJsonObject> Data,FString Error){
            if(!Weak.IsValid() || Weak->Owner!=Name)return;Weak->Fetching=false;
            auto* U=Weak->GetGameInstance()->GetSubsystem<UPaitAccountSubsystem>();
            if(Ok)U->GardenState=Data;else U->GardenStatus=Error;
        });
    }
    if(Account->GardenState)Refresh(Account->GardenState);
}
void APaitGarden::Refresh(TSharedPtr<FJsonObject> State)
{
    auto* Account=GetGameInstance()->GetSubsystem<UPaitAccountSubsystem>();if(!Catalog){Account->GardenStatus=TEXT("植物模型清单未加载");return;}
    TMap<FString,TArray<FTransform>> Groups;
    auto Add=[&](const FString& Species,int32 Stage,double X,double Y,double Z,double Yaw,bool Pot){
        FString Base=Species;if(Stage<10)Base.RemoveFromEnd(TEXT("-dream"));
        const FString Key=Base+FString::Printf(TEXT("-%02d"),FMath::Clamp(Stage,1,10));
        Groups.FindOrAdd(Key).Add(FTransform(FRotator(0,-FMath::RadiansToDegrees(Yaw),0),FVector(X*100,Y*100,Z*100)));
        if(Pot)Groups.FindOrAdd(TEXT("flowerpot")).Add(FTransform(FRotator(0,-FMath::RadiansToDegrees(Yaw),0),FVector(X*100,Y*100,(Z-.29)*100)));
    };
    for(auto V:A(State,TEXT("beds"))){auto Bed=V->AsObject();const TSharedPtr<FJsonObject>* Plant=nullptr;if(Bed->TryGetObjectField(TEXT("plant"),Plant))Add(S(*Plant,TEXT("species")),N(*Plant,TEXT("stage")),N(Bed,TEXT("x")),N(Bed,TEXT("z")),.23,0,false);}
    for(auto V:A(State,TEXT("arrangements"))){auto P=V->AsObject();bool Pot=S(P,TEXT("container"))==TEXT("pot");Add(S(P,TEXT("species")),N(P,TEXT("stage")),N(P,TEXT("x")),N(P,TEXT("z")),Pot?.325:.035,N(P,TEXT("yaw")),Pot);}
    for(auto V:A(State,TEXT("decorations"))){auto D=V->AsObject();for(auto P:A(State,TEXT("placements"))){auto Place=P->AsObject();if(S(Place,TEXT("id"))==S(D,TEXT("slot"))){bool Pot=S(Place,TEXT("kind"))==TEXT("flower");Add(S(D,TEXT("species")),10,N(Place,TEXT("x")),N(Place,TEXT("z")),Pot?.33:.04,0,Pot);break;}}}
    FString Next;TArray<FString> Keys;Groups.GetKeys(Keys);Keys.Sort();TArray<FSoftObjectPath> Assets;
    for(auto Key:Keys){Next+=Key;for(auto& Transform:Groups[Key])Next+=Transform.ToHumanReadableString();const TSharedPtr<FJsonObject>* Entry=nullptr;if(!Catalog->TryGetObjectField(Key,Entry)){Account->GardenStatus=TEXT("缺少植物模型：")+Key;return;}for(auto V:A(*Entry,TEXT("meshes")))Assets.AddUnique(FSoftObjectPath(V->AsString()));}
    if(Next==Signature)return;Signature=Next;const uint64 Epoch=++Generation;if(Handle)Handle->CancelHandle();
    if(Assets.IsEmpty()){ClearModels();Account->GardenLoading=false;return;}
    Account->GardenLoading=true;Account->GardenStatus=TEXT("正在载入花园模型…");TWeakObjectPtr<APaitGarden> Weak(this);const FString Name=Owner;
    Handle=UAssetManager::GetStreamableManager().RequestAsyncLoad(Assets,FStreamableDelegate::CreateLambda([Weak,Epoch,Name,Groups](){
        if(!Weak.IsValid() || Weak->Generation!=Epoch || Weak->Owner!=Name)return;
        auto* U=Weak->GetGameInstance()->GetSubsystem<UPaitAccountSubsystem>();if(U->Username!=Name || !U->IsLoggedIn())return;
        Weak->ClearModels();int32 Count=0;
        for(auto& Pair:Groups){const auto Entry=Weak->Catalog->GetObjectField(Pair.Key);for(auto V:A(Entry,TEXT("meshes"))){auto* Mesh=Cast<UStaticMesh>(FSoftObjectPath(V->AsString()).ResolveObject());if(!Mesh)continue;
            auto* C=NewObject<UInstancedStaticMeshComponent>(Weak.Get());C->SetupAttachment(Weak->GetRootComponent());C->SetStaticMesh(Mesh);C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->RegisterComponent();for(auto& Transform:Pair.Value)C->AddInstance(Transform,true);Weak->Plants.Add(C);++Count;
        }}
        U->GardenLoading=false;U->GardenStatus=Count?TEXT("花园已同步"):TEXT("植物模型未能载入");
    }));
}
bool APaitGarden::Click(const FVector& Point)
{
    auto* U=GetGameInstance()->GetSubsystem<UPaitAccountSubsystem>();if(!U || !U->GardenState)return false;
    for(auto V:A(U->GardenState,TEXT("beds"))){auto Bed=V->AsObject();if(FMath::Abs(Point.X/100-N(Bed,TEXT("x")))<N(Bed,TEXT("w"))*.5+.12 && FMath::Abs(Point.Y/100-N(Bed,TEXT("z")))<N(Bed,TEXT("d"))*.5+.12){U->OpenGarden(S(Bed,TEXT("id")));return true;}}
    return false;
}
TSharedRef<FJsonObject> APaitGarden::Diagnostics() const
{
    auto Data=MakeShared<FJsonObject>();Data->SetNumberField(TEXT("mesh_components"),Plants.Num());int32 Instances=0;
    for(auto C:Plants)if(C)Instances+=C->GetInstanceCount();Data->SetNumberField(TEXT("mesh_instances"),Instances);
    Data->SetNumberField(TEXT("catalog_entries"),Catalog?Catalog->Values.Num():0);Data->SetNumberField(TEXT("demonstration_meshes_suppressed"),Owner.IsEmpty()?0:DemonstrationPlants.Num());
    Data->SetBoolField(TEXT("account_bound"),!Owner.IsEmpty());return Data;
}
