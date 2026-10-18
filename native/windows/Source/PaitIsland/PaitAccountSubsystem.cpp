#include "PaitAccountSubsystem.h"
#include "PaitAccountPanel.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Serialization/JsonSerializer.h"
#include "Engine/GameInstance.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/PlayerController.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Containers/Ticker.h"

void UPaitAccountSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    FString Url;
    if (FParse::Value(FCommandLine::Get(), TEXT("PaitApi="), Url))
    {
        // No credentials over cleartext beyond the local companion service.
        FString Port=Url; Port.RemoveFromStart(TEXT("http://127.0.0.1:"));
        const bool Local=Url.StartsWith(TEXT("http://127.0.0.1:")) && Port.IsNumeric() && FCString::Atoi(*Port)>0 && FCString::Atoi(*Port)<=65535;
        if (Url.StartsWith(TEXT("https://")) || Local) BaseUrl = Url;
    }
    BaseUrl.RemoveFromEnd(TEXT("/"));
    if(FParse::Param(FCommandLine::Get(),TEXT("PaitAccountFixture")))
    {
        TWeakObjectPtr<UPaitAccountSubsystem> Weak(this);
        FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([Weak](float){if(Weak.IsValid())Weak->RunFixtureStep(0);return false;}),15.f);
    }
}
void UPaitAccountSubsystem::ClearSession()
{
    CancelVoice();
    ++SessionEpoch;
    for (auto& Request : Pending) if (Request) { Request->OnProcessRequestComplete().Unbind(); Request->CancelRequest(); }
    Pending.Empty(); Token.Empty(); Username.Empty();
    GardenState.Reset();SelectedBed.Empty();GardenStatus.Empty();GardenLoading=false;
    CareBusy=false;
    MutationBody.Reset();MutationPath.Empty();
}
void UPaitAccountSubsystem::Deinitialize()
{
    if (Panel.IsValid() && GetGameInstance()->GetGameViewportClient()) GetGameInstance()->GetGameViewportClient()->RemoveViewportWidgetContent(Panel.ToSharedRef());
    Panel.Reset(); ClearSession(); Super::Deinitialize();
}
void UPaitAccountSubsystem::Call(const FString& Method, const FString& Path, TSharedPtr<FJsonObject> Body, FPaitApiReply Reply)
{
    const uint64 Epoch = SessionEpoch;
    auto Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(BaseUrl + TEXT("/api/native/v1/") + Path);
    Request->SetVerb(Method); Request->SetTimeout(Path.StartsWith(TEXT("park"))?4.5f:90.f);
    Request->SetHeader(TEXT("Accept"), TEXT("application/json"));
    if (!Token.IsEmpty()) Request->SetHeader(TEXT("Authorization"), TEXT("Bearer ") + Token);
    if (Method != TEXT("GET"))
    {
        FString Json;
        FJsonSerializer::Serialize(Body.IsValid() ? Body.ToSharedRef() : MakeShared<FJsonObject>(), TJsonWriterFactory<>::Create(&Json));
        Request->SetHeader(TEXT("Content-Type"), TEXT("application/json")); Request->SetContentAsString(Json);
    }
    Pending.Add(Request);
    TWeakObjectPtr<UPaitAccountSubsystem> Weak(this);
    Request->OnProcessRequestComplete().BindLambda([Weak, Epoch, Reply=MoveTemp(Reply)](FHttpRequestPtr Req, FHttpResponsePtr Response, bool Connected) mutable
    {
        if (!Weak.IsValid() || Epoch != Weak->SessionEpoch) return;
        Weak->Pending.Remove(Req);
        TSharedPtr<FJsonObject> Data;
        if (Response.IsValid()) FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Response->GetContentAsString()), Data);
        if (!Connected || !Response.IsValid()) { Reply(false, Data, TEXT("连接失败，请检查客户端服务。原操作不要重复提交。")); return; }
        const int32 Code = Response->GetResponseCode();
        if(Data)Data->SetNumberField(TEXT("_http_status"),Code);
        if (Code == 401 && !Req->GetURL().EndsWith(TEXT("/session"))) Weak->ClearSession();
        FString Error;
        if (Data) Data->TryGetStringField(TEXT("error"), Error);
        if (Error.IsEmpty()) Error = FString::Printf(TEXT("请求未完成（%d）"), Code);
        Reply(Code >= 200 && Code < 300 && Data.IsValid(), Data, Error);
    });
    if (!Request->ProcessRequest())
    {
        // Route immediate failures through the same completion path.
        Request->OnProcessRequestComplete().ExecuteIfBound(Request, nullptr, false);
    }
}
void UPaitAccountSubsystem::Login(const FString& Name, const FString& Password, FPaitApiReply Reply)
{
    ClearSession();
    auto Body = MakeShared<FJsonObject>(); Body->SetStringField(TEXT("username"), Name); Body->SetStringField(TEXT("password"), Password);
    TWeakObjectPtr<UPaitAccountSubsystem> Weak(this);
    Call(TEXT("POST"), TEXT("session"), Body, [Weak, Reply=MoveTemp(Reply)](bool Ok, TSharedPtr<FJsonObject> Data, FString Error) mutable
    {
        if (!Weak.IsValid()) return;
        if (Ok && Data->TryGetStringField(TEXT("token"), Weak->Token)){Data->TryGetStringField(TEXT("username"), Weak->Username);Weak->LoadOutbox();}
        else Ok = false;
        Reply(Ok, Data, Error);
    });
}
void UPaitAccountSubsystem::Logout()
{
    // Cancel account-dependent callbacks before revocation. This request carries
    // the old token, but no state callback survives into another account.
    const FString OldToken = Token;
    ClearSession();
    if (OldToken.IsEmpty()) return;
    auto Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BaseUrl + TEXT("/api/native/v1/session")); Req->SetVerb(TEXT("DELETE"));
    Req->SetHeader(TEXT("Authorization"),TEXT("Bearer ")+OldToken);
    Req->SetHeader(TEXT("Content-Type"),TEXT("application/json")); Req->SetContentAsString(TEXT("{}")); Req->SetTimeout(10); Req->ProcessRequest();
}
void UPaitAccountSubsystem::TogglePanel()
{
    auto* Viewport = GetGameInstance()->GetGameViewportClient();
    if (!Viewport) return;
    if (Panel.IsValid()) { CancelVoice(); Viewport->RemoveViewportWidgetContent(Panel.ToSharedRef()); Panel.Reset(); return; }
    if (auto* PC = GetGameInstance()->GetFirstLocalPlayerController())
    {
        PC->bShowMouseCursor = true; FInputModeGameAndUI Mode; Mode.SetHideCursorDuringCapture(false); PC->SetInputMode(Mode);
    }
    Panel = SNew(SPaitAccountPanel).Account(this);
    Viewport->AddViewportWidgetContent(Panel.ToSharedRef(), 50);
}
void UPaitAccountSubsystem::OpenGarden(const FString& Bed)
{
    SelectedBed=Bed;
    if(!Panel.IsValid())TogglePanel();
    if(Panel.IsValid() && IsLoggedIn())StaticCastSharedPtr<SPaitAccountPanel>(Panel)->ShowGarden();
}
