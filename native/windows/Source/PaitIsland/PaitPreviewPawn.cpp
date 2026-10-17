#include "PaitPreviewPawn.h"
#include "PaitMeadowPet.h"
#include "Kismet/GameplayStatics.h"
#include "Camera/CameraComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Animation/SkeletalMeshActor.h"
#include "GameFramework/HUD.h"
#include "Components/InputComponent.h"
#include "InputCoreTypes.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

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
    // Scripted runtime checks call the same gameplay functions directly.
    // Do not let desktop clicks contaminate an unattended action sequence.
    for(const TCHAR* Flag:{TEXT("PaitMeadowTest"),TEXT("PaitAgentTest"),TEXT("PaitCareTest"),TEXT("PaitSmoke")})
        if(FParse::Param(FCommandLine::Get(),Flag)) return;
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
    Input->BindKey(EKeys::F, IE_Pressed, this, &APaitPreviewPawn::Eat);
    Input->BindKey(EKeys::V, IE_Pressed, this, &APaitPreviewPawn::Drink);
    Input->BindKey(EKeys::N, IE_Pressed, this, &APaitPreviewPawn::GoHome);
    Input->BindKey(EKeys::T, IE_Pressed, this, &APaitPreviewPawn::Play);
    Input->BindKey(EKeys::B, IE_Pressed, this, &APaitPreviewPawn::FillBowls);
    Input->BindKey(EKeys::One, IE_Pressed, this, &APaitPreviewPawn::Meadow);
    Input->BindKey(EKeys::Two, IE_Pressed, this, &APaitPreviewPawn::Sakura);
    Input->BindKey(EKeys::A, IE_Pressed, this, &APaitPreviewPawn::ToggleAgent);
}
void APaitPreviewPawn::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(!LoadingIsland.IsEmpty())
    {
        IslandLoadDelay-=DeltaSeconds;
        if(IslandLoadDelay<=0) { const FString Map=LoadingIsland; LoadingIsland.Empty(); UGameplayStatics::OpenLevel(this,FName(*Map)); return; }
    }
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
    if(GetWorld()->GetMapName().Contains(TEXT("Sakura")))
    { SetActorLocation(FVector(-300,-650,180)); TargetDistance=6500; Pitch=-32; Yaw=55; }
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
    if(!PC) return;
    float X=0,Y=0; PC->GetMousePosition(X,Y);
    int32 W=0,H=0; PC->GetViewportSize(W,H);
    if(PC->GetHUD() && PC->GetHUD()->bShowHUD && Y>H-70 && Y<H-20 && X>=20 && X<820)
    {
        const int32 Button=static_cast<int32>((X-20)/100);
        if(Button==0) Eat(); else if(Button==1) Drink(); else if(Button==2) GoHome();
        else if(Button==3) Play(); else if(Button==4) PetCat(); else if(Button==5) FillBowls();
        else if(Button==6) Meadow(); else if(Button==7) Sakura();
        return;
    }
    if(PC->GetHUD() && PC->GetHUD()->bShowHUD && Y<270 && X<1020) return;
    FHitResult Hit;
    if (!PC->GetHitResultUnderCursor(ECC_Visibility,true,Hit) || !Hit.GetActor()) return;
    for (TActorIterator<APaitMeadowPet> It(GetWorld()); It; ++It)
    {
        if(It->CareAt(Hit.ImpactPoint)) return;
        if(Hit.GetActor()->ActorHasTag(TEXT("PaitGround"))) It->RequestMove(Hit.ImpactPoint);
        break;
    }
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

void APaitPreviewPawn::Eat() { for(TActorIterator<APaitMeadowPet> It(GetWorld());It;++It) { It->Care(TEXT("food")); break; } }
void APaitPreviewPawn::Drink() { for(TActorIterator<APaitMeadowPet> It(GetWorld());It;++It) { It->Care(TEXT("water")); break; } }
void APaitPreviewPawn::GoHome() { for(TActorIterator<APaitMeadowPet> It(GetWorld());It;++It) { It->Care(TEXT("home")); break; } }
void APaitPreviewPawn::Play() { for(TActorIterator<APaitMeadowPet> It(GetWorld());It;++It) { It->Care(TEXT("toy")); break; } }
void APaitPreviewPawn::FillBowls() { for(TActorIterator<APaitMeadowPet> It(GetWorld());It;++It) { It->Refill(); break; } }
void APaitPreviewPawn::Meadow() { if(!GetWorld()->GetMapName().Contains(TEXT("Meadow"))) { LoadingIsland=TEXT("/Game/Preview/P1_MeadowV2"); IslandLoadDelay=.2f; } }
void APaitPreviewPawn::Sakura() { if(!GetWorld()->GetMapName().Contains(TEXT("Sakura"))) { LoadingIsland=TEXT("/Game/Preview/P1_SakuraV2"); IslandLoadDelay=.2f; } }
