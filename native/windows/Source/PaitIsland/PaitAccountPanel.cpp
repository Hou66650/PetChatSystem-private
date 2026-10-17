#include "PaitAccountPanel.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Notifications/SProgressBar.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Widgets/Input/SCheckBox.h"
#include "Brushes/SlateRoundedBoxBrush.h"

namespace
{
const FSlateRoundedBoxBrush PanelBrush(FLinearColor::White,20.f);
const FTextBlockStyle& ButtonTextStyle(){static const FTextBlockStyle Style=FTextBlockStyle(FCoreStyle::Get().GetWidgetStyle<FTextBlockStyle>("NormalText")).SetFont(FCoreStyle::GetDefaultFontStyle("Regular",14));return Style;}
FString Str(const TSharedPtr<FJsonObject>& O, const TCHAR* Key) { FString V; if(O) O->TryGetStringField(Key,V); return V; }
double Num(const TSharedPtr<FJsonObject>& O, const TCHAR* Key) { double V=0; if(O) O->TryGetNumberField(Key,V); return V; }
TArray<TSharedPtr<FJsonValue>> Rows(const TSharedPtr<FJsonObject>& O, const TCHAR* Key)
{ const TArray<TSharedPtr<FJsonValue>>* V=nullptr; return O && O->TryGetArrayField(Key,V) ? *V : TArray<TSharedPtr<FJsonValue>>(); }
TSharedPtr<FJsonObject> Params(const TCHAR* Key, const FString& Value)
{ auto O=MakeShared<FJsonObject>(); O->SetStringField(Key,Value); return O; }
}
void SPaitAccountPanel::Construct(const FArguments& Args)
{
    Account=Args._Account;
    ChildSlot.HAlign(HAlign_Right).VAlign(VAlign_Center)
    [SNew(SBox).WidthOverride(530).HeightOverride(670).Padding(18)
     [SNew(SBorder).BorderImage(&PanelBrush).BorderBackgroundColor(FLinearColor(.05f,.13f,.11f,.91f)).Padding(18)
      [SNew(SVerticalBox)
       +SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("派特岛 · 我的陪伴"))).Font(FCoreStyle::GetDefaultFontStyle("Bold",22))]
       +SVerticalBox::Slot().AutoHeight().Padding(0,10)[SNew(SHorizontalBox)
        +SHorizontalBox::Slot().AutoWidth()[SNew(SButton).Text(FText::FromString(TEXT("收起 · I"))).OnClicked_Lambda([this](){if(Account.IsValid())Account->TogglePanel();return FReply::Handled();})]
        +SHorizontalBox::Slot().FillWidth(1)[SNew(STextBlock).Text_Lambda([this](){return FText::FromString(Account.IsValid()?Account->Username:TEXT(""));})]]
       +SVerticalBox::Slot().AutoHeight()[SNew(SProgressBar).Visibility_Lambda([this](){return Busy||(Page==TEXT("farm")&&Account.IsValid()&&Account->GardenLoading)?EVisibility::Visible:EVisibility::Collapsed;}).Percent(TOptional<float>())]
       +SVerticalBox::Slot().AutoHeight().Padding(0,8)[SNew(STextBlock).AutoWrapText(true).Text_Lambda([this](){return FText::FromString(Message.IsEmpty()&&Page==TEXT("farm")&&Account.IsValid()?Account->GardenStatus:Message);})]
       +SVerticalBox::Slot().AutoHeight()[SNew(SButton).Text(FText::FromString(TEXT("重试未确认操作（沿用原回执）"))).Visibility_Lambda([this](){return Account.IsValid()&&Account->HasPendingMutation()?EVisibility::Visible:EVisibility::Collapsed;}).IsEnabled_Lambda([this](){return !Busy;}).OnClicked_Lambda([this](){Busy=true;TWeakPtr<SPaitAccountPanel> Weak=SharedThis(this);Account->RetryMutation([Weak](bool Ok,TSharedPtr<FJsonObject>,FString Error){if(auto S=Weak.Pin()){S->Busy=false;S->Message=Ok?TEXT("操作结果已确认"):Error;if(Ok)S->Load(S->Page);}});return FReply::Handled();})]
       +SVerticalBox::Slot().FillHeight(1)[SNew(SScrollBox)+SScrollBox::Slot()[SAssignNew(Content,SVerticalBox)]]]]];
    if(Account.IsValid() && Account->IsLoggedIn())Load(TEXT("account"));else Rebuild();
}
void SPaitAccountPanel::Line(const FString& Text)
{ Content->AddSlot().AutoHeight().Padding(0,6)[SNew(STextBlock).Text(FText::FromString(Text)).Font(FCoreStyle::GetDefaultFontStyle("Regular",14)).AutoWrapText(true)]; }
void SPaitAccountPanel::Button(const FString& Text,TFunction<void()> Action)
{ Content->AddSlot().AutoHeight().Padding(0,4)[SNew(SButton).TextStyle(&ButtonTextStyle()).ContentPadding(FMargin(12,7)).Text(FText::FromString(Text)).IsEnabled_Lambda([this](){return !Busy;}).OnClicked_Lambda([Action=MoveTemp(Action)](){Action();return FReply::Handled();})]; }
void SPaitAccountPanel::Chip(const FString& Text,TFunction<void()> Action,TSharedPtr<SWrapBox> Row)
{Row->AddSlot().Padding(3)[SNew(SButton).Text(FText::FromString(Text)).IsEnabled_Lambda([this](){return !Busy;}).OnClicked_Lambda([Action=MoveTemp(Action)](){Action();return FReply::Handled();})];}
void SPaitAccountPanel::Rebuild()
{
    Content->ClearChildren(); if(!Account.IsValid())return;
    if(!Account->IsLoggedIn())
    {
        Line(TEXT("使用已有派特岛账号登录。账户数据来自服务端；关闭客户端后需要重新登录。"));
        Content->AddSlot().AutoHeight().Padding(0,8)[SAssignNew(LoginName,SEditableTextBox).HintText(FText::FromString(TEXT("用户名")))];
        Content->AddSlot().AutoHeight().Padding(0,8)[SAssignNew(Password,SEditableTextBox).IsPassword(true).HintText(FText::FromString(TEXT("密码")))];
        if(RegisterMode)
        {
            Content->AddSlot().AutoHeight().Padding(0,8)[SAssignNew(PasswordConfirm,SEditableTextBox).IsPassword(true).HintText(FText::FromString(TEXT("再次输入密码（至少 8 位）")))];
            Button(TEXT("注册账号"),[this](){
                auto Body=Params(TEXT("username"),LoginName->GetText().ToString());Body->SetStringField(TEXT("password"),Password->GetText().ToString());Body->SetStringField(TEXT("password2"),PasswordConfirm->GetText().ToString());
                Password->SetText(FText::GetEmpty());PasswordConfirm->SetText(FText::GetEmpty());Busy=true;Message=TEXT("正在创建账号…");TWeakPtr<SPaitAccountPanel> Weak=SharedThis(this);
                Account->Call(TEXT("POST"),TEXT("registration"),Body,[Weak](bool Ok,TSharedPtr<FJsonObject>,FString Error){if(auto S=Weak.Pin()){S->Busy=false;S->Message=Ok?TEXT("注册成功，请登录"):Error;if(Ok){S->RegisterMode=false;S->Rebuild();}}});
            });
            Button(TEXT("返回登录"),[this](){RegisterMode=false;Rebuild();});return;
        }
        Button(TEXT("登录"),[this](){
            Busy=true; Message=TEXT("正在登录…"); const FString Secret=Password->GetText().ToString(); Password->SetText(FText::GetEmpty());
            TWeakPtr<SPaitAccountPanel> Weak=SharedThis(this);
            Account->Login(LoginName->GetText().ToString(),Secret,[Weak](bool Ok,TSharedPtr<FJsonObject>,FString Error){
                if(auto Self=Weak.Pin()){Self->Busy=false;Self->Message=Ok?TEXT("已登录"):Error;if(Ok)Self->Load(TEXT("account"));}
            });
        });
        Button(TEXT("创建新账号"),[this](){RegisterMode=true;Rebuild();});
        return;
    }
    TSharedPtr<SWrapBox> Tabs,Pets;
    Content->AddSlot().AutoHeight()[SAssignNew(Tabs,SWrapBox).UseAllottedSize(true)];
    for(const auto& Tab:TArray<TPair<FString,FString>>{{TEXT("account"),TEXT("账号")},{TEXT("supplies"),TEXT("补给")},{TEXT("farm"),TEXT("花园")},{TEXT("history"),TEXT("聊天")},{TEXT("voices"),TEXT("声音")}})
        Chip(Tab.Value,[this,Key=Tab.Key](){Account->CancelVoice();Load(Key);},Tabs);
    Line(FString::Printf(TEXT("当前伙伴：%s"),Account->PetId==1?TEXT("柴犬"):Account->PetId==2?TEXT("哈士奇"):Account->PetId==3?TEXT("猫咪"):TEXT("德牧")));
    Content->AddSlot().AutoHeight()[SAssignNew(Pets,SWrapBox).UseAllottedSize(true)];
    for(int32 Id=1;Id<=4;++Id)
        Chip(Id==1?TEXT("柴犬"):Id==2?TEXT("哈士奇"):Id==3?TEXT("猫咪"):TEXT("德牧"),[this,Id](){Account->SelectPet(Id);Load(Page);},Pets);
    Chip(TEXT("退出账号"),[this](){Account->Logout();Message=TEXT("本机登录已清除");Busy=false;Rebuild();},Pets);
}
void SPaitAccountPanel::Load(const FString& NewPage)
{
    if(!Account.IsValid())return;
    Page=NewPage;Rebuild();Busy=true;Message=TEXT("正在读取账号数据…");
    const uint64 Epoch=++ViewEpoch;
    TWeakPtr<SPaitAccountPanel> Weak=SharedThis(this);
    Account->Call(TEXT("GET"),Page+FString::Printf(TEXT("?petId=%d"),Account->PetId),nullptr,[Weak,Epoch](bool Ok,TSharedPtr<FJsonObject> Data,FString Error){
        if(auto Self=Weak.Pin()){if(Self->ViewEpoch!=Epoch)return;Self->Busy=false;Self->Message=Ok?TEXT(""):Error;Self->Rebuild();if(Ok)Self->Render(Data);}
    });
}
void SPaitAccountPanel::Mutate(const FString& Path,TSharedPtr<FJsonObject> Body)
{
    if(!Account.IsValid()||Busy)return;
    if(!Body)Body=MakeShared<FJsonObject>();
    Body->SetStringField(TEXT("token"),FGuid::NewGuid().ToString(EGuidFormats::Digits));
    Busy=true;Message=TEXT("正在保存，请稍候…");
    TWeakPtr<SPaitAccountPanel> Weak=SharedThis(this);
    Account->Mutate(Path,Body,[Weak,Path](bool Ok,TSharedPtr<FJsonObject> Data,FString Error){
        if(auto Self=Weak.Pin()){
            Self->Busy=false;Self->Message=Ok?TEXT("已保存到账号"):Error;
            if(Ok && Path==TEXT("chat")){const FString Text=Str(Data,TEXT("reply"));Self->Line(TEXT("它：")+Text);Self->Button(TEXT("用当前声音朗读"),[Weak,Text](){if(auto S=Weak.Pin())S->ReadAloud(Text);});}
            else if(Ok)Self->Load(Self->Page);
        }
    });
}
void SPaitAccountPanel::Render(TSharedPtr<FJsonObject> Data)
{
    if(Page==TEXT("account"))
    {Line(FString::Printf(TEXT("账号：%s · ID %.0f\n代币：%.0f"),*Str(Data,TEXT("username")),Num(Data,TEXT("accountId")),Num(Data,TEXT("balance"))));return;}
    if(Page==TEXT("supplies"))
    {
        Line(FString::Printf(TEXT("可用代币：%.0f"),Num(Data,TEXT("balance"))));
        const TSharedPtr<FJsonObject>* Stock=nullptr;Data->TryGetObjectField(TEXT("inventory"),Stock);
        for(auto Value:Rows(Data,TEXT("catalog"))){auto Item=Value->AsObject();const FString Id=Str(Item,TEXT("id"));
            Line(FString::Printf(TEXT("%s · 库存 %.0f"),*Str(Item,TEXT("name")),Stock?Num(*Stock,*Id):0));
            if(Str(Item,TEXT("kind"))!=TEXT("water"))Button(FString::Printf(TEXT("购买一份 · %.0f 代币"),Num(Item,TEXT("price"))),[this,Id](){Mutate(TEXT("supplies/buy"),Params(TEXT("item"),Id));});
        }
        Button(TEXT("领取今日补给"),[this](){Mutate(TEXT("supplies/daily"),nullptr);});return;
    }
    if(Page==TEXT("farm"))
    {
        Account->GardenState=Data;
        if(!Account->SelectedBed.IsEmpty())Button(TEXT("查看全部种植床"),[this](){Account->SelectedBed.Empty();Load(TEXT("farm"));});
        bool Started=false;Data->TryGetBoolField(TEXT("started"),Started);
        if(!Started){Button(TEXT("开启我的花园"),[this](){Mutate(TEXT("farm/start"),nullptr);});return;}
        const TSharedPtr<FJsonObject>* Stock=nullptr;Data->TryGetObjectField(TEXT("inventory"),Stock);
        const auto Catalog=Rows(Data,TEXT("catalog"));
        for(auto Value:Rows(Data,TEXT("beds")))
        {
            auto Bed=Value->AsObject();const FString Id=Str(Bed,TEXT("id")); const TSharedPtr<FJsonObject>* Plant=nullptr;
            if(!Account->SelectedBed.IsEmpty() && Account->SelectedBed!=Id)continue;
            if(Bed->TryGetObjectField(TEXT("plant"),Plant)){
                Line(Id+TEXT(" · ")+Str(*Plant,TEXT("species"))+FString::Printf(TEXT(" · 阶段 %.0f"),Num(*Plant,TEXT("stage"))));
                const FString PlantId=Str(*Plant,TEXT("id"));
                for(const auto& Op:TArray<TPair<FString,FString>>{{TEXT("water"),TEXT("浇水")},{TEXT("fertilize"),TEXT("施肥")},{TEXT("harvest"),TEXT("收获")}})
                    Button(Op.Value,[this,Id,PlantId,Key=Op.Key](){auto Body=Params(TEXT("bed"),Id);Body->SetStringField(TEXT("plant"),PlantId);Mutate(TEXT("farm/")+Key,Body);});
            }else{
                Line(Id+TEXT(" · 空闲"));
                for(auto C:Catalog){auto Species=C->AsObject();const FString Sid=Str(Species,TEXT("id"));if(!Stock||Num(*Stock,*(TEXT("seed:")+Sid))<1)continue;
                    Button(TEXT("种下 ")+Str(Species,TEXT("name")),[this,Id,Sid](){auto Body=Params(TEXT("bed"),Id);Body->SetStringField(TEXT("species"),Sid);Mutate(TEXT("farm/plant"),Body);});}
            }
        }
        for(auto Value:Rows(Data,TEXT("shop"))){auto Item=Value->AsObject();const FString Id=Str(Item,TEXT("id"));
            Button(Str(Item,TEXT("name"))+FString::Printf(TEXT(" · %.0f 代币"),Num(Item,TEXT("price"))),[this,Id](){Mutate(TEXT("farm/buy"),Params(TEXT("item"),Id));});}
        Line(TEXT("生长按服务端时间保存；植物将同步显示在猫岛种植床。自由移栽操作还在适配。"));return;
    }
    if(Page==TEXT("history"))
    {
        FString LastReply;
        for(auto Value:Rows(Data,TEXT("messages"))){auto Row=Value->AsObject();const bool User=Str(Row,TEXT("role"))==TEXT("user");const FString Text=Str(Row,TEXT("content"));Line((User?TEXT("你："):TEXT("它："))+Text);if(!User)LastReply=Text;}
        if(!LastReply.IsEmpty())Button(TEXT("朗读最近一条回复"),[this,LastReply](){ReadAloud(LastReply);});
        Content->AddSlot().AutoHeight().Padding(0,10)[SAssignNew(ChatInput,SEditableTextBox).HintText(FText::FromString(TEXT("想对它说些什么…")))];
        Button(TEXT("发送"),[this](){const FString Text=ChatInput->GetText().ToString();if(Text.TrimStartAndEnd().IsEmpty())return;
            auto Body=Params(TEXT("message"),Text);Body->SetNumberField(TEXT("petId"),Account->PetId);Body->SetStringField(TEXT("requestId"),FGuid::NewGuid().ToString(EGuidFormats::Digits));
            Line(TEXT("你：")+Text);ChatInput->SetText(FText::GetEmpty());Mutate(TEXT("chat"),Body);
        });return;
    }
    if(Page==TEXT("voices"))
    {
        Line(TEXT("声音仅用于当前选定宠物。录音先在本机试听，点击创建后才上传。"));
        const FString Active=Str(Data,TEXT("activeId"));
        for(auto Value:Rows(Data,TEXT("profiles"))){auto V=Value->AsObject();const FString Id=Str(V,TEXT("id"));
            Line(Str(V,TEXT("name"))+TEXT(" · ")+Str(V,TEXT("status"))+(Id==Active?TEXT(" · 已选用"):TEXT("")));
            if(Str(V,TEXT("status"))==TEXT("ready")){
                Button(TEXT("试听"),[this,Id](){Busy=true;Message=TEXT("正在生成试听…");TWeakPtr<SPaitAccountPanel> Weak=SharedThis(this);Account->PreviewVoice(Id,[Weak](bool Ok,TSharedPtr<FJsonObject>,FString E){if(auto S=Weak.Pin()){S->Busy=false;S->Message=Ok?TEXT("正在播放"):E;}});});
                Button(TEXT("使用这个声音"),[this,Id](){Account->CancelVoice();auto Body=Params(TEXT("id"),Id);Body->SetNumberField(TEXT("petId"),Account->PetId);Mutate(TEXT("voices/selection"),Body);});
            }
        }
        Button(TEXT("恢复默认声音"),[this](){Account->CancelVoice();auto Body=MakeShared<FJsonObject>();Body->SetField(TEXT("id"),MakeShared<FJsonValueNull>());Body->SetNumberField(TEXT("petId"),Account->PetId);Mutate(TEXT("voices/selection"),Body);});
        Line(TEXT("录制自己的声音 · 3–30 秒"));
        Content->AddSlot().AutoHeight().Padding(0,6)[SAssignNew(VoiceName,SEditableTextBox).HintText(FText::FromString(TEXT("给这个声音起个名字")))];
        Content->AddSlot().AutoHeight().Padding(0,6)[SAssignNew(VoiceTranscript,SEditableTextBox).HintText(FText::FromString(TEXT("录音原文（可选）")))];
        VoiceConsent=false;
        Content->AddSlot().AutoHeight()[SNew(SCheckBox).OnCheckStateChanged_Lambda([this](ECheckBoxState State){VoiceConsent=State==ECheckBoxState::Checked;})[SNew(STextBlock).Text(FText::FromString(TEXT("本人声音或已获得使用授权")))]];
        Content->AddSlot().AutoHeight().Padding(0,6)[SNew(SButton).IsEnabled_Lambda([this](){return !Busy;}).Text_Lambda([this](){return FText::FromString(Account->IsRecording()?FString::Printf(TEXT("结束录音 · %.0f 秒"),Account->RecordingSeconds()):TEXT("开始录音"));}).OnClicked_Lambda([this](){FString Error;const bool Was=Account->IsRecording();const bool Ok=Was?Account->StopRecording(Error):Account->StartRecording(Error);Message=Ok?(Was?TEXT("录音完成，请先试听"):TEXT("正在录音，最长 30 秒")):Error;return FReply::Handled();})];
        Button(TEXT("试听本次录音"),[this](){FString Error;Message=Account->PreviewRecording(Error)?TEXT("正在播放本次录音"):Error;});
        Button(TEXT("上传录音并创建专属声音"),[this](){
            Busy=true;Message=TEXT("正在上传录音…");TWeakPtr<SPaitAccountPanel> Weak=SharedThis(this);
            Account->UploadRecording(VoiceName->GetText().ToString(),VoiceTranscript->GetText().ToString(),VoiceConsent,[Weak](bool Ok,TSharedPtr<FJsonObject>,FString Error){
                if(auto Self=Weak.Pin()){Self->Busy=false;Self->Message=Ok?TEXT("已提交，声音创建完成后可选用。点击刷新查看进度。 "):Error;}
            });
        });
        Button(TEXT("刷新创建进度"),[this](){Load(TEXT("voices"));});
    }
}
void SPaitAccountPanel::ReadAloud(const FString& Text)
{
    if(!Account.IsValid() || Busy)return;Busy=true;Message=TEXT("正在使用当前声音生成语音…");TWeakPtr<SPaitAccountPanel> Weak=SharedThis(this);
    Account->Call(TEXT("GET"),FString::Printf(TEXT("voices?petId=%d"),Account->PetId),nullptr,[Weak,Text](bool Ok,TSharedPtr<FJsonObject> Data,FString Error){
        if(auto Self=Weak.Pin()){
            if(!Ok){Self->Busy=false;Self->Message=Error;return;}
            Self->Account->Speak(Text,Str(Data,TEXT("activeId")),[Weak](bool Played,TSharedPtr<FJsonObject>,FString E){if(auto S=Weak.Pin()){S->Busy=false;S->Message=Played?TEXT("正在播放"):E;}});
        }
    });
}
