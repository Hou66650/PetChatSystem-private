import { UIAbility } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { TabletDesktopHost } from '../service/TabletDesktopHost';

export default class EntryAbility extends UIAbility {
  onForeground(): void { AppStorage.setOrCreate('paitAppForeground', true); }
  onBackground(): void { AppStorage.setOrCreate('paitAppForeground', false); }
  onWindowStageCreate(windowStage: window.WindowStage): void {
    TabletDesktopHost.shared().setContext(this.context);
    windowStage.loadContent('pages/WebPage');
  }
  onDestroy(): void { TabletDesktopHost.shared().cancel(); }
}
