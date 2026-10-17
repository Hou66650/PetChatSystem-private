#include "PaitMeadowPet.h"
#include "Animation/AnimSequence.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "UnrealClient.h"

// Native local policy: sense real surfaces -> choose a reachable destination ->
// execute -> record actual outcome. No LLM calls, accounts or economic writes.
void APaitMeadowPet::InitializeAgent()
{
    for (const TCHAR* Name : {TEXT("sniff"),TEXT("alert_scan"),TEXT("sit_down"),TEXT("sit_idle"),
                             TEXT("stand_up"),TEXT("touch_head"),TEXT("affection"),TEXT("paw_greeting")})
    {
        const FString N=FString(TEXT("cat"))+Name;
        AgentClips.Add(Name,LoadObject<UAnimSequence>(nullptr,
            *(TEXT("/Game/Imported/P0Cat/cat/SkeletalMeshes/")+N+TEXT(".")+N)));
    }
    AgentRandom.Initialize(bAgentTest ? 4217 : FMath::Rand());
    bAutonomy=!bTest;
    MemoryFile=(bAgentTest || bTest) ? EvidenceDir/TEXT("preview-memory.json") :
        FPaths::ProjectSavedDir()/TEXT("Preview/MeadowV2/agent-memory.json");
    // Only this isolated preview's map-scoped visit counters survive restart.
    // No offline hunger penalty or production account state is loaded.
    FString Json; TSharedPtr<FJsonObject> Root;
    if (!bTest && !bAgentTest && IFileManager::Get().FileSize(*MemoryFile)<65536 &&
        FFileHelper::LoadFileToString(Json,*MemoryFile) &&
        FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),Root) && Root)
    {
        FString Map; double Schema=0;
        const TSharedPtr<FJsonObject>* Stored=nullptr;
        if (Root->TryGetStringField(TEXT("map"),Map) && Map==TEXT("P1_MeadowV2") &&
            Root->TryGetNumberField(TEXT("schema"),Schema) && Schema==1 &&
            Root->TryGetObjectField(TEXT("visits"),Stored) && (*Stored)->Values.Num()<=128)
            for (const auto& Pair : (*Stored)->Values)
            {
                double Count=0;
                if (Pair.Key.Len()<48 && Pair.Value->TryGetNumber(Count) && FMath::IsFinite(Count) && Count>=0 && Count<=9999)
                    Visits.Add(FString(Pair.Key.ToView()),static_cast<int32>(Count));
            }
    }
}
void APaitMeadowPet::EndPlay(const EEndPlayReason::Type Reason)
{
    if (!bTest && !bAgentTest) SaveMemory();
    Super::EndPlay(Reason);
}
FString APaitMeadowPet::CellAt(const FVector& Point) const
{
    return FString::Printf(TEXT("%d:%d"),FMath::FloorToInt(Point.X/200.f),FMath::FloorToInt(Point.Y/200.f));
}
FString APaitMeadowPet::PlaceAt(const FVector& Point) const
{
    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(PaitPlace),true);
    if (GetWorld()->LineTraceSingleByChannel(Hit,Point+FVector(0,0,160),Point-FVector(0,0,240),ECC_Visibility,Params))
        if (const UStaticMeshComponent* C=Cast<UStaticMeshComponent>(Hit.GetComponent()))
            if (C->GetStaticMesh())
            {
                const FString N=C->GetStaticMesh()->GetName();
                if (N.Contains(TEXT("Farm_terrace"))) return TEXT("Garden terrace");
                if (N.Contains(TEXT("cat_home"))) return TEXT("Cat shelter");
                if (N.Contains(TEXT("bridge"))) return TEXT("Stone bridge");
                if (N.Contains(TEXT("Conservatory"))) return TEXT("Greenhouse");
                if (N.Contains(TEXT("Cloud_meadow"))) return TEXT("Meadow");
                if (N.Contains(TEXT("Mistwood"))) return TEXT("Forest clearing");
            }
    return TEXT("Island ground");
}
void APaitMeadowPet::Remember(const FString& Action,const FString& Outcome)
{
    TSharedRef<FJsonObject> E=MakeShared<FJsonObject>();
    E->SetNumberField(TEXT("session_seconds"),AgentClock);
    E->SetStringField(TEXT("action"),Action);
    E->SetStringField(TEXT("outcome"),Outcome);
    E->SetStringField(TEXT("source"),bAgentAction ? TEXT("local_policy") : TEXT("player"));
    E->SetStringField(TEXT("place"),PlaceAt(Feet));
    E->SetStringField(TEXT("position_cm"),Feet.ToString());
    AgentEvents.Add(MakeShared<FJsonValueObject>(E));
    if (AgentEvents.Num()>64) AgentEvents.RemoveAt(0);
}
void APaitMeadowPet::SaveMemory() const
{
    if (bTest) return;
    TSharedRef<FJsonObject> Root=MakeShared<FJsonObject>(), Stored=MakeShared<FJsonObject>();
    for (const auto& Pair : Visits) Stored->SetNumberField(Pair.Key,Pair.Value);
    Root->SetNumberField(TEXT("schema"),1);
    Root->SetStringField(TEXT("map"),TEXT("P1_MeadowV2"));
    Root->SetStringField(TEXT("scope"),TEXT("isolated_local_preview_not_account_memory"));
    Root->SetObjectField(TEXT("visits"),Stored);
    FString Json; FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Json));
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(MemoryFile),true);
    const FString Temp=MemoryFile+TEXT(".tmp");
    if (FFileHelper::SaveStringToFile(Json,*Temp))
        IFileManager::Get().Move(*MemoryFile,*Temp,true);
}
void APaitMeadowPet::InterruptAction(const FString& Reason)
{
    if (!ActiveAction.IsEmpty()) Remember(ActiveAction,Reason);
    ActiveAction.Empty(); Route.Reset(); ActionSteps.Reset(); GreetingRemaining=0;
    bAgentRoute=false; bAgentAction=false;
}
void APaitMeadowPet::StartAction(const FString& Action,bool FromAgent)
{
    if (!bReady) return;
    InterruptAction(TEXT("interrupted"));
    auto Add=[this](const TCHAR* Name,float Duration=0.f,bool Loop=false)
    {
        const TObjectPtr<UAnimSequence>* Clip=AgentClips.Find(Name);
        if (Clip && *Clip) ActionSteps.Add({Name,Duration>0 ? Duration : (*Clip)->GetPlayLength(),Loop});
    };
    // The imported sleep loop is not a complete grounded lying pose. Use the
    // source's foot-corrected seated sequence until a proper sleep rig is baked.
    if (Action==TEXT("rest")) { Add(TEXT("sit_down")); Add(TEXT("sit_idle"),8.f,true); Add(TEXT("stand_up")); }
    else if (Action==TEXT("pet")) { Add(TEXT("touch_head")); Add(TEXT("affection")); }
    else if (Action==TEXT("greet")) Add(TEXT("paw_greeting"));
    else if (Action==TEXT("sniff")) Add(TEXT("sniff"));
    else Add(TEXT("alert_scan"));
    if (ActionSteps.IsEmpty()) { SetClip(Idle); NextDecision=AgentClock+8; return; }
    ActiveAction=Action; bAgentAction=FromAgent; ActionStep=0;
    for (const FActionStep& Step : ActionSteps) GreetingRemaining+=Step.Seconds;
    ActionStepRemaining=ActionSteps[0].Seconds;
    CurrentClip=nullptr; SetClip(AgentClips[ActionSteps[0].Clip],ActionSteps[0].Loop);
    if (!FromAgent) PlayerLeaseUntil=AgentClock+GreetingRemaining+15.f;
    Status=Action==TEXT("rest") ? TEXT("Resting here on safe ground") :
        Action==TEXT("pet") ? TEXT("Leaning into your touch") :
        Action==TEXT("sniff") ? TEXT("Sniffing: ")+PlaceAt(Feet) :
        Action==TEXT("greet") ? TEXT("Hello! A little paw greeting") : TEXT("Listening to the island");
    Remember(Action,TEXT("started"));
}
void APaitMeadowPet::TickAction(float Dt)
{
    GreetingRemaining=FMath::Max(0.f,GreetingRemaining-Dt);
    ActionStepRemaining-=Dt;
    if (ActiveAction==TEXT("rest")) Energy=FMath::Min(1.f,Energy+Dt*.035f);
    if (ActionStepRemaining>0) return;
    ++ActionStep;
    if (ActionSteps.IsValidIndex(ActionStep))
    {
        ActionStepRemaining=ActionSteps[ActionStep].Seconds;
        CurrentClip=nullptr; SetClip(AgentClips[ActionSteps[ActionStep].Clip],ActionSteps[ActionStep].Loop);
        // Keep the total timer positive when a slow frame crosses a step.
        GreetingRemaining=ActionStepRemaining;
        for (int32 I=ActionStep+1;I<ActionSteps.Num();++I) GreetingRemaining+=ActionSteps[I].Seconds;
        return;
    }
    Remember(ActiveAction,TEXT("completed"));
    if (ActiveAction==TEXT("rest")) ++CompletedRests;
    if (ActiveAction==TEXT("pet")) ++CompletedPets;
    if (ActiveAction==TEXT("sniff") && bAgentAction) { ++CompletedExplorations; Curiosity=FMath::Max(0.f,Curiosity-.22f); }
    ActiveAction.Empty(); ActionSteps.Reset(); GreetingRemaining=0; SetClip(Idle);
    bAgentAction=false; NextDecision=AgentClock+AgentRandom.FRandRange(5.f,9.f);
    Status=TEXT("Taking a quiet moment");
}
void APaitMeadowPet::Arrived()
{
    Remember(TEXT("walk"),TEXT("completed")); ActiveAction.Empty();
    LastCell=CellAt(Feet);
    if (Visits.Contains(LastCell) || Visits.Num()<128)
        Visits.FindOrAdd(LastCell)=FMath::Min(9999,Visits.FindRef(LastCell)+1);
    SaveMemory();
    if (bAgentRoute) { bAgentRoute=false; StartAction(TEXT("sniff"),true); }
    else { SetClip(Idle); PlayerLeaseUntil=AgentClock+15; Status=TEXT("Arrived at your chosen spot"); }
}
void APaitMeadowPet::Blocked()
{
    Remember(TEXT("walk"),TEXT("blocked"));
    if (!TargetCell.IsEmpty()) BlockedCells.Add(TargetCell,AgentClock+60.f);
    ActiveAction.Empty(); bAgentRoute=false; SetClip(Idle);
    NextDecision=AgentClock+8; Status=TEXT("Stopped at an unsafe edge; choosing another route");
}
void APaitMeadowPet::Pet() { StartAction(TEXT("pet"),false); }
void APaitMeadowPet::Rest() { StartAction(TEXT("rest"),false); }
void APaitMeadowPet::ToggleAutonomy()
{
    bAutonomy=!bAutonomy;
    if (!bAutonomy && (bAgentRoute || bAgentAction)) { InterruptAction(TEXT("paused")); SetClip(Idle); }
    NextDecision=AgentClock+3.f;
    AgentReason=bAutonomy ? TEXT("Autonomy resumed") : TEXT("Autonomy paused by you");
}
void APaitMeadowPet::TickAgent(float Dt)
{
    AgentClock+=Dt;
    if (!bReady || bTest) return;
    const float LifeDt=FMath::Min(Dt,.25f); // a stalled/background frame is not hours of neglect
    Energy=FMath::Max(.15f,Energy-LifeDt*(Route.IsEmpty()?.00035f:.001f));
    Curiosity=FMath::Min(1.f,Curiosity+LifeDt*.003f);
    if (!bAutonomy || !ActiveAction.IsEmpty() || !Route.IsEmpty() ||
        AgentClock<PlayerLeaseUntil || AgentClock<NextDecision) return;
    NextDecision=AgentClock+8.f;
    for (auto It=BlockedCells.CreateIterator();It;++It) if (It.Value()<=AgentClock) It.RemoveCurrent();
    if (Energy<.3f) { AgentReason=TEXT("Energy is low; resting before exploring"); StartAction(TEXT("rest"),true); return; }
    if (Curiosity<.35f) { AgentReason=TEXT("Recently explored; taking time to listen"); StartAction(TEXT("observe"),true); return; }
    struct FCandidate { FVector Position; FString Cell; float Score; };
    TArray<FCandidate> Candidates;
    // Ground truth is the current UE scene, never the old web map coordinates.
    const float Rotation=AgentRandom.FRandRange(0.f,45.f);
    for (int32 I=0;I<8;++I)
    {
        const float Angle=FMath::DegreesToRadians(Rotation+I*45.f);
        const FVector P=Feet+FVector(FMath::Cos(Angle),FMath::Sin(Angle),0)*300.f;
        const FString Cell=CellAt(P);
        if (BlockedCells.Contains(Cell)) continue;
        Candidates.Add({P,Cell,static_cast<float>(Visits.FindRef(Cell))*4.f+(Cell==LastCell?8.f:0.f)+AgentRandom.FRand()});
    }
    Candidates.Sort([](const FCandidate& A,const FCandidate& B){ return A.Score<B.Score; });
    int32 Tried=0;
    for (const FCandidate& Candidate : Candidates)
    {
        if (++Tried>4) break; // bounded expensive nav/physics work per decision
        if (RequestMove(Candidate.Position,true))
        { AgentReason=TEXT("Curious about a less-visited reachable patch"); return; }
        BlockedCells.Add(Candidate.Cell,AgentClock+45.f);
    }
    AgentReason=TEXT("Nearby routes blocked; observing here, then trying another direction");
    StartAction(TEXT("observe"),true);
}
FString APaitMeadowPet::GetAgentSummary() const
{
    return FString::Printf(TEXT("Local Agent: %s | Energy %.0f%% | Explored %d | %s"),
        !bAutonomy?TEXT("paused"):AgentClock<PlayerLeaseUntil?TEXT("your turn"):TEXT("autonomous"),
        Energy*100.f,CompletedExplorations,*AgentReason);
}
FString APaitMeadowPet::GetLastEvent() const
{
    if (AgentEvents.IsEmpty()) return TEXT("A autonomy | P pet | R rest | G greet | Click ground to walk");
    const TSharedPtr<FJsonObject> E=AgentEvents.Last()->AsObject();
    return E->GetStringField(TEXT("place"))+TEXT(" / ")+E->GetStringField(TEXT("action"))+TEXT(" / ")+E->GetStringField(TEXT("outcome"));
}

// Real packaged-runtime check of planning -> physical movement -> outcome,
// player override, pause/resume, fatigue rest, affection and persisted visits.
void APaitMeadowPet::TickAgentTest(float Dt)
{
    TestElapsed+=Dt;
    if (TestElapsed>150.f) { FinishAgentTest(TEXT("Agent sequence timed out: ")+Status); return; }
    if (!bReady) return;
    if (!TestCamera)
    {
        TestCamera=GetWorld()->SpawnActor<ACameraActor>();
        TestCamera->GetCameraComponent()->SetFieldOfView(45.f);
        GetWorld()->GetFirstPlayerController()->SetViewTarget(TestCamera);
    }
    const FVector Target=Feet+FVector(0,0,40);
    TestCamera->SetActorLocation(Target+FVector(0,350,220));
    TestCamera->SetActorRotation((Target-TestCamera->GetActorLocation()).Rotation());
    if (AgentTestStage==0 && bAgentRoute && TravelCm>40.f)
    {
        Greet();
        if (!Route.IsEmpty() || bAgentAction) { FinishAgentTest(TEXT("Player override failed")); return; }
        AgentTestStage=1; AgentTestStageStarted=AgentClock;
    }
    else if (AgentTestStage==1 && AgentClock-AgentTestStageStarted>7.f)
    {
        bPlayerPriorityVerified=!bAgentRoute && AgentClock<PlayerLeaseUntil;
        if (!bPlayerPriorityVerified) { FinishAgentTest(TEXT("Autonomy stole player control")); return; }
        ToggleAutonomy(); AgentTestPausePosition=Feet; AgentTestStage=2; AgentTestStageStarted=AgentClock;
    }
    else if (AgentTestStage==2 && AgentClock-AgentTestStageStarted>5.f)
    {
        bPauseVerified=!bAutonomy && FVector::Dist(Feet,AgentTestPausePosition)<.01f;
        if (!bPauseVerified) { FinishAgentTest(TEXT("Pause did not stop autonomy")); return; }
        ToggleAutonomy(); AgentTestStage=3;
    }
    else if (AgentTestStage==3 && CompletedExplorations>0)
    {
        FScreenshotRequest::RequestScreenshot(EvidenceDir/TEXT("agent-exploring.png"),true,false);
        Energy=.2f; RestEnergyBefore=Energy; AgentTestStage=4;
    }
    else if (AgentTestStage==4 && ActiveAction==TEXT("rest") && ActionStep==1 && ActionStepRemaining<6.f)
    {
        FScreenshotRequest::RequestScreenshot(EvidenceDir/TEXT("agent-resting.png"),true,false);
        AgentTestStage=5;
    }
    else if (AgentTestStage==5 && CompletedRests>0)
    {
        if (Energy<=RestEnergyBefore) { FinishAgentTest(TEXT("Rest did not restore energy")); return; }
        Pet(); AgentTestStage=6;
    }
    else if (AgentTestStage==6 && CompletedPets>0)
    {
        SaveMemory(); FString Saved; TSharedPtr<FJsonObject> Data;
        if (FFileHelper::LoadFileToString(Saved,*MemoryFile) &&
            FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Saved),Data) && Data)
        {
            const TSharedPtr<FJsonObject>* Stored=nullptr;
            bMemoryVerified=Data->TryGetObjectField(TEXT("visits"),Stored) && (*Stored)->Values.Num()==Visits.Num() && !Visits.IsEmpty();
            if (bMemoryVerified) for (const auto& Pair : Visits)
            { double Count=0; if (!(*Stored)->TryGetNumberField(Pair.Key,Count) || Count!=Pair.Value) bMemoryVerified=false; }
        }
        FinishAgentTest(bMemoryVerified ? TEXT("") : TEXT("Visit memory did not persist"));
    }
}
void APaitMeadowPet::FinishAgentTest(const FString& Error)
{
    bTestFinished=true;
    const bool Passed=Error.IsEmpty() && bPlayerPriorityVerified && bPauseVerified && bMemoryVerified &&
        CompletedExplorations>0 && CompletedRests>0 && CompletedPets>0;
    TSharedRef<FJsonObject> R=MakeShared<FJsonObject>();
    R->SetBoolField(TEXT("passed"),Passed); R->SetStringField(TEXT("error"),Error);
    R->SetStringField(TEXT("actual_map"),GetWorld()->GetMapName());
    R->SetStringField(TEXT("decision_source"),TEXT("native_local_policy_no_cloud_model"));
    R->SetNumberField(TEXT("elapsed_seconds"),TestElapsed); R->SetNumberField(TEXT("travel_cm"),TravelCm);
    R->SetNumberField(TEXT("completed_explorations"),CompletedExplorations);
    R->SetNumberField(TEXT("completed_rests"),CompletedRests); R->SetNumberField(TEXT("completed_pet_responses"),CompletedPets);
    R->SetBoolField(TEXT("player_priority"),bPlayerPriorityVerified); R->SetBoolField(TEXT("pause_resume"),bPauseVerified);
    R->SetBoolField(TEXT("visit_memory_disk_roundtrip"),bMemoryVerified);
    R->SetBoolField(TEXT("manual_input_validated"),false); R->SetBoolField(TEXT("performance_qualified"),false);
    R->SetArrayField(TEXT("events"),AgentEvents);
    FString Json; FJsonSerializer::Serialize(R,TJsonWriterFactory<>::Create(&Json));
    const bool Saved=FFileHelper::SaveStringToFile(Json,*(EvidenceDir/TEXT("agent.json")));
    FPlatformMisc::RequestExitWithStatus(false,Passed&&Saved?0:2);
}
