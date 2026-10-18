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
#include "PaitMeadowPet.h"

void UPaitAccountSubsystem::FinishFixture(bool Success,const FString& Error)
{
    FString Directory;FParse::Value(FCommandLine::Get(),TEXT("PaitEvidenceDir="),Directory);
    if(Directory.IsEmpty())Directory=FPaths::ProjectSavedDir()/TEXT("Qualification/NativeAccount");
    IFileManager::Get().MakeDirectory(*Directory,true);
    auto Report=MakeShared<FJsonObject>();Report->SetBoolField(TEXT("passed"),Success);Report->SetStringField(TEXT("error"),Error);
    Report->SetStringField(TEXT("scope"),FParse::Param(FCommandLine::Get(),TEXT("PaitProviderCheck"))
        ? TEXT("compiled native HTTP and synthetic realtime provider round; isolated accounts, no production writes, microphone or speaker playback")
        : TEXT("compiled native HTTP: accounts, farm, chat, account meal commit and realtime event lifecycle; no production writes, microphone or paid provider test"));
    Report->SetBoolField(TEXT("account_meal_commit"),Success);Report->SetBoolField(TEXT("realtime_interrupt_and_stale_events"),Success);
    Report->SetBoolField(TEXT("synthetic_provider_round"),Success&&FParse::Param(FCommandLine::Get(),TEXT("PaitProviderCheck")));
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
        if(Ok && (Step==13||Step==15)){
            const TSharedPtr<FJsonObject>* Bowls=nullptr;const TSharedPtr<FJsonObject>* Cat=nullptr;double Food=100;
            if(Data->TryGetObjectField(TEXT("bowls"),Bowls)&&(*Bowls)->TryGetObjectField(TEXT("3"),Cat))(*Cat)->TryGetNumberField(TEXT("food"),Food);
            if(Step==13){Weak->FixtureFoodBefore=Food;Ok=Food>=25;}
            else Ok=Food==Weak->FixtureFoodBefore-25;
        }
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
    case 13:case 15:Call(TEXT("GET"),TEXT("supplies"),nullptr,MoveTemp(Next));break;
    case 14:{
        const double Start=FPlatformTime::Seconds();
        FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([Weak,Start,Started=false,Meals=0](float)mutable{
            if(!Weak.IsValid())return false;
            if(FPlatformTime::Seconds()-Start>180){Weak->FinishFixture(false,TEXT("Account meal timeout"));return false;}
            for(TActorIterator<APaitMeadowPet> Pet(Weak->GetWorld());Pet;++Pet){
                if(!Started){Meals=Pet->GetCompletedMeals();Started=Pet->Care(TEXT("food"));return true;}
                if(Pet->GetCompletedMeals()>Meals&&!Weak->CareBusy&&!Weak->HasPendingMutation()){Weak->RunFixtureStep(15);return false;}
            }return true;
        }),.5f);break;}
    default:{
        FString Error;if(!TestLiveProtocol(Error)){FinishFixture(false,Error);break;}
        if(!FParse::Param(FCommandLine::Get(),TEXT("PaitProviderCheck"))){FinishFixture(true,TEXT(""));break;}
        StartLive();const double Start=FPlatformTime::Seconds();
        FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([Weak,Start](float){
            if(!Weak.IsValid())return false;
            if(Weak->IsLiveRoundComplete()){
                FString Directory;FParse::Value(FCommandLine::Get(),TEXT("PaitEvidenceDir="),Directory);
                FString Json;FJsonSerializer::Serialize(Weak->LiveDiagnostics(),TJsonWriterFactory<>::Create(&Json));FFileHelper::SaveStringToFile(Json,*(Directory/TEXT("native-live-provider.json")));
                Weak->StopLive();Weak->FinishFixture(true,TEXT(""));return false;
            }
            if(!Weak->IsLive()||FPlatformTime::Seconds()-Start>90){const FString Error=Weak->LiveStatus;Weak->StopLive();Weak->FinishFixture(false,Error);return false;}
            return true;
        }),.25f);break;
    }
    }
}
