#include "PaitAccountSubsystem.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Misc/SecureHash.h"
#include "HAL/FileManager.h"
#include "Serialization/JsonSerializer.h"

FString UPaitAccountSubsystem::OutboxPath() const
{return FPaths::ProjectSavedDir()/TEXT("NativeOutbox")/(FMD5::HashAnsiString(*(BaseUrl+TEXT("|")+Username))+TEXT(".json"));}
void UPaitAccountSubsystem::LoadOutbox()
{
    FString Json;TSharedPtr<FJsonObject> Envelope;
    if(!FFileHelper::LoadFileToString(Json,*OutboxPath()) || Json.Len()>32768 || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),Envelope))return;
    const TSharedPtr<FJsonObject>* Body=nullptr;FString Path;
    if(Envelope->TryGetObjectField(TEXT("body"),Body) && Envelope->TryGetStringField(TEXT("path"),Path) && (Path.StartsWith(TEXT("farm/")) || Path.StartsWith(TEXT("supplies/")) || Path.StartsWith(TEXT("market/")))){MutationBody=*Body;MutationPath=Path;}
}
void UPaitAccountSubsystem::Mutate(const FString& Path,TSharedPtr<FJsonObject> Body,FPaitApiReply Reply)
{
    if(!Path.StartsWith(TEXT("farm/")) && !Path.StartsWith(TEXT("supplies/")) && !Path.StartsWith(TEXT("market/"))){Call(TEXT("POST"),Path,Body,MoveTemp(Reply));return;}
    if(!IsLoggedIn()){Reply(false,nullptr,TEXT("请先登录"));return;}
    if(HasPendingMutation()){Reply(false,nullptr,TEXT("还有一笔结果未确认的操作，请先点击重试，避免重复扣款"));return;}
    MutationPath=Path;MutationBody=Body.IsValid()?Body:MakeShared<FJsonObject>();
    if(!MutationBody->HasField(TEXT("token")))MutationBody->SetStringField(TEXT("token"),FGuid::NewGuid().ToString(EGuidFormats::Digits));
    auto Envelope=MakeShared<FJsonObject>();Envelope->SetStringField(TEXT("path"),MutationPath);Envelope->SetObjectField(TEXT("body"),MutationBody);
    FString Json;FJsonSerializer::Serialize(Envelope,TJsonWriterFactory<>::Create(&Json));const FString File=OutboxPath();IFileManager::Get().MakeDirectory(*FPaths::GetPath(File),true);
    if(!FFileHelper::SaveStringToFile(Json,*(File+TEXT(".tmp"))) || !IFileManager::Get().Move(*File,*(File+TEXT(".tmp")),true,true))
    {MutationBody.Reset();MutationPath.Empty();Reply(false,nullptr,TEXT("无法保存操作回执，未向服务器提交"));return;}
    RetryMutation(MoveTemp(Reply));
}
void UPaitAccountSubsystem::RetryMutation(FPaitApiReply Reply)
{
    if(!IsLoggedIn() || !HasPendingMutation()){Reply(false,nullptr,TEXT("没有待确认操作"));return;}
    TWeakObjectPtr<UPaitAccountSubsystem> Weak(this);
    Call(TEXT("POST"),MutationPath,MutationBody,[Weak,Reply=MoveTemp(Reply)](bool Ok,TSharedPtr<FJsonObject> Data,FString Error)mutable{
        if(!Weak.IsValid())return;double Code=0;if(Data)Data->TryGetNumberField(TEXT("_http_status"),Code);
        if(Ok || (Code>=400 && Code<500 && Code!=408 && Code!=401))
        {
            if(IFileManager::Get().Delete(*Weak->OutboxPath(),false,true)){Weak->MutationBody.Reset();Weak->MutationPath.Empty();}
        }
        Reply(Ok,Data,Error);
    });
}
