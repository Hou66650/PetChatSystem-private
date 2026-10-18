import { webview } from '@kit.ArkWeb';
import { TabletDesktopHost } from '../service/TabletDesktopHost';

interface DesktopFrame { close: boolean; dx: number; dy: number; }
@Entry
@Component
struct DesktopPet {
  @StorageLink('paitDesktopOrigin') private origin: string = '';
  @StorageLink('paitDesktopCode') private code: string = '';
  @StorageLink('paitDesktopVisible') private visible: boolean = true;
  @StorageLink('paitDesktopClosing') private closing: boolean = false;
  private controller: webview.WebviewController = new webview.WebviewController();
  private timer: number = -1;
  private busy: boolean = false;
  private alive: boolean = false;
  aboutToAppear(): void { this.alive = true; }
  aboutToDisappear(): void { this.alive = false; if (this.timer !== -1) { clearInterval(this.timer); this.timer = -1; } }
  private async poll(): Promise<void> {
    if (!this.alive || this.busy || this.controller.getUrl() !== this.origin + '/tablet-companion') { return; }
    this.busy = true;
    try {
      const raw = await this.controller.runJavaScript('window.PaitTabletRenderer?.exchange(' +
        JSON.stringify({ code: this.code, visible: this.visible, closing: this.closing }) + ')');
      if (!this.alive || raw.length > 256) { return; }
      const decoded = raw.startsWith('"') ? JSON.parse(raw) as string : raw;
      const frame = JSON.parse(decoded) as DesktopFrame;
      if (frame?.close === true) { TabletDesktopHost.shared().cancel(); }
      else if (frame) { TabletDesktopHost.shared().move(frame.dx, frame.dy); }
    } catch (_) {} finally { this.busy = false; }
  }
  build() {
    Stack() {
    Web({ src: this.origin + '/tablet-companion', controller: this.controller })
      .width('100%').height('100%').backgroundColor(Color.Transparent)
      .javaScriptAccess(true).domStorageAccess(false).fileAccess(false)
      .mixedMode(MixedMode.None).multiWindowAccess(false)
      .onPageEnd(() => { if (this.timer === -1) { this.timer = setInterval(() => { this.poll(); }, 50); } })
      .onOverrideUrlLoading((request) => request.getRequestUrl() !== this.origin + '/tablet-companion')
      .onErrorReceive((event) => { if (event?.request.isMainFrame()) { TabletDesktopHost.shared().cancel(); } })
    }.width('100%').height('100%').backgroundColor(Color.Transparent)
  }
}
