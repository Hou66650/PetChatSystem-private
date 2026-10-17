// Opt-in compiled HTTP integration test. Refuses a non-fixture service before login.
#include "PaitAccountSubsystem.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "HAL/FileManager.h"
#include "Serialization/JsonSerializer.h"
#include "Kismet/KismetSystemLibrary.h"
#include "PaitPreviewPawn.h"
#include "GameFramework/PlayerController.h"
#include "Containers/Ticker.h"
#include "UnrealClient.h"
#include "PaitGarden.h"
#include "EngineUtils.h"

void UPaitAccountSubsystem::FinishFixture(bool Success,const FString& Error)
{
    FString Directory;FParse::Value(FCommandLine::Get(),TEXT("PaitEvidenceDir="),Directory);
    if(Directory.IsEmpty())Directory=FPaths::ProjectSavedDir()/TEXT("Qualification/NativeAccount");
    IFileManager::Get().MakeDirectory(*Directory,true);
    auto Report=MakeShared<FJsonObject>();Report->SetBoolField(TEXT("passed"),Success);Report->SetStringField(TEXT("error"),Error);
    Report->SetStringField(TEXT("scope"),TEXT("compiled native HTTP: isolated accounts, farm persistence, chat and voice-state; no production writes or microphone test"));
    FString Json;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Json));FFileHelper::SaveStringToFile(Json,*(Directory/TEXT("native-account.json")));
    if(Success && FParse::Param(FCommandLine::Get(),TEXT("PaitAccountCapture")))
    {
        OpenGarden();
        if(auto* PC=GetGameInstance()->GetFirstLocalPlayerController())if(auto* Pawn=Cast<APaitPreviewPawn>(PC->GetPawn()))Pawn->FocusGarden();
        TWeakObjectPtr<UPaitAccountSubsystem> Weak(this);
        FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([Directory,Weak](float){
            if(Weak.IsValid())for(TActorIterator<APaitGarden> It(Weak->GetWorld());It;++It){FString Json;FJsonSerializer::Serialize(It->Diagnostics(),TJsonWriterFactory<>::Create(&Json));FFileHelper::SaveStringToFile(Json,*(Directory/TEXT("native-garden.json")));}
            FScreenshotRequest::RequestScreenshot(Directory/TEXT("native-garden.png"),true,false);return false;
        }),20.f);
        FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([Weak](float){if(Weak.IsValid()){Weak->Logout();UKismetSystemLibrary::QuitGame(Weak->GetWorld(),nullptr,EQuitPreference::Quit,true);}return false;}),24.f);
    }
    else{Logout();UKismetSystemLibrary::QuitGame(GetWorld(),nullptr,EQuitPreference::Quit,true);}
}
void UPaitAccountSubsystem::RunFixtureStep(int32 Step)
{
    TWeakObjectPtr<UPaitAccountSubsystem> Weak(this);
    auto Next=[Weak,Step](bool Ok,TSharedPtr<FJsonObject> Data,FString Error){
        if(!Weak.IsValid())return;
        bool Flag=false;FString Name;
        if(Ok && Step==0)Ok=Data->TryGetBoolField(TEXT("fixture"),Flag) && Flag;
        if(Ok && (Step==2 || Step==9)){Data->TryGetStringField(TEXT("username"),Name);Ok=Name==(Step==2?TEXT("native-check-a"):TEXT("native-check-b"));}
        if(Ok && (Step==4 || Step==7))Ok=Data->TryGetBoolField(TEXT("started"),Flag)&&Flag;
        if(!Ok){Weak->FinishFixture(false,FString::Printf(TEXT("step %d: %s"),Step,*Error));return;}
        Weak->RunFixtureStep(Step+1);
    };
    switch(Step){
    case 0: Call(TEXT("GET"),TEXT("bootstrap"),nullptr,MoveTemp(Next));break;
    case 1:case 6: Login(TEXT("native-check-a"),TEXT("native-isolated-check"),MoveTemp(Next));break;
    case 2:case 9:Call(TEXT("GET"),TEXT("account"),nullptr,MoveTemp(Next));break;
    case 3:{if(HasPendingMutation()){RetryMutation(MoveTemp(Next));break;}auto Body=MakeShared<FJsonObject>();Body->SetStringField(TEXT("token"),TEXT("native-compiled-farm-start"));Mutate(TEXT("farm/start"),Body,MoveTemp(Next));break;}
    case 4:case 7:Call(TEXT("GET"),TEXT("farm"),nullptr,MoveTemp(Next));break;
    case 5:Logout();RunFixtureStep(6);break;
    case 8:Logout();Login(TEXT("native-check-b"),TEXT("native-isolated-check"),MoveTemp(Next));break;
    case 10:Call(TEXT("GET"),TEXT("voices?petId=3"),nullptr,MoveTemp(Next));break;
    case 11:{auto Body=MakeShared<FJsonObject>();Body->SetNumberField(TEXT("petId"),3);Body->SetStringField(TEXT("message"),TEXT("你好"));Body->SetStringField(TEXT("requestId"),FGuid::NewGuid().ToString(EGuidFormats::Digits));Call(TEXT("POST"),TEXT("chat"),Body,MoveTemp(Next));break;}
    case 12:Logout();Login(TEXT("native-check-a"),TEXT("native-isolated-check"),MoveTemp(Next));break;
    default:FinishFixture(true,TEXT(""));break;
    }
}
