#include "PaitQualificationGameMode.h"
#include "PaitPreviewPawn.h"
#include "PaitQualificationRun.h"
#include "PaitMeadowPet.h"
#include "Kismet/GameplayStatics.h"
#include "EngineUtils.h"
#include "Engine/Canvas.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "RHI.h"
#include "UnrealClient.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

APaitQualificationGameMode::APaitQualificationGameMode()
{
    DefaultPawnClass = APaitPreviewPawn::StaticClass();
    HUDClass = APaitQualificationHUD::StaticClass();
    PrimaryActorTick.bCanEverTick = true;
}
void APaitQualificationGameMode::BeginPlay()
{
    Super::BeginPlay();
    // Consume only once per process, so subsequent in-game island switches work.
    static bool StartupDestinationConsumed=false;
    if(!StartupDestinationConsumed)
    {
        StartupDestinationConsumed=true; FString Destination;
        if(FParse::Value(FCommandLine::Get(),TEXT("PaitIsland="),Destination) && Destination==TEXT("Sakura") &&
           !GetWorld()->GetMapName().Contains(TEXT("Sakura")))
        { UGameplayStatics::OpenLevel(this,TEXT("/Game/Preview/P1_SakuraV2")); return; }
    }
    if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
    {
        PC->bShowMouseCursor = true;
        FInputModeGameOnly Input;
        Input.SetConsumeCaptureMouseDown(false);
        PC->SetInputMode(Input);
    }
    UE_LOG(LogTemp, Display, TEXT("PAIT P0 | Adapter=%s | No account or cloud writes"),
        *GRHIAdapterName);
    if (FParse::Param(FCommandLine::Get(), TEXT("PaitQualification")))
    {
        GetWorld()->SpawnActor<APaitQualificationRun>();
        return;
    }
    bSmokeRun = FParse::Param(FCommandLine::Get(), TEXT("PaitSmoke"));
    if (GetWorld()->GetMapName().Contains(TEXT("P1_MeadowV2")) || GetWorld()->GetMapName().Contains(TEXT("P1_SakuraV2")))
        GetWorld()->SpawnActor<APaitMeadowPet>();
    if (bSmokeRun)
    {
        SmokeStarted = FPlatformTime::Seconds();
        FString EvidenceDir;
        if (!FParse::Value(FCommandLine::Get(), TEXT("PaitEvidenceDir="), EvidenceDir))
            EvidenceDir = FPaths::ProjectSavedDir() / TEXT("Qualification");
        SmokeScreenshot = FPaths::ConvertRelativePathToFull(EvidenceDir / TEXT("runtime-smoke.png"));
        IFileManager::Get().MakeDirectory(*FPaths::GetPath(SmokeScreenshot), true);
        // A previous screenshot must never make a new launch appear successful.
        if (IFileManager::Get().FileExists(*SmokeScreenshot) &&
            !IFileManager::Get().Delete(*SmokeScreenshot))
        {
            UE_LOG(LogTemp, Error, TEXT("PAIT_SMOKE_FAILED stale capture cannot be removed"));
            FPlatformMisc::RequestExitWithStatus(false, 2);
        }
    }
}
void APaitQualificationGameMode::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!bSmokeRun) return;
    ++SmokeFrames;
    const double Now = FPlatformTime::Seconds();
    if(Now-SmokeStarted>=29.0 && FParse::Param(FCommandLine::Get(),TEXT("PaitCleanCapture")))
        if(APlayerController* PC=GetWorld()->GetFirstPlayerController())
            if(AHUD* HUD=PC->GetHUD()) HUD->bShowHUD=false;
    if (!bCaptureRequested && Now - SmokeStarted >= 30.0 && SmokeFrames >= 120)
    {
        FScreenshotRequest::RequestScreenshot(SmokeScreenshot, true, false);
        CaptureRequestedAt = Now;
        bCaptureRequested = true;
        UE_LOG(LogTemp, Display, TEXT("PAIT_SMOKE_CAPTURE_REQUEST %s"), *SmokeScreenshot);
    }
    if (bCaptureRequested && Now - CaptureRequestedAt >= 3.0 &&
        IFileManager::Get().FileSize(*SmokeScreenshot) > 1024)
    {
        UE_LOG(LogTemp, Display, TEXT("PAIT_SMOKE_CAPTURE_SAVED frames=%llu adapter=%s; launch only, NOT performance qualification"),
            static_cast<unsigned long long>(SmokeFrames), *GRHIAdapterName);
        // Shipping disables normal logs: retain a small explicit evidence file.
        TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
        Report->SetStringField(TEXT("status"), TEXT("rendered_capture_saved"));
        Report->SetStringField(TEXT("actual_map"), GetWorld()->GetMapName());
        Report->SetStringField(TEXT("adapter"), GRHIAdapterName);
        Report->SetStringField(TEXT("screenshot"), SmokeScreenshot);
        Report->SetNumberField(TEXT("frames"), static_cast<double>(SmokeFrames));
        Report->SetBoolField(TEXT("performance_qualified"), false);
        FString Json;
        FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Json));
        const bool bSaved = FFileHelper::SaveStringToFile(Json,
            *(FPaths::GetPath(SmokeScreenshot) / TEXT("runtime-smoke.json")));
        bSmokeRun = false;
        FPlatformMisc::RequestExitWithStatus(false, bSaved ? 0 : 2);
    }
    else if (Now - SmokeStarted > 120.0)
    {
        UE_LOG(LogTemp, Error, TEXT("PAIT_SMOKE_FAILED no rendered capture within timeout"));
        bSmokeRun = false;
        FPlatformMisc::RequestExitWithStatus(false, 2);
    }
}
void APaitQualificationHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas) return;
    if(const APaitPreviewPawn* Pawn=Cast<APaitPreviewPawn>(GetOwningPawn()))
        if(!Pawn->LoadingIsland.IsEmpty())
        {
            DrawRect(FLinearColor(.05f,.12f,.1f,.85f),Canvas->ClipX*.25f,Canvas->ClipY*.45f,Canvas->ClipX*.5f,100);
            DrawText(TEXT("Loading island resources..."),FLinearColor::White,Canvas->ClipX*.25f+24,Canvas->ClipY*.45f+20,nullptr,1.2f);
            DrawRect(FLinearColor(.8f,.95f,.9f,.35f),Canvas->ClipX*.25f+24,Canvas->ClipY*.45f+62,Canvas->ClipX*.5f-48,8);
            return;
        }
    DrawRect(FLinearColor(0.025f, .07f, .06f, .8f), 20.f, 20.f, FMath::Min(1000.f,Canvas->ClipX-40.f), 244.f);
    const bool bMeadow = GetWorld()->GetMapName().Contains(TEXT("P1_"));
    DrawText(bMeadow ? *FString(TEXT("PAIT ISLAND | ")+GetWorld()->GetMapName()+TEXT(" - local preview")) : TEXT("PAIT ISLAND | P0 engine qualification only"), FLinearColor::White,
        36.f, 32.f, nullptr, 1.2f);
    DrawText(TEXT("RMB orbit | MMB pan | Wheel zoom | C pet | H hide | Home reset"), FLinearColor(.7f, .85f, .75f),
        36.f, 62.f, nullptr, 1.f);
    DrawText(FString::Printf(TEXT("GPU: %s | %s"), *GRHIAdapterName,
        bMeadow ? TEXT("Materials and gameplay in progress") : TEXT("Not the final cat island")),
        FLinearColor(.9f, .8f, .5f), 36.f, 91.f, nullptr, 1.f);
    if (bMeadow)
        for (TActorIterator<APaitMeadowPet> It(GetWorld()); It; ++It)
        {
            DrawText(It->GetStatus(),FLinearColor(.9f,.95f,.9f),36.f,118.f,nullptr,1.f);
            DrawText(TEXT("A autonomy on/off | P pet | R rest | G greet | Click ground to walk"),FLinearColor(.7f,.85f,.75f),36.f,144.f,nullptr,1.f);
            DrawText(It->GetAgentSummary(),FLinearColor(.9f,.8f,.5f),36.f,170.f,nullptr,.85f);
            DrawText(It->GetLastEvent(),FLinearColor(.8f,.9f,.85f),36.f,196.f,nullptr,1.f);
            DrawText(It->GetCareSummary(),FLinearColor(.9f,.9f,.7f),36.f,224.f,nullptr,1.f);
            if(APlayerController* PC=GetOwningPlayerController())
            {
                FHitResult Hit; float X=0,Y=0; PC->GetMousePosition(X,Y);
                if(Y>270 && Y<Canvas->ClipY-80 && PC->GetHitResultUnderCursor(ECC_Visibility,true,Hit))
                {
                    const FString Hint=It->CareHint(Hit.ImpactPoint);
                    if(!Hint.IsEmpty())
                    {
                        const float Left=FMath::Clamp(X+18.f,20.f,Canvas->ClipX-320.f);
                        DrawRect(FLinearColor(.06f,.14f,.12f,.8f),Left,Y+16,300,38);
                        DrawText(Hint,FLinearColor(.95f,.95f,.85f),Left+10,Y+26,nullptr,1.f);
                    }
                }
            }
            const TCHAR* Buttons[]={TEXT("Eat [F]"),TEXT("Drink [V]"),TEXT("Home [N]"),TEXT("Toy [T]"),TEXT("Pet [P]"),TEXT("Refill [B]"),TEXT("Meadow [1]"),TEXT("Sakura [2]")};
            for(int32 I=0;I<8;++I)
            {
                DrawRect(FLinearColor(.05f,.14f,.12f,.8f),20+I*100,Canvas->ClipY-70,96,50);
                DrawText(Buttons[I],FLinearColor(.95f,.9f,.75f),28+I*100,Canvas->ClipY-52,nullptr,1.f);
            }
            break;
        }
}
