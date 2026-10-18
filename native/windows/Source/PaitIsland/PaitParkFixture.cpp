#include "PaitPark.h"
#include "PaitAccountSubsystem.h"
#include "PaitPreviewPawn.h"
#include "Engine/GameInstance.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "UnrealClient.h"

void APaitPark::TickFixture(float Dt){
    if(!FParse::Param(FCommandLine::Get(),TEXT("PaitParkFixture")))return;
    TestTime+=Dt;FString Dir;FParse::Value(FCommandLine::Get(),TEXT("PaitEvidenceDir="),Dir);if(Dir.IsEmpty())return;
    auto* A=GetGameInstance()->GetSubsystem<UPaitAccountSubsystem>();TWeakObjectPtr<APaitPark> W(this);
    if(TestStep==0&&TestTime>8){TestStep=1;
        A->Call(TEXT("GET"),TEXT("bootstrap"),nullptr,[W](bool Ok,TSharedPtr<FJsonObject> D,FString){
            if(!W.IsValid())return;bool Fixture=false;if(!Ok||!D->TryGetBoolField(TEXT("fixture"),Fixture)||!Fixture){W->Status=TEXT("Refusing non-fixture API");W->TestStep=99;return;}
            W->GetGameInstance()->GetSubsystem<UPaitAccountSubsystem>()->Login(TEXT("native-check-a"),TEXT("native-isolated-check"),[W](bool Success,TSharedPtr<FJsonObject>,FString Error){if(!W.IsValid())return;if(!Success){W->Status=Error;W->TestStep=99;return;}W->Session=W->GetGameInstance()->GetSubsystem<UPaitAccountSubsystem>()->GetSessionRevision();W->Busy=false;W->Join();W->TestStep=2;});
        });
    }
    if(TestStep==2&&!Token.IsEmpty()&&!Busy&&Navigation){Auto=false;ManualUntil=10000;Facility(TEXT("bridge"));TestStep=3;}
    if(TestStep==3&&FacilityId==TEXT("bridge")&&Progress>5){TestBridge=true;if(auto* P=Pets.Find(Mine))TestHeight=FMath::Max(TestHeight,float(P->Position.Z));}
    if(TestStep==3&&TestBridge&&FacilityId.IsEmpty()&&!Busy){FScreenshotRequest::RequestScreenshot(Dir/TEXT("park-bridge.png"),true,false);TestStep=4;}
    if(TestStep==4&&!Busy&&!GroundSyncPending){Facility(TEXT("tunnel"));TestStep=5;}
    if(TestStep==5&&FacilityId==TEXT("tunnel")&&Progress>7)TestTunnel=true;
    if(TestStep==5&&TestTunnel&&FacilityId.IsEmpty()&&!Busy&&!GroundSyncPending){FScreenshotRequest::RequestScreenshot(Dir/TEXT("park-play.png"),true,false);TestStep=6;ActionUntil=TestTime+3;}
    if((TestStep==6&&TestTime>ActionUntil)||TestTime>260||TestStep==99){
        auto Report=MakeShared<FJsonObject>();bool Pass=TestStep==6&&TestBridge&&TestTunnel&&TestHeight>30&&Pets.Contains(Mine)&&Pets[Mine].Parts.Num()>0;
        Report->SetBoolField(TEXT("passed"),Pass);Report->SetStringField(TEXT("status"),Status);Report->SetNumberField(TEXT("step"),TestStep);Report->SetNumberField(TEXT("bridge_height_cm"),TestHeight);Report->SetNumberField(TEXT("rendered_pets"),Pets.Num());Report->SetBoolField(TEXT("production_mutations"),false);Report->SetBoolField(TEXT("manual_mouse_verified"),false);Report->SetBoolField(TEXT("full_web_parity"),false);
        Report->SetStringField(TEXT("facility"),FacilityId);Report->SetNumberField(TEXT("progress"),Progress);Report->SetNumberField(TEXT("confirmed_progress"),ConfirmedProgress);Report->SetBoolField(TEXT("ground_sync_pending"),GroundSyncPending);Report->SetBoolField(TEXT("request_pending"),Busy);Report->SetNumberField(TEXT("path_points"),Path.Num());
        FString Json;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Json));FFileHelper::SaveStringToFile(Json,*(Dir/TEXT("park-gameplay.json")));Leave();FPlatformMisc::RequestExitWithStatus(false,Pass?0:2);
    }
}
