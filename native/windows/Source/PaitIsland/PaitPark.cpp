#include "PaitPark.h"
#include "PaitExperience.h"
#include "EngineUtils.h"
#include "Engine/Engine.h"
#include "HAL/IConsoleManager.h"
#include "PaitAccountSubsystem.h"
#include "Engine/GameInstance.h"
#include "Engine/GameViewportClient.h"
#include "Animation/SkeletalMeshActor.h"
#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/SkeletalMesh.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Notifications/SProgressBar.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "GameFramework/GameUserSettings.h"

namespace {
UPaitAccountSubsystem* Account(AActor* A){return A->GetGameInstance()->GetSubsystem<UPaitAccountSubsystem>();}
// UE Interchange GLTF::ConvertVec3 maps (X,Y,Z) to (X,Z,Y), centimetres.
FVector World(double X,double Z,double Y=0){return FVector(X*100,Z*100,Y*100);}
const TCHAR* Roots[]={TEXT(""),TEXT("/Game/Imported/P1Shiba/qiuqiu/SkeletalMeshes/"),TEXT("/Game/Imported/P1Husky/xueqiu/SkeletalMeshes/"),TEXT("/Game/Imported/P0Cat/cat/SkeletalMeshes/"),TEXT("/Game/Imported/P1Shepherd/shepherd/SkeletalMeshes/")};
const TCHAR* Prefixes[]={TEXT(""),TEXT("qiuqiu"),TEXT("xueqiu"),TEXT("cat"),TEXT("shepherd")};
const FSlateRoundedBoxBrush Glass(FLinearColor::White,18.f);
const FButtonStyle& ButtonStyle(){static FButtonStyle S=FButtonStyle().SetNormal(FSlateRoundedBoxBrush(FLinearColor(.04,.13,.10,.85),14.f)).SetHovered(FSlateRoundedBoxBrush(FLinearColor(.16,.3,.22),14.f));return S;}
FString ClipFor(const FString& A){if(A==TEXT("sleep"))return TEXT("sleep_loop");if(A==TEXT("sit"))return TEXT("sit_idle");if(A==TEXT("greet")||A==TEXT("happy"))return TEXT("tail_greeting");if(A==TEXT("ball")||A==TEXT("bow"))return TEXT("play_bow");if(A==TEXT("look"))return TEXT("curious_listen");if(A==TEXT("sniff")||A==TEXT("stretch"))return A;return TEXT("idle_breathe");}
}
APaitPark::APaitPark(){PrimaryActorTick.bCanEverTick=true;}
void APaitPark::BeginPlay(){Super::BeginPlay();Session=Account(this)->GetSessionRevision();Interface();if(auto* Limit=IConsoleManager::Get().FindConsoleVariable(TEXT("t.MaxFPS"))){PreviousFrameLimit=Limit->GetFloat();Limit->Set(60.f,ECVF_SetByCode);}if(GEngine)GEngine->ForceGarbageCollection(true);}
void APaitPark::ClearPets(){for(auto& Pair:Pets)for(auto& Part:Pair.Value.Parts)if(Part.IsValid())Part->Destroy();Pets.Empty();Mine.Empty();}
void APaitPark::Leave(){
    const FString Old=Token;Token.Empty();++Epoch;Busy=Routing=false;GroundSyncPending=false;Path.Empty();FacilityId.Empty();PendingFacility.Empty();ClearPets();
    if(!Old.IsEmpty()){auto B=MakeShared<FJsonObject>();B->SetStringField(TEXT("token"),Old);Account(this)->Call(TEXT("POST"),TEXT("park/leave"),B,[](bool,TSharedPtr<FJsonObject>,FString){});}
    Status=TEXT("已结束游玩，伙伴回到你身边。");
}
void APaitPark::EndPlay(const EEndPlayReason::Type R){Leave();if(auto* Limit=IConsoleManager::Get().FindConsoleVariable(TEXT("t.MaxFPS")))Limit->Set(PreviousFrameLimit,ECVF_SetByCode);if(Widget&&GetGameInstance()->GetGameViewportClient())GetGameInstance()->GetGameViewportClient()->RemoveViewportWidgetContent(Widget.ToSharedRef());Widget.Reset();Super::EndPlay(R);}
void APaitPark::Join(){
    if(Busy||!Token.IsEmpty())return;
    if(!Account(this)->IsLoggedIn()){Status=TEXT("请先登录，再选择带伙伴入园。");Account(this)->TogglePanel();return;}
    Busy=true;const uint64 E=++Epoch;TWeakObjectPtr<APaitPark> W(this);TWeakObjectPtr<UPaitAccountSubsystem> A(Account(this));
    auto B=MakeShared<FJsonObject>();B->SetNumberField(TEXT("pet"),PetId);Status=TEXT("正在带伙伴入园…");
    Account(this)->Call(TEXT("POST"),TEXT("park/join"),B,[W,A,E](bool Ok,TSharedPtr<FJsonObject> D,FString Error){
        if(!W.IsValid()||E!=W->Epoch){if(Ok&&A.IsValid()){auto L=MakeShared<FJsonObject>();L->SetStringField(TEXT("token"),D->GetStringField(TEXT("token")));A->Call(TEXT("POST"),TEXT("park/leave"),L,[](bool,TSharedPtr<FJsonObject>,FString){});}return;}
        W->Busy=false;if(!Ok){W->Status=Error;return;}W->Token=D->GetStringField(TEXT("token"));W->Auto=true;W->Energy=1;W->Apply(D,true);W->LastContactAt=FPlatformTime::Seconds();W->Status=TEXT("已入园 · 点击草坪移动，或让它自主游玩。");W->NextSyncAt=FPlatformTime::Seconds()+.6;
    });
}
void APaitPark::Animate(FPaitParkPet& P,const FString& Clip){
    if(P.Clip==Clip)return;FString Name=P.Prefix+Clip;
    UAnimSequence* Anim=LoadObject<UAnimSequence>(nullptr,*(P.Root+Name+TEXT(".")+Name));
    if(!Anim){Name=P.Prefix+TEXT("idle_breathe");Anim=LoadObject<UAnimSequence>(nullptr,*(P.Root+Name+TEXT(".")+Name));}
    if(Anim)for(auto& Part:P.Parts)if(Part.IsValid())Part->GetSkeletalMeshComponent()->PlayAnimation(Anim,true);P.Clip=Clip;
}
void APaitPark::Apply(TSharedPtr<FJsonObject> D,bool Initial){
    Online=D->GetIntegerField(TEXT("count"));const TSharedPtr<FJsonObject>* Nav=nullptr;if(D->TryGetObjectField(TEXT("navigation"),Nav))Navigation=*Nav;
    TSet<FString> Present;
    for(auto& Value:D->GetArrayField(TEXT("players"))){auto Row=Value->AsObject();FString Id=Row->GetStringField(TEXT("id"));Present.Add(Id);bool Own=!Token.IsEmpty()&&Row->GetBoolField(TEXT("mine"));auto Spec=Row->GetObjectField(TEXT("spec"));int32 Kind=FCString::Atoi(*Spec->GetStringField(TEXT("id")));if(Kind<1||Kind>4)continue;
        if(Own){Mine=Id;if(Initial){Self=FVector2D(Row->GetNumberField(TEXT("x")),Row->GetNumberField(TEXT("z")));Yaw=Row->GetNumberField(TEXT("yaw"));}}
        auto& P=Pets.FindOrAdd(Id);
        if(P.Root.IsEmpty()){
            P.Root=Roots[Kind];P.Prefix=Prefixes[Kind];P.Name=Spec->GetStringField(TEXT("name"));P.Height=Spec->GetNumberField(TEXT("height"));
            auto& Registry=FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();TArray<FAssetData> Found;Registry.GetAssetsByPath(FName(*P.Root.LeftChop(1)),Found,true);
            for(auto& Asset:Found)if(Asset.AssetClassPath==USkeletalMesh::StaticClass()->GetClassPathName())if(auto* Mesh=Cast<USkeletalMesh>(Asset.GetAsset())){
                auto* Actor=GetWorld()->SpawnActor<ASkeletalMeshActor>();auto* C=Actor->GetSkeletalMeshComponent();C->SetSkeletalMesh(Mesh);C->SetCollisionEnabled(ECollisionEnabled::NoCollision);P.Parts.Add(Actor);
            }
            P.Position=World(Row->GetNumberField(TEXT("x")),Row->GetNumberField(TEXT("z")));Animate(P,TEXT("idle_breathe"));
            FBox Bounds(ForceInit);for(auto& Part:P.Parts)if(Part.IsValid())Bounds+=Part->GetSkeletalMeshComponent()->GetSkeletalMeshAsset()->GetBounds().GetBox();
            float Scale=Bounds.IsValid?P.Height*100/FMath::Max(1.,Bounds.GetSize().Z):1.f;
            for(auto& Part:P.Parts)if(Part.IsValid()){Part->SetActorScale3D(FVector(Scale));auto* C=Part->GetSkeletalMeshComponent();C->TickAnimation(0,false);C->RefreshBoneTransforms();}
            if(P.Parts.Num()&&P.Parts[0].IsValid()){auto* C=P.Parts[0]->GetSkeletalMeshComponent();
                FVector Forward=C->GetSocketLocation(TEXT("head"))-C->GetSocketLocation(TEXT("spine"));Forward.Z=0;P.HeadingOffset=Forward.Rotation().Yaw;
                float Sole=MAX_flt;for(const TCHAR* Bone:{TEXT("FL_foot"),TEXT("FR_foot"),TEXT("HL_foot"),TEXT("HR_foot")})if(C->GetBoneIndex(Bone)!=INDEX_NONE)Sole=FMath::Min(Sole,float(C->GetSocketLocation(Bone).Z));P.Lift=Sole<MAX_flt?3.f-Sole:0;
            }
        }
        float Y=0,Angle=Row->GetNumberField(TEXT("yaw"));const TSharedPtr<FJsonObject>* B=nullptr;
        if(Row->TryGetObjectField(TEXT("behavior"),B)){const TSharedPtr<FJsonObject>* F=nullptr;if((*B)->TryGetObjectField(TEXT("facility"),F)){
            float H=Angle;auto Point=SampleFacility((*F)->GetStringField(TEXT("id")),(*F)->GetNumberField(TEXT("progress")),H);Y=Point.Y;Angle=H;
            if(Own&&FacilityId==(*F)->GetStringField(TEXT("id"))){FacilityConfirmed=true;ConfirmedProgress=(*F)->GetNumberField(TEXT("progress"));}
        }}
        if(!Own){FVector Next=World(Row->GetNumberField(TEXT("x")),Row->GetNumberField(TEXT("z")),Y);bool Moving=FVector::DistSquared(Next,P.Position)>4;P.Position=Next;P.Heading=90-FMath::RadiansToDegrees(Angle)-P.HeadingOffset;Animate(P,Moving?TEXT("walk"):ClipFor(Row->GetStringField(TEXT("action"))));}
    }
    TArray<FString> Removed;for(auto& Pair:Pets)if(!Present.Contains(Pair.Key)){for(auto& Part:Pair.Value.Parts)if(Part.IsValid())Part->Destroy();Removed.Add(Pair.Key);}for(auto& Id:Removed)Pets.Remove(Id);
}
FVector APaitPark::SampleFacility(const FString& Id,float Distance,float& Heading)const{
    if(Navigation)for(auto& V:Navigation->GetArrayField(TEXT("facilities"))){auto F=V->AsObject();if(F->GetStringField(TEXT("id"))!=Id)continue;const auto& Points=F->GetArrayField(TEXT("path"));
        for(int32 I=1;I<Points.Num();++I){auto A=Points[I-1]->AsArray(),B=Points[I]->AsArray();FVector P(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber()),Q(B[0]->AsNumber(),B[1]->AsNumber(),B[2]->AsNumber());float N=FVector2D::Distance(FVector2D(P.X,P.Z),FVector2D(Q.X,Q.Z));if(Distance<=N||I==Points.Num()-1){Heading=FMath::Atan2(Q.X-P.X,Q.Z-P.Z);return FMath::Lerp(P,Q,FMath::Clamp(Distance/N,0.f,1.f));}Distance-=N;}}
    return FVector(Self.X,0,Self.Y);
}
void APaitPark::Sync(){
    if(Busy||Routing||!Account(this)->IsLoggedIn())return;Busy=true;NextSyncAt=FPlatformTime::Seconds()+.6;const uint64 E=Epoch;TWeakObjectPtr<APaitPark> W(this);
    auto B=MakeShared<FJsonObject>();bool Joined=!Token.IsEmpty();
    if(Joined){B->SetStringField(TEXT("token"),Token);B->SetNumberField(TEXT("x"),Self.X);B->SetNumberField(TEXT("z"),Self.Y);B->SetNumberField(TEXT("yaw"),Yaw);B->SetStringField(TEXT("action"),CurrentAction);auto Behavior=MakeShared<FJsonObject>();Behavior->SetStringField(TEXT("activity"),FacilityId.IsEmpty()?Activity:TEXT("facility"));Behavior->SetBoolField(TEXT("autonomous"),Auto);if(!FacilityId.IsEmpty()){auto F=MakeShared<FJsonObject>();F->SetStringField(TEXT("id"),FacilityId);F->SetNumberField(TEXT("progress"),Progress);Behavior->SetObjectField(TEXT("facility"),F);}B->SetObjectField(TEXT("behavior"),Behavior);}
    const bool SentGround=FacilityId.IsEmpty();
    Account(this)->Call(Joined?TEXT("POST"):TEXT("GET"),Joined?TEXT("park/sync"):TEXT("park"),B,[W,E,SentGround](bool Ok,TSharedPtr<FJsonObject> D,FString Error){if(!W.IsValid()||W->Epoch!=E)return;W->Busy=false;W->NextSyncAt=FPlatformTime::Seconds()+.6;if(!Ok){if(D&&D->GetIntegerField(TEXT("_http_status"))==429){W->Status=TEXT("同步稍后重试，伙伴仍在园内。");return;}if(!W->Token.IsEmpty()&&(!D||D->GetIntegerField(TEXT("_http_status"))>=500)&&FPlatformTime::Seconds()-W->LastContactAt<10){W->Status=TEXT("连接暂时变慢，正在恢复同步…");return;}W->Leave();W->Status=Error;W->NextSyncAt=FPlatformTime::Seconds()+3;return;}W->LastContactAt=FPlatformTime::Seconds();W->Apply(D);if(SentGround)W->GroundSyncPending=false;});
}
void APaitPark::Route(FVector2D Point){
    if(Token.IsEmpty()||Routing||Busy||GroundSyncPending||!FacilityId.IsEmpty())return;Path.Empty();Routing=true;const uint64 E=Epoch;TWeakObjectPtr<APaitPark> W(this);auto B=MakeShared<FJsonObject>();B->SetStringField(TEXT("token"),Token);B->SetNumberField(TEXT("x"),Point.X);B->SetNumberField(TEXT("z"),Point.Y);
    Account(this)->Call(TEXT("POST"),TEXT("park/route"),B,[W,E](bool Ok,TSharedPtr<FJsonObject> D,FString Error){if(!W.IsValid()||W->Epoch!=E)return;W->Routing=false;if(!Ok){W->Status=Error;W->PendingFacility.Empty();return;}for(auto& V:D->GetArrayField(TEXT("path"))){auto P=V->AsObject();W->Path.Add(FVector2D(P->GetNumberField(TEXT("x")),P->GetNumberField(TEXT("z"))));}W->Status=W->Path.Num()?TEXT("正沿草坪走过去…"):TEXT("那里暂时不能到达，请选择开阔草坪。");});
}
void APaitPark::MoveTo(FVector Point){ManualUntil=GetWorld()->GetTimeSeconds()+20;PendingFacility.Empty();Activity=TEXT("manual");Route(FVector2D(Point.X/100,Point.Y/100));}
void APaitPark::Action(FString Value){if(!FacilityId.IsEmpty()||Token.IsEmpty())return;Path.Empty();PendingFacility.Empty();CurrentAction=Value;ActionUntil=GetWorld()->GetTimeSeconds()+7;ManualUntil=ActionUntil+5;Activity=TEXT("manual");Status=TEXT("它正在回应你。");}
void APaitPark::Facility(FString Id){if(!Navigation||Token.IsEmpty()||GroundSyncPending||!FacilityId.IsEmpty())return;for(auto& V:Navigation->GetArrayField(TEXT("facilities"))){auto F=V->AsObject();if(F->GetStringField(TEXT("id"))!=Id)continue;if(auto* P=Pets.Find(Mine))if(P->Height>F->GetNumberField(TEXT("maxHeight"))){Status=TEXT("这项设施不适合它的体型。");return;}PendingFacility=Id;auto Start=F->GetArrayField(TEXT("path"))[0]->AsArray();Route(FVector2D(Start[0]->AsNumber(),Start[2]->AsNumber()));}}
void APaitPark::Think(){
    if(!Auto||Token.IsEmpty()||!Path.IsEmpty()||Routing||Busy||!FacilityId.IsEmpty()||GetWorld()->GetTimeSeconds()<ManualUntil)return;
    Energy=FMath::Clamp(Energy-.06f,0.f,1.f);
    if(Energy<.25){CurrentAction=TEXT("sleep");Activity=TEXT("rest");Energy+=.18;Status=TEXT("玩了一会儿，想在草坪歇歇。");DecisionIn=15;return;}
    int32 Choice=FMath::RandRange(0,6);DecisionIn=8;
    if(Choice==0){Facility(TEXT("bridge"));return;}if(Choice==1){Facility(TEXT("tunnel"));return;}
    if(Choice==2){for(auto& P:Pets)if(P.Key!=Mine){FVector2D Goal(P.Value.Position.X/100,P.Value.Position.Y/100);FVector2D Delta=(Self-Goal).GetSafeNormal();Route(Goal+Delta*1.5f);CurrentAction=TEXT("greet");Activity=TEXT("greet");return;}}
    if(Choice==3){CurrentAction=TEXT("sniff");Activity=TEXT("observe");Status=TEXT("闻闻草坪上新鲜的气味。");return;}
    CurrentAction=TEXT("idle");Activity=TEXT("explore");float A=FMath::FRand()*2*PI;Route(FVector2D(FMath::Cos(A)*5.5,FMath::Sin(A)*4.2));
}
void APaitPark::Tick(float Dt){
    Super::Tick(Dt);TickFixture(Dt);auto* A=Account(this);if(Session!=A->GetSessionRevision()){Token.Empty();++Epoch;Busy=Routing=false;GroundSyncPending=false;Path.Empty();FacilityId.Empty();ClearPets();Session=A->GetSessionRevision();Status=TEXT("账号已变化，请重新带伙伴入园。");}
    if(ActionUntil>0&&GetWorld()->GetTimeSeconds()>ActionUntil){ActionUntil=0;CurrentAction=TEXT("idle");}
    if(FPlatformTime::Seconds()>=NextSyncAt)Sync();DecisionIn-=Dt;if(DecisionIn<=0){DecisionIn=3;Think();}
    float Y=0;
    if(!Token.IsEmpty()){
        if(!FacilityId.IsEmpty()&&FacilityConfirmed&&Navigation){for(auto& V:Navigation->GetArrayField(TEXT("facilities"))){auto F=V->AsObject();if(F->GetStringField(TEXT("id"))!=FacilityId)continue;float Length=0;const auto& Points=F->GetArrayField(TEXT("path"));for(int I=1;I<Points.Num();++I){auto P=Points[I-1]->AsArray(),Q=Points[I]->AsArray();Length+=FVector2D::Distance(FVector2D(P[0]->AsNumber(),P[2]->AsNumber()),FVector2D(Q[0]->AsNumber(),Q[2]->AsNumber()));}
            // Keep progress at the endpoint through at least one completed sync.
            if(ConfirmedProgress>=Length-0.0001f&&!Busy){FacilityId.Empty();GroundSyncPending=true;CurrentAction=TEXT("sniff");Activity=TEXT("explore");DecisionIn=8;break;}
            // Bound prediction below the 0.6-second response-to-request interval.
            // Network latency must not accumulate a burst beyond the server speed allowance.
            Progress=FMath::Min(Length,FMath::Min(ConfirmedProgress+float(F->GetNumberField(TEXT("speed")))*.5f,Progress+float(F->GetNumberField(TEXT("speed")))*Dt));FVector Point=SampleFacility(FacilityId,Progress,Yaw);Self=FVector2D(Point.X,Point.Z);Y=Point.Y;break;}}
        else if(!Path.IsEmpty()&&!Busy&&!Routing){FVector2D Delta=Path[0]-Self;float Step=FMath::Min(Delta.Size(),Dt*1.2f);bool Blocked=false;for(auto& P:Pets)if(P.Key!=Mine&&FVector2D::Distance(FVector2D(P.Value.Position.X/100,P.Value.Position.Y/100),Self+Delta.GetSafeNormal()*Step)<.7f)Blocked=true;if(!Blocked){Self+=Delta.GetSafeNormal()*Step;Yaw=FMath::Atan2(Delta.X,Delta.Y);if(Delta.Size()<.04f)Path.RemoveAt(0);}}
        else if(!PendingFacility.IsEmpty()&&!Busy&&!Routing&&Path.IsEmpty()){FacilityId=PendingFacility;PendingFacility.Empty();Progress=0;ConfirmedProgress=0;FacilityConfirmed=false;}
        if(auto* P=Pets.Find(Mine)){P->Position=World(Self.X,Self.Y,Y);P->Heading=90-FMath::RadiansToDegrees(Yaw)-P->HeadingOffset;Animate(*P,(!Path.IsEmpty()||!FacilityId.IsEmpty())?TEXT("walk"):ClipFor(CurrentAction));}
    }
    for(auto& Pair:Pets)for(auto& Part:Pair.Value.Parts)if(Part.IsValid()){Part->SetActorLocation(FMath::VInterpTo(Part->GetActorLocation(),Pair.Value.Position+FVector(0,0,Pair.Value.Lift),Dt,12));Part->SetActorRotation(FMath::RInterpTo(Part->GetActorRotation(),FRotator(0,Pair.Value.Heading,0),Dt,10));}
}
void APaitPark::ShowInterface(bool Show){Hidden=!Show;for(TActorIterator<APaitExperience> E(GetWorld());E;++E)E->InterfaceHidden=Hidden;}
void APaitPark::Interface(){
    TWeakObjectPtr<APaitPark> W(this);auto Root=SNew(SOverlay).Visibility(EVisibility::SelfHitTestInvisible);
    auto Button=[W](const FString& Name,TFunction<void(APaitPark*)> F){return SNew(SButton).ButtonStyle(&ButtonStyle()).ContentPadding(FMargin(12,10)).OnClicked_Lambda([W,F](){if(W.IsValid())F(W.Get());return FReply::Handled();})[SNew(STextBlock).Text(FText::FromString(Name)).Font(FCoreStyle::GetDefaultFontStyle("Regular",15))];};
    auto Panel=SNew(SVerticalBox);Panel->AddSlot().AutoHeight()[SNew(STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Regular",24)).Text(FText::FromString(TEXT("爪心乐园 · 中心岛")))];
    Panel->AddSlot().AutoHeight().Padding(0,8)[SNew(STextBlock).Text_Lambda([W](){return FText::FromString(W.IsValid()?W->Status:TEXT(""));})];
    Panel->AddSlot().AutoHeight()[SNew(STextBlock).Text_Lambda([W](){if(!W.IsValid())return FText();FString S=FString::Printf(TEXT("在线伙伴 %d / 12"),W->Online);for(auto& P:W->Pets)S+=TEXT("  · ")+P.Value.Name;return FText::FromString(S);})];
    auto PetsRow=SNew(SHorizontalBox);const TCHAR* Names[]={TEXT("柴犬"),TEXT("哈士奇"),TEXT("猫咪"),TEXT("德牧")};
    for(int I=1;I<=4;++I)PetsRow->AddSlot().AutoWidth().Padding(3)[Button(Names[I-1],[I](APaitPark* P){if(P->Token.IsEmpty()&&!P->Busy){P->PetId=I;P->Status=FString(TEXT("已选择："))+(I==1?TEXT("柴犬"):I==2?TEXT("哈士奇"):I==3?TEXT("猫咪"):TEXT("德牧"));}})];
    PetsRow->AddSlot().AutoWidth().Padding(3)[Button(TEXT("带它入园"),[](APaitPark* P){P->Join();})];PetsRow->AddSlot().AutoWidth().Padding(3)[Button(TEXT("结束游玩"),[](APaitPark* P){P->Leave();})];Panel->AddSlot().AutoHeight().Padding(0,6)[PetsRow];
    auto Actions=SNew(SHorizontalBox);Actions->AddSlot().AutoWidth().Padding(3)[Button(TEXT("自主游玩 开/关"),[](APaitPark* P){P->Auto=!P->Auto;P->Status=P->Auto?TEXT("它会自己探索和休息。"):TEXT("已暂停自主选择，设施中会先返回草坪。");})];
    Actions->AddSlot().AutoWidth().Padding(3)[Button(TEXT("打招呼"),[](APaitPark* P){P->Action(TEXT("greet"));})];Actions->AddSlot().AutoWidth().Padding(3)[Button(TEXT("休息"),[](APaitPark* P){P->Action(TEXT("sleep"));})];
    Actions->AddSlot().AutoWidth().Padding(3)[Button(TEXT("走低桥"),[](APaitPark* P){P->Facility(TEXT("bridge"));})];Actions->AddSlot().AutoWidth().Padding(3)[Button(TEXT("猫耳隧道"),[](APaitPark* P){P->Facility(TEXT("tunnel"));})];Panel->AddSlot().AutoHeight()[Actions];
    Panel->AddSlot().AutoHeight().Padding(0,6)[SNew(SProgressBar).Visibility_Lambda([W](){return W.IsValid()&&(W->Busy||W->Routing)&&W->Token.IsEmpty()?EVisibility::Visible:EVisibility::Collapsed;}).Percent(TOptional<float>())];
    Root->AddSlot().HAlign(HAlign_Center).VAlign(VAlign_Bottom).Padding(20,22)[SNew(SBorder).BorderImage(&Glass).BorderBackgroundColor(FLinearColor(.025,.08,.065,.88)).Padding(18).Visibility_Lambda([W](){return W.IsValid()&&!W->Hidden&&!Account(W.Get())->IsPanelVisible()?EVisibility::Visible:EVisibility::Collapsed;})[Panel]];
    Root->AddSlot().HAlign(HAlign_Right).VAlign(VAlign_Center).Padding(20)[Button(TEXT("显示 / 隐藏界面"),[](APaitPark* P){P->ShowInterface(P->Hidden);})];
    Root->AddSlot().HAlign(HAlign_Right).VAlign(VAlign_Top).Padding(20,84)[Button(TEXT("全屏 / 窗口"),[](APaitPark*){auto* S=UGameUserSettings::GetGameUserSettings();S->SetFullscreenMode(S->GetFullscreenMode()==EWindowMode::Windowed?EWindowMode::WindowedFullscreen:EWindowMode::Windowed);S->ApplyResolutionSettings(false);})];
    Widget=Root;GetGameInstance()->GetGameViewportClient()->AddViewportWidgetContent(Root,11);
}
