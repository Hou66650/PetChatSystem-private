#include "PaitPreviewPawn.h"
#include "PaitMeadowPet.h"
#include "Camera/CameraComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Animation/SkeletalMeshActor.h"
#include "GameFramework/HUD.h"
#include "Components/InputComponent.h"
#include "InputCoreTypes.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"

APaitPreviewPawn::APaitPreviewPawn()
{
    PrimaryActorTick.bCanEverTick = true;
    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
    Arm = CreateDefaultSubobject<USpringArmComponent>(TEXT("OrbitArm"));
    Arm->SetupAttachment(RootComponent);
    Arm->bDoCollisionTest = false;
    Arm->TargetArmLength = TargetDistance;
    Arm->SetRelativeRotation(FRotator(Pitch, Yaw, 0.f));
    Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
    Camera->SetupAttachment(Arm, USpringArmComponent::SocketName);
    Camera->FieldOfView = 50.f;
}
void APaitPreviewPawn::BeginPlay()
{
    Super::BeginPlay();
    ResetView();
    Arm->TargetArmLength = TargetDistance;
}
void APaitPreviewPawn::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    Input->BindAxis(TEXT("LookX"), this, &APaitPreviewPawn::Horizontal);
    Input->BindAxis(TEXT("LookY"), this, &APaitPreviewPawn::Vertical);
    Input->BindAxis(TEXT("Zoom"), this, &APaitPreviewPawn::Zoom);
    Input->BindAction(TEXT("Orbit"), IE_Pressed, this, &APaitPreviewPawn::StartOrbit);
    Input->BindAction(TEXT("Orbit"), IE_Released, this, &APaitPreviewPawn::StopOrbit);
    Input->BindAction(TEXT("Pan"), IE_Pressed, this, &APaitPreviewPawn::StartPan);
    Input->BindAction(TEXT("Pan"), IE_Released, this, &APaitPreviewPawn::StopPan);
    Input->BindAction(TEXT("ResetView"), IE_Pressed, this, &APaitPreviewPawn::ResetView);
    Input->BindKey(EKeys::C, IE_Pressed, this, &APaitPreviewPawn::FocusPet);
    Input->BindKey(EKeys::H, IE_Pressed, this, &APaitPreviewPawn::ToggleInterface);
    Input->BindKey(EKeys::LeftMouseButton, IE_Pressed, this, &APaitPreviewPawn::MovePetToCursor);
    Input->BindKey(EKeys::G, IE_Pressed, this, &APaitPreviewPawn::GreetPet);
    Input->BindKey(EKeys::P, IE_Pressed, this, &APaitPreviewPawn::PetCat);
    Input->BindKey(EKeys::R, IE_Pressed, this, &APaitPreviewPawn::RestPet);
    Input->BindKey(EKeys::A, IE_Pressed, this, &APaitPreviewPawn::ToggleAgent);
}
void APaitPreviewPawn::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    // Exponential smoothing keeps zoom time consistent across frame rates.
    const float Alpha = 1.f - FMath::Exp(-12.f * DeltaSeconds);
    Arm->TargetArmLength = FMath::Lerp(Arm->TargetArmLength, TargetDistance, Alpha);
    if (const APlayerController* PC = Cast<APlayerController>(Controller))
    {
        if (!PC->IsInputKeyDown(EKeys::RightMouseButton)) bOrbit = false;
        if (!PC->IsInputKeyDown(EKeys::MiddleMouseButton)) bPan = false;
    }
    UpdateCursor();
}
void APaitPreviewPawn::Horizontal(float Value)
{
    // Mouse deltas already integrate motion; do not multiply by DeltaSeconds.
    if (bPan)
        SetActorLocation(GetActorLocation() + Camera->GetRightVector() * -Value * TargetDistance * .0008f);
    else if (bOrbit) Yaw += Value * .25f;
    Arm->SetRelativeRotation(FRotator(Pitch, Yaw, 0.f));
}
void APaitPreviewPawn::Vertical(float Value)
{
    if (bPan)
        SetActorLocation(GetActorLocation() + Camera->GetUpVector() * -Value * TargetDistance * .0008f);
    else if (bOrbit) Pitch = FMath::Clamp(Pitch - Value * .25f, -80.f, -5.f);
    Arm->SetRelativeRotation(FRotator(Pitch, Yaw, 0.f));
}
void APaitPreviewPawn::Zoom(float Value)
{
    TargetDistance = FMath::Clamp(TargetDistance * FMath::Exp(-Value * .12f), 250.f, 8000.f);
}
void APaitPreviewPawn::StartOrbit() { bOrbit = true; UpdateCursor(); }
void APaitPreviewPawn::StopOrbit() { bOrbit = false; UpdateCursor(); }
void APaitPreviewPawn::StartPan() { bPan = true; UpdateCursor(); }
void APaitPreviewPawn::StopPan() { bPan = false; UpdateCursor(); }
void APaitPreviewPawn::UpdateCursor()
{
    if (APlayerController* PC = Cast<APlayerController>(Controller))
        PC->bShowMouseCursor = !(bOrbit || bPan);
}
void APaitPreviewPawn::ResetView()
{
    const bool bMeadow = GetWorld() && GetWorld()->GetMapName().Contains(TEXT("P1_MeadowV2"));
    SetActorLocation(bMeadow ? FVector(200.f, 200.f, 150.f) : FVector(0.f, 0.f, 150.f));
    Yaw = -45.f;
    Pitch = bMeadow ? -34.f : -28.f;
    TargetDistance = bMeadow ? 5600.f : 2200.f;
    Arm->SetRelativeRotation(FRotator(Pitch, Yaw, 0.f));
}
void APaitPreviewPawn::FocusPet()
{
    for (TActorIterator<ASkeletalMeshActor> It(GetWorld()); It; ++It)
    {
        SetActorLocation(It->GetActorLocation() + FVector(0.f, 0.f, 65.f));
        TargetDistance = 400.f;
        Pitch = -18.f;
        Arm->SetRelativeRotation(FRotator(Pitch, Yaw, 0.f));
        break;
    }
}
void APaitPreviewPawn::ToggleInterface()
{
    if (APlayerController* PC = Cast<APlayerController>(Controller))
        if (AHUD* HUD = PC->GetHUD()) HUD->bShowHUD = !HUD->bShowHUD;
}
void APaitPreviewPawn::MovePetToCursor()
{
    if (bOrbit || bPan) return;
    APlayerController* PC=Cast<APlayerController>(Controller);
    FHitResult Hit;
    if (!PC || !PC->GetHitResultUnderCursor(ECC_Visibility,true,Hit) || !Hit.GetActor() ||
        !Hit.GetActor()->ActorHasTag(TEXT("PaitGround"))) return;
    for (TActorIterator<APaitMeadowPet> It(GetWorld()); It; ++It) { It->RequestMove(Hit.ImpactPoint); break; }
}
void APaitPreviewPawn::GreetPet()
{
    for (TActorIterator<APaitMeadowPet> It(GetWorld()); It; ++It) { It->Greet(); break; }
}
void APaitPreviewPawn::PetCat()
{
    for (TActorIterator<APaitMeadowPet> It(GetWorld()); It; ++It) { It->Pet(); break; }
}
void APaitPreviewPawn::RestPet()
{
    for (TActorIterator<APaitMeadowPet> It(GetWorld()); It; ++It) { It->Rest(); break; }
}
void APaitPreviewPawn::ToggleAgent()
{
    for (TActorIterator<APaitMeadowPet> It(GetWorld()); It; ++It) { It->ToggleAutonomy(); break; }
}
