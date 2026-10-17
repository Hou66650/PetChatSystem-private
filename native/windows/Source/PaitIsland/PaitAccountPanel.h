#pragma once
#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "PaitAccountSubsystem.h"
class SVerticalBox;
class SEditableTextBox;
class SWrapBox;

class SPaitAccountPanel : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SPaitAccountPanel) {} SLATE_ARGUMENT(UPaitAccountSubsystem*, Account) SLATE_END_ARGS()
    void Construct(const FArguments& Args);
    void ShowGarden(){Load(TEXT("farm"));}
private:
    void Rebuild();
    void Load(const FString& Page);
    void Render(TSharedPtr<FJsonObject> Data);
    void Mutate(const FString& Path, TSharedPtr<FJsonObject> Body);
    void Line(const FString& Text);
    void Button(const FString& Text, TFunction<void()> Action);
    void Chip(const FString& Text, TFunction<void()> Action, TSharedPtr<SWrapBox> Row);
    void ReadAloud(const FString& Text);
    FString Page = TEXT("account"), Message;
    bool Busy = false;
    bool VoiceConsent = false, RegisterMode = false;
    uint64 ViewEpoch = 0;
    TWeakObjectPtr<UPaitAccountSubsystem> Account;
    TSharedPtr<SVerticalBox> Content;
    TSharedPtr<SEditableTextBox> LoginName, Password, PasswordConfirm, ChatInput, VoiceName, VoiceTranscript;
};
