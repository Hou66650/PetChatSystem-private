#include "PaitExperience.h"
#include "PaitPreviewPawn.h"
#include "PaitMeadowPet.h"
#include "PaitAccountSubsystem.h"
#include "Engine/GameInstance.h"
#include "Engine/GameViewportClient.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Widgets/SOverlay.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SBackgroundBlur.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Notifications/SProgressBar.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "MoviePlayer.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"
#include "HAL/FileManager.h"

namespace {
const TCHAR* Keys[]={TEXT("Sakura"),TEXT("Snow"),TEXT("Meadow"),TEXT("Camp"),TEXT("Park")};
const TCHAR* Names[]={TEXT("樱花庭院"),TEXT("雪境木屋"),TEXT("雾林温室"),TEXT("山岭营地"),TEXT("爪心乐园")};
const TCHAR* Pets[]={TEXT("球球 · 柴犬"),TEXT("雪球 · 哈士奇"),TEXT("团子 · 猫咪"),TEXT("德牧"),TEXT("公共中心岛")};
const TCHAR* Descriptions[]={TEXT("风吹过花瓣，它跑过桥来迎接你。"),TEXT("踩着松软的雪，一起去找新的快乐。"),TEXT("阳光落在叶子上，留一会儿给慵懒。"),TEXT("山风与远方，还有始终陪着你的它。"),TEXT("带伙伴去草坪上认识新朋友，一起自在游玩。")};
const FVector Centers[]={FVector(-2700,-350,-100),FVector(-1300,-2300,0),FVector(1300,-2300,-100),FVector(2700,-350,-100),FVector(0,1900,0)};
const FSlateRoundedBoxBrush Glass(FLinearColor::White,18.f);
const FLinearColor Ink(.9f,.94f,.88f), Shade(.025f,.08f,.065f,.75f);
TSharedRef<SWidget> Text(const FString& Value,int32 Size=16){return SNew(STextBlock).Text(FText::FromString(Value)).Font(FCoreStyle::GetDefaultFontStyle("Regular",Size)).ColorAndOpacity(Ink);}
const FButtonStyle& SoftButton(){static const FButtonStyle S=FButtonStyle().SetNormal(FSlateRoundedBoxBrush(FLinearColor(.06f,.14f,.12f,.76f),18.f)).SetHovered(FSlateRoundedBoxBrush(FLinearColor(.14f,.28f,.22f,.92f),18.f)).SetPressed(FSlateRoundedBoxBrush(FLinearColor(.2f,.35f,.27f),18.f));return S;}
TSharedRef<SWidget> Button(const FString& Value,TFunction<void()> Action){return SNew(SButton).ButtonStyle(&SoftButton()).ContentPadding(FMargin(18,12)).OnClicked_Lambda([Action](){Action();return FReply::Handled();})[Text(Value)];}
APaitPreviewPawn* Pawn(AActor* A){return Cast<APaitPreviewPawn>(UGameplayStatics::GetPlayerPawn(A,0));}
int32 FlowStep=0;
}
APaitExperience::APaitExperience(){PrimaryActorTick.bCanEverTick=true;}
bool APaitExperience::IsHome()const{return GetWorld()->GetMapName().Contains(TEXT("IslandHome"));}
void APaitExperience::BeginPlay(){Super::BeginPlay();BuildInterface();}
void APaitExperience::EndPlay(const EEndPlayReason::Type Reason){
    if(Interface.IsValid()&&GetGameInstance()->GetGameViewportClient())GetGameInstance()->GetGameViewportClient()->RemoveViewportWidgetContent(Interface.ToSharedRef());
    Interface.Reset();Super::EndPlay(Reason);
}
void APaitExperience::Account(){if(auto* A=GetGameInstance()->GetSubsystem<UPaitAccountSubsystem>())A->TogglePanel();}
void APaitExperience::Select(int32 Index){
    if(!Destination.IsEmpty()||Index<0||Index>4)return;
    Selected=Index;AutoOrbit=false;
    if(auto* P=Pawn(this))P->SetExperienceView(Centers[Index],3600,-34,-90,true);
}
void APaitExperience::Overview(){Selected=INDEX_NONE;AutoOrbit=false;if(auto* P=Pawn(this))P->SetExperienceView(FVector(0,450,-150),11000,-48,-90,true);}
bool APaitExperience::Click(AActor* Target){
    if(!IsHome())return false;
    for(int32 I=0;I<5;++I)if(Target&&Target->ActorHasTag(FName(*(FString(TEXT("Home"))+Keys[I])))){
        const double Now=FPlatformTime::Seconds();if(Selected==I&&Now-LastClick<.45)Enter();else Select(I);LastClick=Now;break;
    }return true;
}
void APaitExperience::Enter(){if(Selected==INDEX_NONE||!Destination.IsEmpty())return;Travel(Selected==4?TEXT("/Game/Preview/P2_Park"):FString(TEXT("/Game/Preview/P1_"))+Keys[Selected]+TEXT("V2"));if(auto* P=Pawn(this))P->SetExperienceView(Centers[Selected],1100,-22,-90,true);}
void APaitExperience::ReturnHome(){if(!IsHome())Travel(TEXT("/Game/Preview/P2_IslandHome"));}
void APaitExperience::Travel(const FString& Map){
    if(!Destination.IsEmpty())return;
    if(auto* A=GetGameInstance()->GetSubsystem<UPaitAccountSubsystem>()){if(A->IsPanelVisible())A->TogglePanel();else A->CancelVoice();}
    Destination=Map;Flight=.001f;AutoOrbit=false;
}
void APaitExperience::Tick(float Dt){
    Super::Tick(Dt);Elapsed+=Dt;
    if(AutoOrbit&&Destination.IsEmpty())if(auto* P=Pawn(this))P->OrbitExperience(Dt*5);
    if(!Destination.IsEmpty()){
        Flight+=Dt;
        if(Flight>1.4f){
            FLoadingScreenAttributes L;L.bAutoCompleteWhenLoadingCompletes=true;L.MinimumLoadingScreenDisplayTime=.5f;
            L.WidgetLoadingScreen=SNew(SBorder).BorderBackgroundColor(FLinearColor(.035f,.09f,.08f)).HAlign(HAlign_Center).VAlign(VAlign_Center)
                [SNew(SBox).WidthOverride(440)[SNew(SVerticalBox)+SVerticalBox::Slot().AutoHeight().Padding(0,16)[Text(TEXT("穿过云海，去它的身边…"),24)]+SVerticalBox::Slot().AutoHeight()[SNew(SProgressBar).Percent(TOptional<float>())]]];
            if(GetMoviePlayer())GetMoviePlayer()->SetupLoadingScreen(L);
            const FString Map=Destination;Destination.Empty();UGameplayStatics::OpenLevel(this,FName(*Map));return;
        }
    }
    if(!FParse::Param(FCommandLine::Get(),TEXT("PaitHomeFlow")))return;
    FString Dir;FParse::Value(FCommandLine::Get(),TEXT("PaitEvidenceDir="),Dir);
    if(Dir.IsEmpty())return;
    if(IsHome()){
        if(FlowStep==5&&Elapsed>5){FFileHelper::SaveStringToFile(TEXT("{\"passed\":true,\"islands_entered\":5,\"returned_home\":5,\"manual_mouse_checked\":false}"),*(Dir/TEXT("home-flow.json")));FPlatformMisc::RequestExit(false);return;}
        if(Elapsed>6&&Selected==INDEX_NONE)Select(FlowStep);
        if(Elapsed>12&&Elapsed-Dt<=12)FScreenshotRequest::RequestScreenshot(Dir/FString::Printf(TEXT("home-%d.png"),FlowStep),true,false);
        if(Elapsed>15&&Destination.IsEmpty())Enter();
    }else{
        if(Elapsed>8&&Elapsed-Dt<=8)FScreenshotRequest::RequestScreenshot(Dir/FString::Printf(TEXT("island-%d.png"),FlowStep),true,false);
        if(Elapsed>10&&Destination.IsEmpty()){
            if(!GetWorld()->GetMapName().Contains(Keys[FlowStep])){FPlatformMisc::RequestExitWithStatus(false,2);return;}
            ++FlowStep;ReturnHome();
        }
    }
}
void APaitExperience::BuildInterface(){
    TWeakObjectPtr<APaitExperience> W(this);
    auto Root=SNew(SOverlay).Visibility(EVisibility::SelfHitTestInvisible);
    auto Main=SNew(SOverlay).Visibility_Lambda([W](){if(!W.IsValid()||W->InterfaceHidden)return EVisibility::Collapsed;auto* A=W->GetGameInstance()->GetSubsystem<UPaitAccountSubsystem>();return A&&A->IsPanelVisible()?EVisibility::Collapsed:EVisibility::SelfHitTestInvisible;});
    Root->AddSlot()[Main];
    Main->AddSlot().HAlign(HAlign_Fill).VAlign(VAlign_Top).Padding(28,20)
      [SNew(SHorizontalBox)+SHorizontalBox::Slot().AutoWidth()[Text(TEXT("派特岛"),26)]
       +SHorizontalBox::Slot().FillWidth(1).Padding(24,5)[Text(IsHome()?TEXT("云端群岛 / ABOVE THE CLOUDS"):TEXT("留一点时间，陪它慢慢生活。"),14)]
       +SHorizontalBox::Slot().AutoWidth()[Button(IsHome()?TEXT("群岛全景"):TEXT("返回群岛"),[W](){if(W.IsValid()){if(W->IsHome())W->Overview();else W->ReturnHome();}})]
       +SHorizontalBox::Slot().AutoWidth().Padding(8,0)[Button(TEXT("我的陪伴 / 登录"),[W](){if(W.IsValid())W->Account();})]];
    if(IsHome()){
        Main->AddSlot().HAlign(HAlign_Left).VAlign(VAlign_Top).Padding(46,115)
          [SNew(SVerticalBox).Visibility_Lambda([W](){return W.IsValid()&&W->Selected==INDEX_NONE?EVisibility::SelfHitTestInvisible:EVisibility::Collapsed;})+SVerticalBox::Slot().AutoHeight()[Text(TEXT("在云海尽头，\n与你相遇。"),38)]
           +SVerticalBox::Slot().AutoHeight().Padding(0,18)[Text(TEXT("穿过山风与晨雾，抵达它等你的地方。"),15)]
           +SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Left)[Button(TEXT("自动环绕"),[W](){if(W.IsValid())W->AutoOrbit=!W->AutoOrbit;})]];
        auto Choices=SNew(SHorizontalBox);
        for(int32 I=0;I<5;++I)Choices->AddSlot().FillWidth(1).Padding(4)[SNew(SButton).ButtonStyle(&SoftButton()).ContentPadding(FMargin(20,15))
            .ButtonColorAndOpacity_Lambda([W,I](){return W.IsValid()&&W->Selected==I?FLinearColor(.24f,.4f,.32f,.95f):Shade;})
            .OnClicked_Lambda([W,I](){if(W.IsValid())W->Select(I);return FReply::Handled();})
            [SNew(SVerticalBox)+SVerticalBox::Slot().AutoHeight()[Text(Names[I],20)]+SVerticalBox::Slot().AutoHeight().Padding(0,5)[Text(Pets[I],13)]]];
        Main->AddSlot().HAlign(HAlign_Center).VAlign(VAlign_Bottom).Padding(32,24)
          [SNew(SBox).MaxDesiredWidth(1050)[SNew(SVerticalBox)
           +SVerticalBox::Slot().AutoHeight().Padding(8,12)[SNew(SHorizontalBox).Visibility_Lambda([W](){return W.IsValid()&&W->Selected>=0?EVisibility::SelfHitTestInvisible:EVisibility::Collapsed;})
            +SHorizontalBox::Slot().FillWidth(1)[SNew(SVerticalBox)
             +SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Regular",28)).ColorAndOpacity(Ink).Text_Lambda([W](){return FText::FromString(W.IsValid()&&W->Selected>=0?Names[W->Selected]:TEXT("五座岛屿，一片属于你的世界"));})]
             +SVerticalBox::Slot().AutoHeight().Padding(0,6)[SNew(STextBlock).ColorAndOpacity(Ink).Text_Lambda([W](){return FText::FromString(W.IsValid()&&W->Selected>=0?Descriptions[W->Selected]:TEXT("点击岛屿近看 · 右键环绕 · 滚轮缩放"));})]]
            +SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[SNew(SBox).Visibility_Lambda([W](){return W.IsValid()&&W->Selected>=0?EVisibility::Visible:EVisibility::Hidden;})[Button(TEXT("进入小岛  ↗"),[W](){if(W.IsValid())W->Enter();})]]]
           +SVerticalBox::Slot().AutoHeight()[Choices]]];
    }else if(!GetWorld()->GetMapName().Contains(TEXT("P2_Park"))){
        auto Actions=SNew(SHorizontalBox);
        const TCHAR* Labels[]={TEXT("叫它过来"),TEXT("抚摸"),TEXT("吃饭"),TEXT("喝水"),TEXT("玩耍"),TEXT("回窝"),TEXT("聊天 / 语音")};
        for(int32 I=0;I<7;++I)Actions->AddSlot().AutoWidth().Padding(3)[Button(Labels[I],[W,I](){if(!W.IsValid())return;if(I==6){W->Account();return;}for(TActorIterator<APaitMeadowPet> P(W->GetWorld());P;++P){if(I==0)P->Greet();if(I==1)P->Pet();if(I>=2)P->Care(I==2?TEXT("food"):I==3?TEXT("water"):I==4?TEXT("toy"):TEXT("home"));break;}})];
        Main->AddSlot().HAlign(HAlign_Center).VAlign(VAlign_Bottom).Padding(20,24)[SNew(SBorder).BorderImage(&Glass).BorderBackgroundColor(Shade).Padding(10)[Actions]];
    }
    Root->AddSlot().HAlign(HAlign_Fill).VAlign(VAlign_Fill)
      [SNew(SBorder).Visibility_Lambda([W](){return W.IsValid()&&W->Flight>0?EVisibility::Visible:EVisibility::Collapsed;})
       .BorderBackgroundColor_Lambda([W](){return FLinearColor(.78f,.87f,.83f,W.IsValid()?FMath::Clamp((W->Flight-.3f)/1.1f,0.f,1.f):0.f);})
       .HAlign(HAlign_Center).VAlign(VAlign_Center)[SNew(SBox).WidthOverride(440)[SNew(SVerticalBox)
        +SVerticalBox::Slot().AutoHeight().Padding(0,16)[Text(TEXT("正在穿过云海…"),24)]
        +SVerticalBox::Slot().AutoHeight()[SNew(SProgressBar).Percent(TOptional<float>())]]]];
    Interface=Root;GetGameInstance()->GetGameViewportClient()->AddViewportWidgetContent(Root,10);
}
