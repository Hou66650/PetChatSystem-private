#include "PaitAccountSubsystem.h"
#include "AudioCaptureCore.h"
#include "WebSocketsModule.h"
#include "IWebSocket.h"
#include "Sound/SoundWaveProcedural.h"
#include "Components/AudioComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Containers/Ticker.h"
#include "Misc/Base64.h"
#include "Misc/ScopeLock.h"
#include "Serialization/JsonSerializer.h"
#include "GenericPlatform/GenericPlatformHttp.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Audio.h"

namespace {
FString Field(const TSharedPtr<FJsonObject>& O,const TCHAR* K){FString S;if(O)O->TryGetStringField(K,S);return S;}
TSharedPtr<FJsonObject> Object(const TSharedPtr<FJsonObject>& O,const TCHAR* K){const TSharedPtr<FJsonObject>* V=nullptr;return O&&O->TryGetObjectField(K,V)?*V:nullptr;}
TSharedPtr<FJsonObject> Event(const TCHAR* Type){auto E=MakeShared<FJsonObject>();E->SetStringField(TEXT("type"),Type);return E;}
struct FLiveTurn { FString User,Reply,Request=FGuid::NewGuid().ToString(EGuidFormats::Digits); bool Done=false,Archived=false,Cancelled=false; };
}

/** Bounded microphone -> 16k PCM -> existing GLM protocol. All state changes
 * occur on the game thread; the capture callback only fills a locked buffer. */
struct FPaitRealtime : TSharedFromThis<FPaitRealtime>
{
    TWeakObjectPtr<UPaitAccountSubsystem> Owner;
    TSharedPtr<IWebSocket> Socket;
    Audio::FAudioCapture Capture;
    FCriticalSection Lock;
    TArray<float> Input;
    int32 InputRate=0;
    double ReadPosition=0,Started=FPlatformTime::Seconds(),LastSpeech=Started,LastCheck=Started;
    bool Overflow=false,Ready=false,Speaking=false,CheckPending=false,Renew=false,Awaiting=false,TtsPending=false;
    int32 Turns=0,ArchivePending=0;
    int32 SavedTurns=0,FixtureOffset=0,ReceivedAudioBytes=0;
    TArray<uint8> FixtureAudio;
    FString Ticket,Profile;
    TSharedPtr<FJsonObject> Config;
    TSharedPtr<FLiveTurn> Current=MakeShared<FLiveTurn>();
    TMap<FString,TSharedPtr<FLiveTurn>> Items,Responses;
    FTSTicker::FDelegateHandle Ticker;
    bool Valid()const{return Owner.IsValid()&&Owner->Realtime.Get()==this&&Owner->IsLoggedIn();}
    ~FPaitRealtime(){Close();}
    void Close(){
        FTSTicker::GetCoreTicker().RemoveTicker(Ticker);
        if(Capture.IsStreamOpen())Capture.AbortStream();
        if(Socket){Socket->OnMessage().Clear();Socket->OnClosed().Clear();Socket->OnConnectionError().Clear();Socket->Close();Socket.Reset();}
    }
    void Fail(const FString& Error){if(Valid()){Owner->StopLive();Owner->LiveStatus=Error;}}
    void Send(TSharedPtr<FJsonObject> Data){if(Socket&&Socket->IsConnected()){FString Json;FJsonSerializer::Serialize(Data.ToSharedRef(),TJsonWriterFactory<>::Create(&Json));Socket->Send(Json);}}
    void ClearOutput(){
        if(!Owner.IsValid())return;
        TtsPending=false;
        ++Owner->VoiceEpoch; // Invalidate delayed cloned-voice HTTP responses.
        if(Owner->Playing)Owner->Playing->Stop();Owner->Playing=nullptr;
        if(Owner->LiveAudio)Owner->LiveAudio->Stop();Owner->LiveAudio=nullptr;
        if(Owner->LiveWave)Owner->LiveWave->ResetAudio();Owner->LiveWave=nullptr;
    }
    void Interrupt(){
        ClearOutput();Current->Cancelled=true;
        for(auto& Pair:Responses)if(!Pair.Value->Done)Pair.Value->Cancelled=true;
        Send(Event(TEXT("response.cancel")));Awaiting=false;
        if(Valid())Owner->LiveStatus=TEXT("已打断，继续说吧");
    }
    void Connect(TSharedPtr<FJsonObject> Session){
        if(!Valid())return;
        Config=Object(Session,TEXT("config"));Ticket=Field(Session,TEXT("ticket"));Profile=Field(Object(Session,TEXT("customVoice")),TEXT("id"));
        const FString Url=Field(Session,TEXT("wsBaseUrl"));
        if(!Config||Ticket.IsEmpty()||!Url.StartsWith(TEXT("wss://"))||Field(Session,TEXT("token")).IsEmpty()){Fail(TEXT("语音会话配置无效"));return;}
        // Match the existing browser transport; never print the signed URL/token.
        Socket=FWebSocketsModule::Get().CreateWebSocket(Url+TEXT("?Authorization=")+FGenericPlatformHttp::UrlEncode(Field(Session,TEXT("token"))));
        Socket->SetTextMessageMemoryLimit(512*1024);
        TWeakPtr<FPaitRealtime> Weak=AsShared();
        Socket->OnMessage().AddLambda([Weak](const FString& Json){if(auto S=Weak.Pin())if(S->Valid())S->Dispatch(Json);});
        Socket->OnConnectionError().AddLambda([Weak](const FString&){if(auto S=Weak.Pin())S->Fail(TEXT("语音连接失败，请检查网络和服务额度后重试"));});
        Socket->OnClosed().AddLambda([Weak](int32,const FString&,bool){if(auto S=Weak.Pin())S->Fail(TEXT("语音连接已结束，可以重新开始"));});
        Ticker=FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([Weak](float){auto S=Weak.Pin();return S&&S->Tick();}),.04f);
        Socket->Connect();
    }
    bool OpenMic(){
        FString FixturePath;
        if(FParse::Param(FCommandLine::Get(),TEXT("PaitAccountFixture"))&&FParse::Value(FCommandLine::Get(),TEXT("PaitLiveAudioFixture="),FixturePath)){
            TArray<uint8> File;FWaveModInfo Info;
            if(!FFileHelper::LoadFileToArray(File,*FixturePath)||File.Num()>640044||!Info.ReadWaveInfo(File.GetData(),File.Num())||*Info.pFormatTag!=1||*Info.pChannels!=1||*Info.pBitsPerSample!=16||*Info.pSamplesPerSec!=16000)return false;
            FixtureAudio.AddZeroed(16000);FixtureAudio.Append(Info.SampleDataStart,Info.SampleDataSize);FixtureAudio.AddZeroed(48000);return true;
        }
        Audio::FAudioCaptureDeviceParams Params;TWeakPtr<FPaitRealtime> Weak=AsShared();
        return Capture.OpenAudioCaptureStream(Params,[Weak](const void* Data,int32 Frames,int32 Channels,int32 Rate,double,bool Lost){
            auto S=Weak.Pin();if(!S||!Data||Channels<1||Channels>32||Rate<8000||Rate>192000)return;
            FScopeLock Guard(&S->Lock);
            if(Lost||(S->InputRate&&S->InputRate!=Rate)||S->Input.Num()+Frames>Rate*2){S->Overflow=true;return;}
            S->InputRate=Rate;const float* PCM=static_cast<const float*>(Data);
            for(int32 I=0;I<Frames;++I){float V=0;for(int32 C=0;C<Channels;++C)V+=PCM[I*Channels+C];S->Input.Add(FMath::IsFinite(V)?V/Channels:0);}
        },1024)&&Capture.StartStream();
    }
    void Archive(const TSharedPtr<FLiveTurn>& Turn){
        if(!Valid()||!Turn||Turn->Archived||Turn->Cancelled||!Turn->Done||Turn->User.IsEmpty()||Turn->Reply.IsEmpty())return;
        Turn->Archived=true;++ArchivePending;
        auto Body=MakeShared<FJsonObject>();Body->SetStringField(TEXT("ticket"),Ticket);Body->SetStringField(TEXT("requestId"),Turn->Request);
        Body->SetStringField(TEXT("message"),Turn->User.Left(1000));Body->SetStringField(TEXT("assistantText"),Turn->Reply.Left(2000));
        TWeakPtr<FPaitRealtime> Weak=AsShared();Owner->Call(TEXT("POST"),TEXT("realtime/round"),Body,[Weak](bool Ok,TSharedPtr<FJsonObject>,FString Error){
            if(auto S=Weak.Pin())if(S->Valid()){--S->ArchivePending;if(!Ok)S->Fail(TEXT("语音记录未保存：")+Error);else ++S->SavedTurns;}
        });
    }
    void Dispatch(const FString& Json){
        TSharedPtr<FJsonObject> E;if(Json.Len()>512*1024||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),E)||!E)return;
        const FString Type=Field(E,TEXT("type"));
        if(Type==TEXT("session.created")){
            auto Update=Event(TEXT("session.update"));auto Session=MakeShared<FJsonObject>(),Beta=MakeShared<FJsonObject>();
            Session->SetStringField(TEXT("instructions"),Field(Config,TEXT("instructions")));
            Session->SetStringField(TEXT("input_audio_format"),TEXT("pcm16"));Session->SetStringField(TEXT("output_audio_format"),TEXT("pcm"));
            auto Vad=MakeShared<FJsonObject>();Vad->SetStringField(TEXT("type"),TEXT("server_vad"));Session->SetObjectField(TEXT("turn_detection"),Vad);
            Beta->SetStringField(TEXT("chat_mode"),TEXT("audio"));Beta->SetStringField(TEXT("tts_source"),TEXT("e2e"));Session->SetObjectField(TEXT("beta_fields"),Beta);
            Session->SetStringField(TEXT("voice"),Field(Config,TEXT("voice")));Update->SetObjectField(TEXT("session"),Session);Send(Update);
        }else if(Type==TEXT("session.updated")){
            if(!Ready){if(!OpenMic()){Fail(TEXT("麦克风打开失败，请检查 Windows 输入设备和权限"));return;}Ready=true;Owner->LiveStatus=TEXT("正在聆听 · 建议佩戴耳机");}
        }else if(Type==TEXT("input_audio_buffer.speech_started")){
            ClearOutput();for(auto& P:Responses)if(!P.Value->Done)P.Value->Cancelled=true;
            Current=MakeShared<FLiveTurn>();Speaking=true;Awaiting=true;LastSpeech=FPlatformTime::Seconds();Owner->LiveUserText.Empty();Owner->LivePetText.Empty();Owner->LiveStatus=TEXT("正在听你说话…");
        }else if(Type==TEXT("input_audio_buffer.speech_stopped")){Speaking=false;LastSpeech=FPlatformTime::Seconds();Owner->LiveStatus=TEXT("正在回应…");
        }else if(Type==TEXT("input_audio_buffer.committed")){Items.Add(Field(E,TEXT("item_id")),Current);
        }else if(Type==TEXT("conversation.item.input_audio_transcription.completed")){
            auto Turn=Items.FindRef(Field(E,TEXT("item_id")));if(!Turn)return;Turn->User=Field(E,TEXT("transcript")).Left(1000);
            if(Turn==Current)Owner->LiveUserText=Turn->User;Archive(Turn);
        }else if(Type==TEXT("response.created")){Speaking=false;Responses.Add(Field(Object(E,TEXT("response")),TEXT("id")),Current);
        }else if(Type==TEXT("response.audio_transcript.delta")||Type==TEXT("response.text.delta")){
            auto Turn=Responses.FindRef(Field(E,TEXT("response_id")));if(!Turn||Turn->Cancelled||Turn!=Current)return;
            Turn->Reply+=Field(E,TEXT("delta"));if(Turn->Reply.Len()>2000){Fail(TEXT("回复过长，已停止通话，请重新开始"));return;}
            if(Turn->Reply.Contains(TEXT("Input validation error"))||Turn->Reply.Contains(TEXT("max_new_tokens"))||Turn->Reply.Contains(TEXT("rate_limit_error"))){Fail(TEXT("语音模型返回了服务错误，请重新连接或检查额度"));return;}
            Owner->LivePetText=Turn->Reply;
        }else if(Type==TEXT("response.text.done")||Type==TEXT("response.audio_transcript.done")){
            auto Turn=Responses.FindRef(Field(E,TEXT("response_id")));if(!Turn||Turn->Cancelled||Turn!=Current)return;
            const FString Text=Field(E,Type==TEXT("response.text.done")?TEXT("text"):TEXT("transcript"));
            if(Turn->Reply.IsEmpty())Turn->Reply=Text.Left(2000);Owner->LivePetText=Turn->Reply;
        }else if(Type==TEXT("response.audio.delta")){
            auto Turn=Responses.FindRef(Field(E,TEXT("response_id")));if(!Turn||Turn->Cancelled||Turn!=Current||!Profile.IsEmpty())return;
            TArray<uint8> PCM;if(!FBase64::Decode(Field(E,TEXT("delta")),PCM)||PCM.Num()%2||PCM.Num()>480000)return;
            ReceivedAudioBytes+=PCM.Num();
            if(!FixtureAudio.IsEmpty())return; // Synthetic test does not play sound or record a microphone.
            if(!Owner->LiveWave){Owner->LiveWave=NewObject<USoundWaveProcedural>(Owner.Get());Owner->LiveWave->SetSampleRate(24000);Owner->LiveWave->NumChannels=1;Owner->LiveWave->Duration=INDEFINITELY_LOOPING_DURATION;}
            if(Owner->LiveWave->GetAvailableAudioByteCount()+PCM.Num()>480000){Fail(TEXT("播放积压，已停止以避免延迟回复"));return;}
            Owner->LiveWave->QueueAudio(PCM.GetData(),PCM.Num());
            if(!Owner->LiveAudio)Owner->LiveAudio=UGameplayStatics::SpawnSound2D(Owner->GetWorld(),Owner->LiveWave);
            Owner->LiveStatus=TEXT("宠物正在说话 · 可插话或点击打断");
        }else if(Type==TEXT("response.done")){
            auto Response=Object(E,TEXT("response"));auto Turn=Responses.FindRef(Field(Response,TEXT("id")));if(!Turn||Turn->Done)return;
            Turn->Done=true;Turn->Cancelled|=Field(Response,TEXT("status"))!=TEXT("completed");
            if(Turn==Current){Awaiting=false;Speaking=false;if(!Turn->Cancelled&&!Profile.IsEmpty()&&!Turn->Reply.IsEmpty()){
                TtsPending=true;TWeakPtr<FPaitRealtime> Weak=AsShared();Owner->Speak(Turn->Reply,Profile,[Weak,Turn](bool Ok,TSharedPtr<FJsonObject>,FString Error){if(auto S=Weak.Pin())if(S->Valid()&&S->Current==Turn&&!Turn->Cancelled){S->TtsPending=false;if(!Ok)S->Fail(Error);}});
            }Owner->LiveStatus=Turn->User.IsEmpty()?TEXT("可继续说话 · 本轮未返回识别文字，暂未保存对话记录"):TEXT("正在聆听 · 可继续说话");}
            Archive(Turn);if(!Turn->Cancelled)++Turns;Renew=Turns>=4;
        }else if(Type==TEXT("error")){Fail(TEXT("语音服务未完成请求，请检查额度或稍后重试"));}
        if(Items.Num()>32||Responses.Num()>32)Renew=true;
    }
    bool Tick(){
        if(!Valid())return false;
        const double Now=FPlatformTime::Seconds();
        if(!Ready){if(Now-Started>20)Fail(TEXT("语音连接超时，请重试"));return Valid();}
        if(Now-LastSpeech>90){Fail(TEXT("长时间未说话，已暂停麦克风；点击开始即可继续"));return false;}
        if(Awaiting&&Now-LastSpeech>60){Fail(TEXT("语音回复超时，请重试"));return false;}
        if(Now-LastCheck>10&&!CheckPending){
            LastCheck=Now;CheckPending=true;auto Body=MakeShared<FJsonObject>();Body->SetStringField(TEXT("ticket"),Ticket);TWeakPtr<FPaitRealtime> Weak=AsShared();
            Owner->Call(TEXT("POST"),TEXT("realtime/check"),Body,[Weak](bool Ok,TSharedPtr<FJsonObject>,FString Error){if(auto S=Weak.Pin())if(S->Valid()){S->CheckPending=false;if(!Ok)S->Fail(Error);}});
        }
        TArray<uint8> PCM;bool Lost;
        {FScopeLock Guard(&Lock);Lost=Overflow;
            if(InputRate){const double Step=static_cast<double>(InputRate)/16000;
                while(ReadPosition+1<Input.Num()){int32 A=FMath::FloorToInt(ReadPosition);float V=FMath::Lerp(Input[A],Input[A+1],static_cast<float>(ReadPosition-A));int16 N=static_cast<int16>(FMath::Clamp(V,-1.f,1.f)*32767);PCM.Add(N&255);PCM.Add((N>>8)&255);ReadPosition+=Step;}
                const int32 Consumed=FMath::Min(FMath::FloorToInt(ReadPosition),FMath::Max(0,Input.Num()-1));if(Consumed){Input.RemoveAt(0,Consumed,EAllowShrinking::No);ReadPosition-=Consumed;}
            }
        }
        if(!FixtureAudio.IsEmpty()&&FixtureOffset<FixtureAudio.Num()){
            const int32 Count=FMath::Min(1280,FixtureAudio.Num()-FixtureOffset);PCM.Append(FixtureAudio.GetData()+FixtureOffset,Count);FixtureOffset+=Count;
        }
        if(Lost){Fail(TEXT("麦克风丢帧或客户端卡顿，请重试"));return false;}
        if(!PCM.IsEmpty()){auto E=Event(TEXT("input_audio_buffer.append"));E->SetStringField(TEXT("audio"),FBase64::Encode(PCM));Send(E);}
        const bool Playing=(Owner->LiveWave&&Owner->LiveWave->GetAvailableAudioByteCount()>0)||(Owner->Playing&&Owner->Playing->IsPlaying());
        if((Renew||Now-Started>480)&&!Speaking&&!Awaiting&&!Playing&&!TtsPending&&ArchivePending==0){Owner->StartLive();return false;}
        return true;
    }
};

void UPaitAccountSubsystem::StartLive(){
    CancelVoice();if(!IsLoggedIn()){LiveStatus=TEXT("请先登录");return;}
    LiveUserText.Empty();LivePetText.Empty();LiveStatus=TEXT("正在连接语音…");
    Realtime=MakeShared<FPaitRealtime>();Realtime->Owner=this;
    auto Body=MakeShared<FJsonObject>();Body->SetNumberField(TEXT("petId"),PetId);
    TWeakPtr<FPaitRealtime> Weak=Realtime;
    Call(TEXT("POST"),TEXT("realtime/session"),Body,[Weak](bool Ok,TSharedPtr<FJsonObject> Data,FString Error){if(auto S=Weak.Pin())if(S->Valid()){if(Ok)S->Connect(Data);else S->Fail(Error);}});
}
void UPaitAccountSubsystem::StopLive(){
    auto Old=Realtime;Realtime.Reset();
    if(Old){Old->ClearOutput();Old->Close();LiveStatus=TEXT("语音已结束，麦克风已关闭");}
}
void UPaitAccountSubsystem::InterruptLive(){if(Realtime)Realtime->Interrupt();}
bool UPaitAccountSubsystem::IsLiveRoundComplete()const{return Realtime&&Realtime->Turns>0&&Realtime->ReceivedAudioBytes>0&&!Realtime->Current->Reply.IsEmpty();}
TSharedRef<FJsonObject> UPaitAccountSubsystem::LiveDiagnostics()const{
    auto R=MakeShared<FJsonObject>();R->SetBoolField(TEXT("connected"),Realtime&&Realtime->Ready);
    R->SetNumberField(TEXT("completed_responses"),Realtime?Realtime->Turns:0);R->SetNumberField(TEXT("audio_bytes"),Realtime?Realtime->ReceivedAudioBytes:0);
    R->SetNumberField(TEXT("saved_rounds"),Realtime?Realtime->SavedTurns:0);R->SetBoolField(TEXT("input_transcript_received"),Realtime&&!Realtime->Current->User.IsEmpty());
    R->SetBoolField(TEXT("microphone_tested"),false);R->SetBoolField(TEXT("speaker_playback_tested"),false);return R;
}

bool UPaitAccountSubsystem::TestLiveProtocol(FString& Error){
    if(!FParse::Param(FCommandLine::Get(),TEXT("PaitAccountFixture"))||!IsLoggedIn())return false;
    StopLive();Realtime=MakeShared<FPaitRealtime>();Realtime->Owner=this;
    auto Test=Realtime;
    auto Dispatch=[Test](const TCHAR* Type,const FString& Id=TEXT(""),const FString& Delta=TEXT("")){
        auto E=Event(Type);E->SetStringField(TEXT("response_id"),Id);E->SetStringField(TEXT("item_id"),Id);E->SetStringField(TEXT("delta"),Delta);
        auto R=MakeShared<FJsonObject>();R->SetStringField(TEXT("id"),Id);E->SetObjectField(TEXT("response"),R);
        FString Json;FJsonSerializer::Serialize(E.ToSharedRef(),TJsonWriterFactory<>::Create(&Json));Test->Dispatch(Json);
    };
    Dispatch(TEXT("input_audio_buffer.speech_started"));Dispatch(TEXT("response.created"),TEXT("old"));
    Dispatch(TEXT("response.audio_transcript.delta"),TEXT("old"),TEXT("first"));
    bool Passed=LivePetText==TEXT("first");
    Dispatch(TEXT("input_audio_buffer.speech_started"));Dispatch(TEXT("response.audio_transcript.delta"),TEXT("old"),TEXT("stale"));
    Passed&=LivePetText.IsEmpty()&&Test->Responses[TEXT("old")]->Cancelled;
    Dispatch(TEXT("response.created"),TEXT("new"));Dispatch(TEXT("response.audio_transcript.delta"),TEXT("new"),TEXT("second"));
    Passed&=LivePetText==TEXT("second");InterruptLive();
    Dispatch(TEXT("response.audio_transcript.delta"),TEXT("new"),TEXT("discard"));Passed&=LivePetText==TEXT("second")&&Test->Current->Cancelled;
    StopLive();Passed&=!Realtime.IsValid()&&!LiveWave&&!LiveAudio;
    if(!Passed)Error=TEXT("Realtime interrupt/stale-response lifecycle failed");return Passed;
}
