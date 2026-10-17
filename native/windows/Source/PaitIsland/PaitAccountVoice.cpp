#include "PaitAccountSubsystem.h"
#include "AudioCaptureCore.h"
#include "Audio.h"
#include "Sound/SoundWaveProcedural.h"
#include "Components/AudioComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Containers/Ticker.h"
#include "Misc/ScopeLock.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Serialization/JsonSerializer.h"

struct FPaitMicBuffer
{
    Audio::FAudioCapture Capture;
    FCriticalSection Lock;
    TArray<float> Mono;
    int32 Rate=0;
    bool Overflow=false;
    ~FPaitMicBuffer(){if(Capture.IsStreamOpen())Capture.AbortStream();}
};
namespace {
void Utf8(TArray<uint8>& Out,const FString& Value){FTCHARToUTF8 V(*Value);Out.Append(reinterpret_cast<const uint8*>(V.Get()),V.Length());}
void LE(TArray<uint8>& Out,uint32 V,int32 Count){for(int32 I=0;I<Count;++I)Out.Add(static_cast<uint8>((V>>(I*8))&255));}
}
void UPaitAccountSubsystem::SelectPet(int32 Id)
{if(Id>=1 && Id<=4 && Id!=PetId){CancelVoice();PetId=Id;}}
void UPaitAccountSubsystem::CancelVoice()
{
    ++VoiceEpoch;
    if(Mic && Mic->Capture.IsStreamOpen())Mic->Capture.AbortStream();
    Mic.Reset();Recording.Empty();RecordingRequestId.Empty();
    if(Playing)Playing->Stop();Playing=nullptr;
}
bool UPaitAccountSubsystem::IsRecording() const {return Mic.IsValid() && Mic->Capture.IsCapturing();}
float UPaitAccountSubsystem::RecordingSeconds() const {return IsRecording()?FMath::Min(30.,FPlatformTime::Seconds()-RecordingStarted):0.f;}
bool UPaitAccountSubsystem::StartRecording(FString& Error)
{
    CancelVoice();
    if(!IsLoggedIn()){Error=TEXT("请先登录");return false;}
    Mic=MakeShared<FPaitMicBuffer,ESPMode::ThreadSafe>();
    Audio::FCaptureDeviceInfo Device;
    if(!Mic->Capture.GetCaptureDeviceInfo(Device)){Mic.Reset();Error=TEXT("无法打开麦克风，请检查 Windows 麦克风权限和输入设备");return false;}
    Audio::FAudioCaptureDeviceParams Params;
    TWeakPtr<FPaitMicBuffer,ESPMode::ThreadSafe> Buffer=Mic;
    if(!Mic->Capture.OpenAudioCaptureStream(Params,[Buffer](const void* Input,int32 Frames,int32 Channels,int32 Rate,double,bool Overflow){
        auto State=Buffer.Pin();if(!State || !Input || Rate<8000 || Rate>192000 || Channels<1 || Channels>32)return;
        FScopeLock Guard(&State->Lock);State->Overflow|=Overflow;
        if(State->Rate && State->Rate!=Rate){State->Overflow=true;return;}State->Rate=Rate;
        const int32 Count=FMath::Min(Frames,Rate*30-State->Mono.Num());
        const float* Samples=static_cast<const float*>(Input);
        for(int32 I=0;I<Count;++I){float Sum=0;for(int32 C=0;C<Channels;++C)Sum+=Samples[I*Channels+C];State->Mono.Add(FMath::IsFinite(Sum)?Sum/Channels:0);}
    },1024) || !Mic->Capture.StartStream())
    {Mic.Reset();Error=TEXT("麦克风启动失败，请检查设备是否被独占");return false;}
    RecordingStarted=FPlatformTime::Seconds();const uint64 Epoch=VoiceEpoch;
    TWeakObjectPtr<UPaitAccountSubsystem> Weak(this);
    FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([Weak,Epoch](float){
        if(Weak.IsValid() && Weak->VoiceEpoch==Epoch && Weak->IsRecording()){FString E;Weak->StopRecording(E);}return false;
    }),30.f);
    return true;
}
bool UPaitAccountSubsystem::StopRecording(FString& Error)
{
    if(!Mic){Error=TEXT("尚未开始录音");return false;}
    Mic->Capture.StopStream();Mic->Capture.CloseStream();
    FScopeLock Guard(&Mic->Lock);
    if(Mic->Overflow || Mic->Rate==0 || Mic->Mono.Num()<3*Mic->Rate){Error=TEXT("录音不足 3 秒或有丢帧，请重新录制");return false;}
    const int32 Count=FMath::Min(720000,static_cast<int32>(static_cast<int64>(Mic->Mono.Num())*24000/Mic->Rate));
    Recording.Empty();Utf8(Recording,TEXT("RIFF"));LE(Recording,36+Count*2,4);Utf8(Recording,TEXT("WAVEfmt "));
    LE(Recording,16,4);LE(Recording,1,2);LE(Recording,1,2);LE(Recording,24000,4);LE(Recording,48000,4);LE(Recording,2,2);LE(Recording,16,2);Utf8(Recording,TEXT("data"));LE(Recording,Count*2,4);
    for(int32 I=0;I<Count;++I){const double P=static_cast<double>(I)*Mic->Rate/24000;const int32 A=FMath::FloorToInt(P),B=FMath::Min(A+1,Mic->Mono.Num()-1);const float V=FMath::Lerp(Mic->Mono[A],Mic->Mono[B],static_cast<float>(P-A));LE(Recording,static_cast<uint16>(static_cast<int16>(FMath::Clamp(V,-1.f,1.f)*32767)),2);}
    RecordingRequestId=FGuid::NewGuid().ToString(EGuidFormats::Digits);return true;
}
bool UPaitAccountSubsystem::PlayWave(const TArray<uint8>& Bytes,FString& Error)
{
    FWaveModInfo Info;
    if(Bytes.Num()>20*1024*1024 || !Info.ReadWaveInfo(Bytes.GetData(),Bytes.Num()) || !Info.pFormatTag || *Info.pFormatTag!=1 || *Info.pBitsPerSample!=16 || *Info.pChannels<1 || *Info.pChannels>2 || *Info.pSamplesPerSec<8000 || *Info.pSamplesPerSec>96000)
    {Error=TEXT("服务返回的音频不是可播放的 PCM WAV");return false;}
    if(Playing)Playing->Stop();
    auto* Wave=NewObject<USoundWaveProcedural>(this);Wave->SetSampleRate(*Info.pSamplesPerSec);Wave->NumChannels=*Info.pChannels;
    Wave->Duration=static_cast<float>(Info.SampleDataSize)/(*Info.pSamplesPerSec*Wave->NumChannels*2);Wave->bLooping=false;
    Wave->QueueAudio(Info.SampleDataStart,Info.SampleDataSize);
    Playing=UGameplayStatics::SpawnSound2D(GetWorld(),Wave,1.f,1.f,0,nullptr,false,true);
    if(!Playing){Error=TEXT("无法启动音频输出");return false;}return true;
}
bool UPaitAccountSubsystem::PreviewRecording(FString& Error){return PlayWave(Recording,Error);}
void UPaitAccountSubsystem::AudioRequest(const FString& Path,TArray<uint8> Bytes,const FString& ContentType,bool Playback,FPaitApiReply Reply)
{
    const uint64 Epoch=SessionEpoch,Voice=VoiceEpoch;const int32 Pet=PetId;
    auto Req=FHttpModule::Get().CreateRequest();Req->SetURL(BaseUrl+TEXT("/api/native/v1/")+Path);Req->SetVerb(TEXT("POST"));Req->SetTimeout(90);
    Req->SetHeader(TEXT("Authorization"),TEXT("Bearer ")+Token);Req->SetHeader(TEXT("Content-Type"),ContentType);Req->SetContent(MoveTemp(Bytes));Pending.Add(Req);
    TWeakObjectPtr<UPaitAccountSubsystem> Weak(this);
    Req->OnProcessRequestComplete().BindLambda([Weak,Epoch,Voice,Pet,Playback,Reply=MoveTemp(Reply)](FHttpRequestPtr Request,FHttpResponsePtr Response,bool Connected)mutable{
        if(!Weak.IsValid() || Weak->SessionEpoch!=Epoch)return;Weak->Pending.Remove(Request);
        if(Weak->VoiceEpoch!=Voice || Weak->PetId!=Pet){Reply(false,nullptr,TEXT("已取消旧宠物或旧音色的请求"));return;}
        FString Error;TSharedPtr<FJsonObject> Data;bool Ok=Connected && Response.IsValid() && EHttpResponseCodes::IsOk(Response->GetResponseCode());
        if(Response && (!Ok || !Playback))FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Response->GetContentAsString()),Data);
        if(Data)Data->TryGetStringField(TEXT("error"),Error);
        if(Response && Response->GetResponseCode()==401)Weak->ClearSession();
        if(Ok && Playback)Ok=Weak->PlayWave(Response->GetContent(),Error);
        if(!Ok && Error.IsEmpty())Error=TEXT("语音请求未完成，请检查服务和输出设备");
        Reply(Ok,Data,Error);
    });
    if(!Req->ProcessRequest())Req->OnProcessRequestComplete().ExecuteIfBound(Req,nullptr,false);
}
void UPaitAccountSubsystem::UploadRecording(const FString& Name,const FString& Transcript,bool Consent,FPaitApiReply Reply)
{
    if(!Consent || !HasRecording() || Name.IsEmpty() || Name.Len()>32 || Transcript.Len()>1000)
    {Reply(false,nullptr,TEXT("请录制 3–30 秒、填写声音名称，并确认拥有录音授权"));return;}
    const FString Boundary=TEXT("pait-")+FGuid::NewGuid().ToString(EGuidFormats::Digits);TArray<uint8> Bytes;
    auto Field=[&](const FString& Key,const FString& Value){Utf8(Bytes,TEXT("--")+Boundary+TEXT("\r\nContent-Disposition: form-data; name=\"")+Key+TEXT("\"\r\n\r\n")+Value+TEXT("\r\n"));};
    Field(TEXT("name"),Name);Field(TEXT("transcript"),Transcript);Field(TEXT("consent"),TEXT("true"));Field(TEXT("petId"),FString::FromInt(PetId));Field(TEXT("requestId"),RecordingRequestId);
    Utf8(Bytes,TEXT("--")+Boundary+TEXT("\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"recording.wav\"\r\nContent-Type: audio/wav\r\n\r\n"));Bytes.Append(Recording);Utf8(Bytes,TEXT("\r\n--")+Boundary+TEXT("--\r\n"));
    AudioRequest(TEXT("voices"),MoveTemp(Bytes),TEXT("multipart/form-data; boundary=")+Boundary,false,MoveTemp(Reply));
}
void UPaitAccountSubsystem::PreviewVoice(const FString& Profile,FPaitApiReply Reply)
{++VoiceEpoch;if(Playing)Playing->Stop();TArray<uint8> Body;Utf8(Body,TEXT("{}"));AudioRequest(TEXT("voices/")+Profile+TEXT("/preview"),MoveTemp(Body),TEXT("application/json"),true,MoveTemp(Reply));}
void UPaitAccountSubsystem::Speak(const FString& Text,const FString& Profile,FPaitApiReply Reply)
{
    ++VoiceEpoch;if(Playing)Playing->Stop();auto Body=MakeShared<FJsonObject>();Body->SetStringField(TEXT("text"),Text.Left(500));Body->SetNumberField(TEXT("petId"),PetId);
    if(Profile.IsEmpty())Body->SetField(TEXT("voiceProfileId"),MakeShared<FJsonValueNull>());else Body->SetStringField(TEXT("voiceProfileId"),Profile);
    FString Json;FJsonSerializer::Serialize(Body,TJsonWriterFactory<>::Create(&Json));TArray<uint8> Bytes;Utf8(Bytes,Json);AudioRequest(TEXT("tts"),MoveTemp(Bytes),TEXT("application/json"),true,MoveTemp(Reply));
}
