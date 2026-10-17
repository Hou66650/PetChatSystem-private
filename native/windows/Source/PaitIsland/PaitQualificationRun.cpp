#include "PaitQualificationRun.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/SkeletalMeshActor.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "RHI.h"
#include "UnrealClient.h"

namespace
{
    const TCHAR* ShotNames[] = {TEXT("01-cat-portrait"), TEXT("02-cat-walk"),
        TEXT("03-cat-trot"), TEXT("04-glass-outside"), TEXT("05-glass-inside"), TEXT("06-overview")};
    const TCHAR* ClipNames[] = {TEXT("idle_breathe"), TEXT("walk"), TEXT("trot")};
}

APaitQualificationRun::APaitQualificationRun()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostUpdateWork;
}

void APaitQualificationRun::BeginPlay()
{
    Super::BeginPlay();
    Started = FPlatformTime::Seconds();
    FParse::Value(FCommandLine::Get(), TEXT("PaitQualificationSeconds="), Duration);
    Duration = FMath::Clamp(Duration, 90.0, 600.0);
    if (!FParse::Value(FCommandLine::Get(), TEXT("PaitEvidenceDir="), EvidenceDir))
        EvidenceDir = FPaths::ProjectSavedDir() / TEXT("Qualification") / FGuid::NewGuid().ToString();
    EvidenceDir = FPaths::ConvertRelativePathToFull(EvidenceDir);
    IFileManager::Get().MakeDirectory(*EvidenceDir, true);
    if (IFileManager::Get().FileExists(*(EvidenceDir / TEXT("qualification.json"))))
    {
        bFinished = true;
        FPlatformMisc::RequestExitWithStatus(false, 2);
        return;
    }
    for (TActorIterator<ASkeletalMeshActor> It(GetWorld()); It; ++It)
    {
        USkeletalMeshComponent* Component = It->GetSkeletalMeshComponent();
        if (Component->GetSkeletalMeshAsset() && Component->GetSkeletalMeshAsset()->GetPathName().StartsWith(TEXT("/Game/Imported/P0Cat/")))
        {
            Component->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
            Cats.Add(*It);
        }
    }
    Cats.Sort([](const ASkeletalMeshActor& A, const ASkeletalMeshActor& B) {
        return A.GetSkeletalMeshComponent()->GetSkeletalMeshAsset()->GetName() < B.GetSkeletalMeshComponent()->GetSkeletalMeshAsset()->GetName();
    });
    if (Cats.Num() != 3) { Finish(TEXT("Expected three standard-cat mesh layers")); return; }
    OriginalCatPosition = Cats[0]->GetActorLocation();
    bool bGlassFound = false;
    for (TActorIterator<AStaticMeshActor> It(GetWorld()); It; ++It)
    {
        const UStaticMeshComponent* Component = It->GetStaticMeshComponent();
        if (Component->GetStaticMesh() && Component->GetStaticMesh()->GetName().StartsWith(TEXT("Individual_glazing")))
        {
            GreenhouseCenter = Component->Bounds.Origin;
            bGlassFound = true;
            break;
        }
    }
    if (!bGlassFound) { Finish(TEXT("Missing greenhouse glazing fixture")); return; }
    for (const TCHAR* Clip : ClipNames)
    {
        const FString Name = FString(TEXT("cat")) + Clip;
        UAnimSequence* Asset = LoadObject<UAnimSequence>(nullptr,
            *(TEXT("/Game/Imported/P0Cat/cat/SkeletalMeshes/") + Name + TEXT(".") + Name));
        if (!Asset) { Finish(TEXT("Missing cooked animation: ") + Name); return; }
        Clips.Add(Asset);
    }
    Camera = GetWorld()->SpawnActor<ACameraActor>();
    if (!Camera || !GetWorld()->GetFirstPlayerController()) { Finish(TEXT("Camera/controller missing")); return; }
    Camera->GetCameraComponent()->SetFieldOfView(45.f);
    GetWorld()->GetFirstPlayerController()->SetViewTarget(Camera);
    EnterShot(0);
}

void APaitQualificationRun::EnterShot(int32 Index)
{
    Shot = Index;
    ShotStarted = FPlatformTime::Seconds();
    bFirstCapture = bSecondCapture = false;
    PreviousPose.Reset();
    const FVector CatPosition = Index >= 3 && Index <= 4
        ? FVector(GreenhouseCenter.X, GreenhouseCenter.Y, OriginalCatPosition.Z + 10.f) : OriginalCatPosition;
    for (ASkeletalMeshActor* Cat : Cats)
    {
        Cat->SetActorLocation(CatPosition);
        Cat->GetSkeletalMeshComponent()->PlayAnimation(Clips[FMath::Min(Index, 2)], true);
    }
    const FVector Target = CatPosition + FVector(0, 0, 65);
    Camera->GetCameraComponent()->SetFieldOfView(Index == 4 ? 95.f : 45.f);
    FVector Position;
    FVector LookAt = Target;
    switch (Index)
    {
    case 0: Position = Target + FVector(240, -270, 90); break;
    case 1: Position = Target + FVector(0, 360, 55); break;
    case 2: Position = Target + FVector(360, 0, 40); break;
    case 3: Position = Target + FVector(600, 600, 250); break;
    case 4: Position = Target + FVector(-145, 0, 25); break;
    default: LookAt = FVector(0, 0, 150); Position = LookAt + FVector(-1500, 1500, 1250); break;
    }
    Camera->SetActorLocation(Position);
    Camera->SetActorRotation((LookAt - Position).Rotation());
}

void APaitQualificationRun::SamplePose()
{
    TSharedRef<FJsonObject> Record = MakeShared<FJsonObject>();
    Record->SetNumberField(TEXT("elapsed_seconds"), FPlatformTime::Seconds() - Started);
    Record->SetStringField(TEXT("shot"), ShotNames[Shot]);
    TArray<TSharedPtr<FJsonValue>> LayerRecords;
    TArray<FTransform> Pose;
    double MaximumChange = 0;
    for (ASkeletalMeshActor* Cat : Cats)
    {
        USkeletalMeshComponent* C = Cat->GetSkeletalMeshComponent();
        UAnimSingleNodeInstance* Animation = C->GetSingleNodeInstance();
        if (!Animation || C->GetNumBones() < 10) { Finish(TEXT("Missing animation instance or bones")); return; }
        TSharedRef<FJsonObject> Layer = MakeShared<FJsonObject>();
        Layer->SetStringField(TEXT("mesh"), C->GetSkeletalMeshAsset()->GetName());
        Layer->SetNumberField(TEXT("bones"), C->GetNumBones());
        Layer->SetNumberField(TEXT("animation_time"), Animation->GetCurrentTime());
        LayerRecords.Add(MakeShared<FJsonValueObject>(Layer));
        for (int32 Bone = 0; Bone < C->GetNumBones(); ++Bone)
        {
            const FTransform Transform = C->GetBoneTransform(Bone);
            if (Transform.ContainsNaN()) { Finish(TEXT("Nonfinite bone pose")); return; }
            const int32 PoseIndex = Pose.Add(Transform);
            if (PreviousPose.IsValidIndex(PoseIndex))
                MaximumChange = FMath::Max(MaximumChange, FVector::Distance(Transform.GetLocation(), PreviousPose[PoseIndex].GetLocation()));
        }
    }
    if (MaximumChange > .01) ++ChangedSamples;
    Record->SetNumberField(TEXT("max_bone_translation_delta_cm"), MaximumChange);
    Record->SetArrayField(TEXT("layers"), LayerRecords);
    Samples.Add(MakeShared<FJsonValueObject>(Record));
    PreviousPose = MoveTemp(Pose);
}

void APaitQualificationRun::Capture(const FString& Suffix)
{
    FString Name = FString(ShotNames[Shot]) + Suffix + TEXT(".png");
    if (IFileManager::Get().FileExists(*(EvidenceDir / Name))) { Finish(TEXT("Stale capture exists")); return; }
    Captures.Add(Name);
    FScreenshotRequest::RequestScreenshot(EvidenceDir / Name, false, false);
}

void APaitQualificationRun::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (bFinished) return;
    ++Frames;
    const double Now = FPlatformTime::Seconds();
    if (Now - LastSample >= .37 && Shot >= 0) { LastSample = Now; SamplePose(); }
    if (bFinished) return;
    // First shot also includes shader/lighting warmup. Subsequent shots settle for 3 s.
    const double Warmup = Shot == 0 ? 30.0 : 3.0;
    const double InShot = Now - ShotStarted;
    if (!bFirstCapture && InShot >= Warmup) { bFirstCapture = true; Capture(Shot < 3 ? TEXT("-a") : TEXT("")); return; }
    if (Shot < 3 && !bSecondCapture && InShot >= Warmup + .63) { bSecondCapture = true; Capture(TEXT("-b")); }
    if (Shot < 5 && InShot >= Warmup + 4.0) EnterShot(Shot + 1);
    if (Now - Started >= Duration) Finish();
}

void APaitQualificationRun::Finish(const FString& Failure)
{
    if (bFinished) return;
    bFinished = true;
    FString Error = Failure;
    if (Error.IsEmpty() && (Captures.Num() != 9 || ChangedSamples < 10)) Error = TEXT("Insufficient captures or bone movement samples");
    for (const FString& CaptureName : Captures)
        if (IFileManager::Get().FileSize(*(EvidenceDir / CaptureName)) < 1024) Error = TEXT("Missing rendered capture: ") + CaptureName;
    TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
    Report->SetStringField(TEXT("status"), Error.IsEmpty() ? TEXT("runtime_checks_passed_requires_visual_review") : TEXT("failed"));
    Report->SetStringField(TEXT("error"), Error);
    Report->SetStringField(TEXT("adapter"), GRHIAdapterName);
    Report->SetNumberField(TEXT("elapsed_seconds"), FPlatformTime::Seconds() - Started);
    Report->SetNumberField(TEXT("frames"), static_cast<double>(Frames));
    Report->SetNumberField(TEXT("changed_pose_samples"), ChangedSamples);
    Report->SetBoolField(TEXT("performance_qualified"), false);
    Report->SetBoolField(TEXT("visual_qualified"), false);
    Report->SetArrayField(TEXT("pose_samples"), Samples);
    TArray<TSharedPtr<FJsonValue>> Images;
    for (const FString& Name : Captures) Images.Add(MakeShared<FJsonValueString>(Name));
    Report->SetArrayField(TEXT("captures"), Images);
    FString Json;
    FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Json));
    const bool bSaved = FFileHelper::SaveStringToFile(Json, *(EvidenceDir / TEXT("qualification.json")));
    FPlatformMisc::RequestExitWithStatus(false, Error.IsEmpty() && bSaved ? 0 : 2);
}
