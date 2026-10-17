#include "PaitMeadowPet.h"
#include "NavigationSystem.h"
#include "NavigationData.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Engine/StaticMeshActor.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/PlayerController.h"
#include "Misc/FileHelper.h"
#include "HAL/PlatformMisc.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "UnrealClient.h"

void APaitMeadowPet::InitializeCare()
{
    // Existing detailed Snow/Camp art is retained. Do not reuse Meadow bowl
    // coordinates until real interaction anchors are authored on those maps.
    if(bAdditionalIsland) return;
    Stations.Add(TEXT("food"),bSakura?FVector(-100,1180,23):FVector(115,628,41));
    Stations.Add(TEXT("water"),bSakura?FVector(-55,1180,23):FVector(185,628,41));
    Stations.Add(TEXT("home"),bSakura?FVector(-40,600,38):FVector(-300,462,13));
    Approaches.Add(TEXT("food"),Stations[TEXT("food")]+FVector(0,bSakura?-75:-80,-25));
    Approaches.Add(TEXT("water"),Stations[TEXT("water")]+FVector(0,bSakura?-75:-80,-25));
    Approaches.Add(TEXT("home"),Stations[TEXT("home")]+FVector(0,-20,0));
    for(TActorIterator<AStaticMeshActor> It(GetWorld());It;++It)
    {
        if(!It->GetStaticMeshComponent()->GetStaticMesh()) continue;
        if(It->GetStaticMeshComponent()->GetStaticMesh()->GetName().Contains(TEXT("Toy_ball")))
        {
            FVector Center,Extent; It->GetActorBounds(false,Center,Extent);
            Stations.Add(TEXT("toy"),Center); Approaches.Add(TEXT("toy"),Center+FVector(0,-90,0)); break;
        }
    }
}
bool APaitMeadowPet::Care(const FString& Kind,bool FromAgent)
{
    if (!bReady || !Stations.Contains(Kind)) { Status=TEXT("That station is not available yet"); return false; }
    const FString Required=Kind==TEXT("home") ? TEXT("sit_idle") : Kind==TEXT("toy") ? TEXT("play_bow") : TEXT("eat");
    if(!AgentClips.FindRef(Required)) { Status=TEXT("The required pet animation is unavailable"); return false; }
    if ((Kind==TEXT("food") && Food<10.f) || (Kind==TEXT("water") && Water<8.f))
    { Status=TEXT("Bowl is empty - refill with B"); return false; }
    const FVector Target=Approaches[Kind];
    if (FVector::Dist2D(Feet,Target)<12.f)
    {
        CurrentYaw=(Stations[Kind]-Feet).Rotation().Yaw-HeadingOffset; ApplyPose(Feet,CurrentYaw);
        StartAction(Kind,FromAgent); Status=TEXT("At ")+Kind+TEXT(" station"); return true;
    }
    if (!RequestMove(Target,FromAgent)) { Status=TEXT("Cannot reach ")+Kind+TEXT(" safely: ")+Status; return false; }
    PendingCare=Kind; CareFacing=Stations[Kind]; Status=TEXT("Walking to ")+Kind;
    return true;
}
bool APaitMeadowPet::CareAt(const FVector& Hit)
{
    FString Closest; double Distance=100.;
    for(const auto& Pair:Stations)
    {
        const double D=FVector::Dist2D(Hit,Pair.Value);
        if(D<Distance && FMath::Abs(Hit.Z-Pair.Value.Z)<90.) { Distance=D; Closest=Pair.Key; }
    }
    if(Closest.IsEmpty()) return false;
    Care(Closest); return true;
}
void APaitMeadowPet::Refill()
{
    Food=100; Water=100; SaveMemory(); Status=TEXT("Both bowls refilled - local preview only");
    const bool Previous=bAgentAction; bAgentAction=false; Remember(TEXT("refill"),TEXT("completed")); bAgentAction=Previous;
}
FString APaitMeadowPet::GetCareSummary() const
{
    return FString::Printf(TEXT("Local preview bowls: food %.0f%% / water %.0f%% | F eat  V drink  N home  T toy  B refill"),Food,Water);
}
void APaitMeadowPet::TickCareTest(float Dt)
{
    TestElapsed+=Dt;
    if(TestElapsed>240.f) { FinishCareTest(TEXT("Care sequence timeout: ")+Status); return; }
    if(!bReady || TestElapsed<8.f) return;
    if(!TestCamera)
    {
        TestCamera=GetWorld()->SpawnActor<ACameraActor>();
        TestCamera->GetCameraComponent()->SetFieldOfView(45.f);
        GetWorld()->GetFirstPlayerController()->SetViewTarget(TestCamera);
    }
    const FVector Target=Feet+FVector(0,0,40);
    TestCamera->SetActorLocation(Target+(CareStageName==TEXT("home") ? FVector(0,500,260) : FVector(300,-450,260)));
    TestCamera->SetActorRotation((Target-TestCamera->GetActorLocation()).Rotation());
    const TArray<FString> Order={TEXT("food"),TEXT("water"),TEXT("home"),TEXT("toy")};
    if(CareTestStage==0)
    {
        if(!Care(Order[0])) { FinishCareTest(Status); return; }
        CareStageName=Order[0]; CareTestStage=1;
    }
    if(ActiveAction==CareStageName && !bArrivalCaptured &&
       (ActiveAction==TEXT("home") ? (ActionStep==1 && ActionStepRemaining<5.f) : (ActionStep==0 && ActionStepRemaining<.8f)))
    { FScreenshotRequest::RequestScreenshot(EvidenceDir/(CareStageName+TEXT(".png")),true,false); bArrivalCaptured=true; }
    if(CareTestStage>0 && ActiveAction.IsEmpty() && Route.IsEmpty())
    {
        const bool Completed=CareTestStage==1 ? Meals==1 : CareTestStage==2 ? Drinks==1 : CareTestStage==3 ? HomeRests==1 : Plays==1;
        if(!Completed) { FinishCareTest(TEXT("Care stopped before completion: ")+Status); return; }
        if(CareTestStage==4) { FinishCareTest(TEXT("")); return; }
        const FString Next=Order[CareTestStage++]; CareStageName=Next; bArrivalCaptured=false;
        if(!Care(Next)) FinishCareTest(Status);
    }
}
void APaitMeadowPet::FinishCareTest(const FString& Error)
{
    bTestFinished=true;
    const bool Passed=Error.IsEmpty() && Meals==1 && Drinks==1 && HomeRests==1 && Plays==1 && Food==90.f && Water==92.f;
    TSharedRef<FJsonObject> R=MakeShared<FJsonObject>();
    R->SetBoolField(TEXT("passed"),Passed); R->SetStringField(TEXT("error"),Error);
    R->SetStringField(TEXT("map"),IslandMap); R->SetStringField(TEXT("feet"),Feet.ToString());
    R->SetNumberField(TEXT("elapsed_seconds"),TestElapsed);
    R->SetStringField(TEXT("status"),Status);
    R->SetStringField(TEXT("route_diagnostic"),LastRouteIssue);
    if(UNavigationSystemV1* Nav=FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()))
        if(ANavigationData* Data=Nav->GetDefaultNavDataInstance(FNavigationSystem::DontCreate))
        { R->SetNumberField(TEXT("nav_height"),Data->GetConfig().AgentHeight); R->SetNumberField(TEXT("nav_radius"),Data->GetConfig().AgentRadius); }
    TArray<TSharedPtr<FJsonValue>> Nearby;
    for(const auto& Pair:Stations)
    {
        FVector G; const bool Valid=GroundAt(Pair.Value,G);
        TSharedRef<FJsonObject> Probe=MakeShared<FJsonObject>();
        Probe->SetStringField(TEXT("station"),Pair.Key); Probe->SetBoolField(TEXT("supported"),Valid); Probe->SetStringField(TEXT("hit"),LastGroundIssue);
        Nearby.Add(MakeShared<FJsonValueObject>(Probe));
    }
    R->SetArrayField(TEXT("station_ground_probes"),Nearby);
    TArray<TSharedPtr<FJsonValue>> HomeProbes;
    if(UNavigationSystemV1* Nav=FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()))
    for(int Y=-150;Y<=100;Y+=25)
    {
        const FVector P=Stations[TEXT("home")]+FVector(0,Y,0);
        FNavLocation N; FVector G=FVector::ZeroVector; GroundAt(P,G);
        TSharedRef<FJsonObject> Q=MakeShared<FJsonObject>();
        Q->SetStringField(TEXT("point"),P.ToString()); Q->SetStringField(TEXT("physical"),LastGroundIssue);
        Q->SetBoolField(TEXT("nav"),Nav->ProjectPointToNavigation(P,N,FVector(10,10,150)));
        Q->SetStringField(TEXT("nav_point"),N.Location.ToString());
        FHitResult H; FCollisionQueryParams Params(SCENE_QUERY_STAT(PaitHomeClearance),true);
        if(GetWorld()->LineTraceSingleByChannel(H,G+FVector(0,0,2),G+FVector(0,0,350),ECC_Visibility,Params))
            Q->SetStringField(TEXT("ceiling"),GetNameSafe(H.GetActor())+TEXT(" ")+H.ImpactPoint.ToString());
        HomeProbes.Add(MakeShared<FJsonValueObject>(Q));
    }
    R->SetArrayField(TEXT("home_navigation_probes"),HomeProbes);
    TArray<TSharedPtr<FJsonValue>> OpenGround;
    if(bSakura) if(UNavigationSystemV1* Nav=FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()))
    for(int X=-450;X<=450;X+=75) for(int Y=400;Y<=1100;Y+=100)
    {
        const FVector P(X,Y,10); FNavLocation N; FVector G;
        if(Nav->ProjectPointToNavigation(P,N,FVector(10,10,60)) && GroundAt(N.Location,G) && FMath::Abs(G.Z-3.5f)<10.f)
            OpenGround.Add(MakeShared<FJsonValueString>(G.ToString()));
    }
    R->SetArrayField(TEXT("open_arrival_ground"),OpenGround);
    TSharedRef<FJsonObject> Places=MakeShared<FJsonObject>();
    for(const auto& Pair:Approaches) Places->SetStringField(Pair.Key,Pair.Value.ToString());
    R->SetObjectField(TEXT("station_approaches"),Places);
    R->SetNumberField(TEXT("meals"),Meals); R->SetNumberField(TEXT("drinks"),Drinks);
    R->SetNumberField(TEXT("home_rests"),HomeRests); R->SetNumberField(TEXT("plays"),Plays);
    R->SetNumberField(TEXT("food_remaining"),Food); R->SetNumberField(TEXT("water_remaining"),Water);
    R->SetArrayField(TEXT("events"),AgentEvents); R->SetBoolField(TEXT("production_connected"),false);
    FString Json; FJsonSerializer::Serialize(R,TJsonWriterFactory<>::Create(&Json));
    bool Saved=FFileHelper::SaveStringToFile(Json,*(EvidenceDir/TEXT("care.json")));
    FPlatformMisc::RequestExitWithStatus(false,Passed&&Saved?0:2);
}

FString APaitMeadowPet::CareHint(const FVector& Hit) const
{
    FString Closest; double Distance=100.;
    for(const auto& Pair:Stations)
    {
        const double D=FVector::Dist2D(Hit,Pair.Value);
        if(D<Distance && FMath::Abs(Hit.Z-Pair.Value.Z)<90.) { Distance=D; Closest=Pair.Key; }
    }
    if(Closest==TEXT("food")) return FString::Printf(TEXT("Food bowl: %.0f%% | Click to eat"),Food);
    if(Closest==TEXT("water")) return FString::Printf(TEXT("Water bowl: %.0f%% | Click to drink"),Water);
    if(Closest==TEXT("home")) return TEXT("Pet shelter | Click to rest here");
    if(Closest==TEXT("toy")) return TEXT("Toy ball | Click to play here");
    return TEXT("");
}
