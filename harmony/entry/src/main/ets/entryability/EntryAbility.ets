import { UIAbility } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';

export default class EntryAbility extends UIAbility {
  onForeground(): void { AppStorage.setOrCreate('paitAppForeground', true); }
  onBackground(): void { AppStorage.setOrCreate('paitAppForeground', false); }
  onWindowStageCreate(windowStage: window.WindowStage): void {
    windowStage.loadContent('pages/WebPage');
  }
}
