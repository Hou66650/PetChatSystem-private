#include "PaitMeadowPet.h"
#include "Animation/SkeletalMeshActor.h"
#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "NavigationSystem.h"
#include "NavigationPath.h"
#include "NavigationData.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "UnrealClient.h"

APaitMeadowPet::APaitMeadowPet() { PrimaryActorTick.bCanEverTick = true; }
void APaitMeadowPet::BeginPlay()
{
    Super::BeginPlay();
    bSakura=GetWorld()->GetMapName().Contains(TEXT("Sakura"));
    IslandMap=bSakura ? TEXT("P1_SakuraV2") : TEXT("P1_MeadowV2");
    PetRoot=bSakura ? TEXT("/Game/Imported/P1Shiba/qiuqiu/SkeletalMeshes/") : TEXT("/Game/Imported/P0Cat/cat/SkeletalMeshes/");
    PetPrefix=bSakura ? TEXT("qiuqiu") : TEXT("cat");
    if(GetWorld()->GetMapName().Contains(TEXT("Snow")))
    { IslandMap=TEXT("P1_SnowV2"); PetRoot=TEXT("/Game/Imported/P1Husky/xueqiu/SkeletalMeshes/"); PetPrefix=TEXT("xueqiu"); bAdditionalIsland=true; }
    else if(GetWorld()->GetMapName().Contains(TEXT("Camp")))
    { IslandMap=TEXT("P1_CampV2"); PetRoot=TEXT("/Game/Imported/P1Shepherd/shepherd/SkeletalMeshes/"); PetPrefix=TEXT("shepherd"); bAdditionalIsland=true; }
    if(!bSakura && !bAdditionalIsland) for(TActorIterator<AStaticMeshActor> It(GetWorld());It;++It)
    {
        const UStaticMesh* Mesh=It->GetStaticMeshComponent()->GetStaticMesh();
        // Cedar batches include the low doorway threshold as well as walls.
        // Only upward-facing physical support is accepted by GroundAt.
        if(Mesh && Mesh->GetPathName().StartsWith(TEXT("/Game/Imported/P1MeadowV2_Conventional/")) &&
           Mesh->GetName().StartsWith(TEXT("cat_home_cedar_"))) It->Tags.AddUnique(TEXT("PaitGround"));
    }
    for (TActorIterator<ASkeletalMeshActor> It(GetWorld()); It; ++It)
    {
        USkeletalMeshComponent* C = It->GetSkeletalMeshComponent();
        if (!C->GetSkeletalMeshAsset() || !C->GetSkeletalMeshAsset()->GetPathName().StartsWith(PetRoot)) continue;
        C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        C->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        Cats.Add(*It);
    }
    auto Clip = [this](const TCHAR* Name) {
        const FString N = PetPrefix + Name;
        return LoadObject<UAnimSequence>(nullptr, *(PetRoot + N + TEXT(".") + N));
    };
    Idle = Clip(TEXT("idle_breathe")); Walk = Clip(TEXT("walk")); Greeting = Clip(TEXT("paw_greeting"));
    SetClip(Idle);
    if (UNavigationSystemV1* Nav=FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()))
    {
        Nav->GetDefaultNavDataInstance(FNavigationSystem::Create);
        // Serialized qualification maps carried the human-sized 144 cm config.
        // The supported agent and each existing runtime nav data must agree.
        for(TActorIterator<ANavigationData> It(GetWorld());It;++It)
        {
            FNavDataConfig Config=It->GetConfig(); Config.AgentHeight=110.f;
            Config.AgentRadius=35.f; Config.AgentStepHeight=18.f; It->SetConfig(Config);
        }
        Nav->Build();
    }
    bTest = FParse::Param(FCommandLine::Get(), TEXT("PaitMeadowTest"));
    bAgentTest = FParse::Param(FCommandLine::Get(), TEXT("PaitAgentTest"));
    bCareTest=FParse::Param(FCommandLine::Get(),TEXT("PaitCareTest"));
    if (bTest || bAgentTest || bCareTest)
    {
        FParse::Value(FCommandLine::Get(), TEXT("PaitEvidenceDir="), EvidenceDir);
        if (EvidenceDir.IsEmpty()) EvidenceDir = FPaths::ProjectSavedDir() / TEXT("Qualification/MeadowInteraction");
        EvidenceDir = FPaths::ConvertRelativePathToFull(EvidenceDir);
        IFileManager::Get().MakeDirectory(*EvidenceDir, true);
    }
    InitializeAgent();
    InitializeCare();
}
bool APaitMeadowPet::GroundAt(const FVector& Point, FVector& Surface) const
{
    FCollisionQueryParams Params(SCENE_QUERY_STAT(PaitGround),true);
    LastGroundIssue.Empty();
    // A paw spans small masonry joints. Check a bounded 6 cm support disk,
    // never bridge an unsupported gap or relax the 18 cm movement step limit.
    for(const FVector& Offset : {FVector::ZeroVector,FVector(6,0,0),FVector(-6,0,0),FVector(0,6,0),FVector(0,-6,0)})
    {
        FHitResult Hit;
        if(!GetWorld()->LineTraceSingleByChannel(Hit,Point+Offset+FVector(0,0,80),Point+Offset-FVector(0,0,240),ECC_Visibility,Params))
        { if(Offset.IsZero()) LastGroundIssue=TEXT("no collision hit"); continue; }
        if(Offset.IsZero()) LastGroundIssue=FString::Printf(TEXT("hit=%s normal=%s point=%s ground=%d"),
            *GetNameSafe(Hit.GetActor()),*Hit.ImpactNormal.ToString(),*Hit.ImpactPoint.ToString(),Hit.GetActor()&&Hit.GetActor()->ActorHasTag(TEXT("PaitGround")));
        if(!Hit.GetActor() || !Hit.GetActor()->ActorHasTag(TEXT("PaitGround")) || Hit.ImpactNormal.Z<.8f) continue;
        Surface=FVector(Point.X,Point.Y,Hit.ImpactPoint.Z); return true;
    }
    return false;
}
bool APaitMeadowPet::InitializeGrounding()
{
    if (Cats.Num()!=(bSakura || bAdditionalIsland?2:3) || !Idle || !Walk || !Greeting) { Status=TEXT("Pet assets unavailable"); return false; }
    UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
    if (!Nav) { Status=TEXT("Navigation system unavailable"); return false; }
    if (UNavigationSystemV1::IsNavigationBeingBuiltOrLocked(GetWorld())) { Status=TEXT("Preparing complete island paths..."); return false; }
    FNavLocation Projected;
    // Seed on the original cat position, never teleport onto a disconnected roof.
    if (!Nav->ProjectPointToNavigation(Cats[0]->GetActorLocation(), Projected, FVector(500,500,180)))
    { Status=TEXT("Waiting for a navigable surface at cat spawn"); return false; }
    // Recast voxel surfaces sit above the actual triangles. Feet always use the
    // physics surface, while a bounded difference rejects roofs/other levels.
    if (!GroundAt(Projected.Location, Feet) || FMath::Abs(Feet.Z-Projected.Location.Z)>60.f)
    { Status=FString::Printf(TEXT("Ground check failed at %.0f, %.0f, %.0f"),Projected.Location.X,Projected.Location.Y,Projected.Location.Z); return false; }
    USkeletalMeshComponent* C = Cats[0]->GetSkeletalMeshComponent();
    float Sole = MAX_flt;
    for (const TCHAR* Bone : {TEXT("FL_foot"),TEXT("FR_foot"),TEXT("HL_foot"),TEXT("HR_foot")})
    {
        if (C->GetBoneIndex(Bone)==INDEX_NONE) { Status=TEXT("Missing foot bone"); return false; }
        Sole = FMath::Min(Sole, static_cast<float>(C->GetSocketLocation(Bone).Z-Cats[0]->GetActorLocation().Z));
    }
    RootLift = 3.f-Sole;
    FVector Forward = C->GetSocketLocation(TEXT("head"))-C->GetSocketLocation(TEXT("spine"));
    Forward.Z = 0;
    CurrentYaw = Cats[0]->GetActorRotation().Yaw;
    HeadingOffset = Forward.Rotation().Yaw-CurrentYaw;
    ApplyPose(Feet, CurrentYaw);
    Status=TEXT("Click open ground to walk | G greeting");
    return true;
}
void APaitMeadowPet::ApplyPose(const FVector& Position, float Yaw)
{
    for (ASkeletalMeshActor* Cat : Cats)
        Cat->SetActorLocationAndRotation(Position+FVector(0,0,RootLift), FRotator(0,Yaw,0));
}
void APaitMeadowPet::SetClip(UAnimSequence* Clip, bool Loop)
{
    if (!Clip || CurrentClip==Clip) return;
    CurrentClip=Clip;
    for (ASkeletalMeshActor* Cat : Cats) Cat->GetSkeletalMeshComponent()->PlayAnimation(Clip,Loop);
}
bool APaitMeadowPet::RequestMove(const FVector& Destination, bool FromAgent)
{
    if (!bReady) return false;
    LastRouteIssue.Empty();
    UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
    FNavLocation Projected;
    FVector Ground;
    if (!Nav || !Nav->ProjectPointToNavigation(Destination,Projected,FVector(45,45,80)))
    { GroundAt(Destination,Ground); LastRouteIssue=TEXT("navigation_projection: ")+Destination.ToString()+TEXT(" physical=")+LastGroundIssue; Status=TEXT("Choose reachable open ground"); return false; }
    if(!GroundAt(Projected.Location,Ground) || FMath::Abs(Ground.Z-Projected.Location.Z)>60.f)
    { LastRouteIssue=TEXT("projected_ground: ")+Projected.Location.ToString()+TEXT(" physical=")+LastGroundIssue; Status=TEXT("Choose reachable open ground"); return false; }
    UNavigationPath* Path = UNavigationSystemV1::FindPathToLocationSynchronously(GetWorld(),Feet,Projected.Location);
    if (!Path || !Path->IsValid() || Path->IsPartial() || Path->PathPoints.Num()<2)
    { LastRouteIssue=TEXT("path_missing_or_partial: ")+Feet.ToString()+TEXT(" -> ")+Projected.Location.ToString(); Status=TEXT("No safe path to that spot"); return false; }
    // Check the actual walking surface before committing. Recast voxels can
    // smooth over narrow steps or pots that are too high for this gait.
    FVector Previous=Feet;
    for (int32 Segment=1; Segment<Path->PathPoints.Num(); ++Segment)
    {
        const FVector A=Path->PathPoints[Segment-1], B=Path->PathPoints[Segment];
        const int32 Samples=FMath::Max(1,FMath::CeilToInt(FVector::Dist2D(A,B)/12.f));
        for (int32 I=1; I<=Samples; ++I)
        {
            FVector Surface=FVector::ZeroVector;
            if (!GroundAt(FMath::Lerp(A,B,static_cast<float>(I)/Samples),Surface) || FMath::Abs(Surface.Z-Previous.Z)>18.f)
            { LastRouteIssue=TEXT("surface_check sample=")+FMath::Lerp(A,B,static_cast<float>(I)/Samples).ToString()+TEXT(" previous=")+Previous.ToString()+TEXT(" surface=")+Surface.ToString()+TEXT(" ")+LastGroundIssue; Status=TEXT("That route needs a safer crossing"); return false; }
            Previous=Surface;
        }
    }
    InterruptAction(TEXT("interrupted"));
    Route=Path->PathPoints; RouteIndex=1; GreetingRemaining=0;
    bAgentRoute=FromAgent; bAgentAction=FromAgent;
    ActiveAction=TEXT("walk"); TargetCell=CellAt(Projected.Location);
    if (!FromAgent) PlayerLeaseUntil=AgentClock+15.f;
    Status=FromAgent ? TEXT("Exploring: ")+PlaceAt(Projected.Location) : TEXT("Walking to your chosen spot");
    Remember(TEXT("walk"),TEXT("started"));
    return true;
}
void APaitMeadowPet::Greet()
{
    if (!bReady) return;
    StartAction(TEXT("greet"),false);
}
void APaitMeadowPet::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!bReady)
    {
        RetryIn-=DeltaSeconds;
        if (RetryIn<=0.f) { RetryIn=.5f; bReady=InitializeGrounding(); }
    }
    else if (Route.IsValidIndex(RouteIndex))
    {
        FVector Delta=Route[RouteIndex]-Feet; Delta.Z=0;
        const float Distance=Delta.Size();
        if (Distance<4.f)
        {
            ++RouteIndex;
            if (!Route.IsValidIndex(RouteIndex)) { Route.Reset(); Arrived(); }
        }
        else
        {
            const float DesiredYaw=Delta.Rotation().Yaw-HeadingOffset;
            CurrentYaw=FMath::FixedTurn(CurrentYaw,DesiredYaw,180.f*DeltaSeconds);
            if (FMath::Abs(FMath::FindDeltaAngleDegrees(CurrentYaw,DesiredYaw))>30.f)
            { SetClip(Idle); ApplyPose(Feet,CurrentYaw); }
            else
            {
                const FVector Candidate=Feet+Delta/Distance*FMath::Min(Distance,65.f*FMath::Min(DeltaSeconds,.05f));
                FVector Ground;
                if (!GroundAt(Candidate,Ground) || FMath::Abs(Ground.Z-Feet.Z)>18.f)
                { LastRouteIssue=TEXT("moving: feet=")+Feet.ToString()+TEXT(" candidate=")+Candidate.ToString()+TEXT(" ground=")+Ground.ToString()+TEXT(" ")+LastGroundIssue; Route.Reset(); Blocked(); }
                else
                {
                    TravelCm+=FVector::Dist2D(Feet,Ground); Feet=Ground;
                    ApplyPose(Feet,CurrentYaw); SetClip(Walk);
                }
            }
        }
    }
    else if (GreetingRemaining>0.f) TickAction(DeltaSeconds);
    TickAgent(DeltaSeconds);
    if (bCareTest && !bTestFinished) TickCareTest(DeltaSeconds);
    if (bTest && !bTestFinished) TickInteractionTest(DeltaSeconds);
    if (bAgentTest && !bTestFinished) TickAgentTest(DeltaSeconds);
}
void APaitMeadowPet::TickInteractionTest(float DeltaSeconds)
{
    TestElapsed+=DeltaSeconds;
    if (TestElapsed>110.f) { FinishTest(TEXT("Navigation or interaction timed out: ")+Status); return; }
    if (!bReady || TestElapsed<8.f) return;
    if (!TestCamera)
    {
        TestCamera=GetWorld()->SpawnActor<ACameraActor>();
        TestCamera->GetCameraComponent()->SetFieldOfView(45.f);
        GetWorld()->GetFirstPlayerController()->SetViewTarget(TestCamera);
    }
    const FVector Target=Feet+FVector(0,0,45);
    TestCamera->SetActorLocation(Target+FVector(0,350,220));
    TestCamera->SetActorRotation((Target-TestCamera->GetActorLocation()).Rotation());
    FVector Ground;
    if (!GroundAt(Feet,Ground)) { FinishTest(TEXT("Lost ground contact")); return; }
    MaxGroundErrorCm=FMath::Max(MaxGroundErrorCm,static_cast<float>(FMath::Abs(Ground.Z-Feet.Z)));
    if (TestStage==0)
    {
        TestStart=Feet;
        bOutsideRejected=!RequestMove(FVector(100000,100000,0));
        for (const FVector& Offset : {FVector(350,0,0),FVector(-350,0,0),FVector(0,350,0),FVector(0,-350,0),FVector(250,250,0)})
            if (RequestMove(TestStart+Offset)) { TestDestination=Route.Last(); TestStage=1; break; }
        if (!TestStage) FinishTest(TEXT("No reachable test destination"));
    }
    else if (TestStage==1)
    {
        if (TravelCm>80.f && !bWalkingCaptured)
        { FScreenshotRequest::RequestScreenshot(EvidenceDir/TEXT("walking.png"),true,false); bWalkingCaptured=true; }
        if (Route.IsEmpty())
        {
            if (TravelCm<250.f || FVector::Dist2D(Feet,TestDestination)>10.f)
            { FinishTest(TEXT("Movement stopped before destination: ")+Status); return; }
            if (!RequestMove(TestStart)) { FinishTest(TEXT("Return path unavailable")); return; }
            TestStage=2;
        }
    }
    else if (TestStage==2 && Route.IsEmpty())
    {
        if (FVector::Dist2D(Feet,TestStart)>10.f) { FinishTest(TEXT("Return did not reach start")); return; }
        Greet(); TestStage=3;
    }
    else if (TestStage==3)
    {
        if (!bArrivalCaptured && GreetingRemaining<Greeting->GetPlayLength()*.6f)
        { FScreenshotRequest::RequestScreenshot(EvidenceDir/TEXT("greeting.png"),true,false); bArrivalCaptured=true; }
        if (GreetingRemaining<=0.f && TestElapsed>30.f) FinishTest(TEXT(""));
    }
}
void APaitMeadowPet::FinishTest(const FString& Error)
{
    bTestFinished=true;
    const bool Passed=Error.IsEmpty() && bOutsideRejected && TravelCm>500.f;
    TSharedRef<FJsonObject> Report=MakeShared<FJsonObject>();
    Report->SetBoolField(TEXT("passed"),Passed);
    Report->SetStringField(TEXT("error"),Error);
    Report->SetStringField(TEXT("actual_map"),GetWorld()->GetMapName());
    Report->SetNumberField(TEXT("elapsed_seconds"),TestElapsed);
    Report->SetNumberField(TEXT("travel_cm"),TravelCm);
    Report->SetNumberField(TEXT("max_root_ground_error_cm"),MaxGroundErrorCm);
    Report->SetNumberField(TEXT("root_lift_cm"),RootLift);
    Report->SetNumberField(TEXT("heading_offset_deg"),HeadingOffset);
    Report->SetStringField(TEXT("end_feet_cm"),Feet.ToString());
    Report->SetStringField(TEXT("test_start_cm"),TestStart.ToString());
    Report->SetStringField(TEXT("test_destination_cm"),TestDestination.ToString());
    Report->SetBoolField(TEXT("outside_destination_rejected"),bOutsideRejected);
    Report->SetBoolField(TEXT("manual_input_validated"),false);
    Report->SetBoolField(TEXT("performance_qualified"),false);
    FString Json; FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Json));
    const bool Saved=FFileHelper::SaveStringToFile(Json,*(EvidenceDir/TEXT("interaction.json")));
    FPlatformMisc::RequestExitWithStatus(false,Passed&&Saved?0:2);
}
