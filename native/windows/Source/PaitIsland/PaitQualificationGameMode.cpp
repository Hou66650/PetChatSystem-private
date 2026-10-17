#include "PaitQualificationGameMode.h"
#include "PaitPreviewPawn.h"
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
    if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
    {
        PC->bShowMouseCursor = true;
        FInputModeGameOnly Input;
        Input.SetConsumeCaptureMouseDown(false);
        PC->SetInputMode(Input);
    }
    UE_LOG(LogTemp, Display, TEXT("PAIT P0 | Adapter=%s | No account or cloud writes"),
        *GRHIAdapterName);
    bSmokeRun = FParse::Param(FCommandLine::Get(), TEXT("PaitSmoke"));
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
    DrawRect(FLinearColor(0.025f, .07f, .06f, .8f), 20.f, 20.f, 650.f, 106.f);
    DrawText(TEXT("PAIT ISLAND | P0 engine qualification only"), FLinearColor::White,
        36.f, 32.f, nullptr, 1.2f);
    DrawText(TEXT("RMB orbit | MMB pan | Wheel zoom | Home reset"), FLinearColor(.7f, .85f, .75f),
        36.f, 62.f, nullptr, 1.f);
    DrawText(FString::Printf(TEXT("GPU: %s | Not the final cat island"), *GRHIAdapterName),
        FLinearColor(.9f, .8f, .5f), 36.f, 91.f, nullptr, 1.f);
}
