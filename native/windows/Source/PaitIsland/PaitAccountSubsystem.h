#pragma once
#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Dom/JsonObject.h"
#include "PaitAccountSubsystem.generated.h"

class SWidget;
class IHttpRequest;
class UAudioComponent;
struct FPaitMicBuffer;
using FPaitApiReply = TFunction<void(bool, TSharedPtr<FJsonObject>, FString)>;

/** Account transport lives across map travel. Credentials are memory-only. */
UCLASS()
class PAITISLAND_API UPaitAccountSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;
    void Login(const FString& Username, const FString& Password, FPaitApiReply Reply);
    void Logout();
    void Call(const FString& Method, const FString& Path, TSharedPtr<FJsonObject> Body, FPaitApiReply Reply);
    void Mutate(const FString& Path, TSharedPtr<FJsonObject> Body, FPaitApiReply Reply);
    void RetryMutation(FPaitApiReply Reply);
    bool HasPendingMutation() const { return MutationBody.IsValid(); }
    void TogglePanel();
    void OpenGarden(const FString& Bed = TEXT(""));
    void SelectPet(int32 Id);
    bool StartRecording(FString& Error);
    bool StopRecording(FString& Error);
    void CancelVoice();
    bool IsRecording() const;
    float RecordingSeconds() const;
    bool HasRecording() const { return Recording.Num()>44; }
    bool PreviewRecording(FString& Error);
    void UploadRecording(const FString& Name, const FString& Transcript, bool Consent, FPaitApiReply Reply);
    void PreviewVoice(const FString& Profile, FPaitApiReply Reply);
    void Speak(const FString& Text, const FString& Profile, FPaitApiReply Reply);
    bool IsLoggedIn() const { return !Token.IsEmpty(); }
    bool IsPanelVisible() const { return Panel.IsValid(); }
    uint64 GetSessionRevision() const { return SessionEpoch; }
    FString Username;
    FString BaseUrl = TEXT("http://127.0.0.1:5012");
    int32 PetId = 3;
    TSharedPtr<FJsonObject> GardenState;
    FString SelectedBed;
    bool GardenLoading = false;
    FString GardenStatus;
private:
    void ClearSession();
    FString Token;
    uint64 SessionEpoch = 0;
    TArray<TSharedPtr<IHttpRequest, ESPMode::ThreadSafe>> Pending;
    TSharedPtr<SWidget> Panel;
    TSharedPtr<FPaitMicBuffer, ESPMode::ThreadSafe> Mic;
    TArray<uint8> Recording;
    FString RecordingRequestId;
    uint64 VoiceEpoch = 0;
    double RecordingStarted = 0;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> Playing;
    bool PlayWave(const TArray<uint8>& Bytes, FString& Error);
    void AudioRequest(const FString& Path, TArray<uint8> Bytes, const FString& ContentType, bool Playback, FPaitApiReply Reply);
    void RunFixtureStep(int32 Step);
    void FinishFixture(bool Success, const FString& Error);
    void LoadOutbox();
    FString OutboxPath() const;
    TSharedPtr<FJsonObject> MutationBody;
    FString MutationPath;
};
