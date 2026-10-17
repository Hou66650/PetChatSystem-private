#include "PaitQualificationGameMode.h"
#include "PaitPreviewPawn.h"
#include "Engine/Canvas.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "RHI.h"

APaitQualificationGameMode::APaitQualificationGameMode()
{
    DefaultPawnClass = APaitPreviewPawn::StaticClass();
    HUDClass = APaitQualificationHUD::StaticClass();
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
