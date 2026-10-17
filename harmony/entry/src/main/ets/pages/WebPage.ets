import { webview } from '@kit.ArkWeb';
import { preferences } from '@kit.ArkData';
import { abilityAccessCtrl, common, Permissions } from '@kit.AbilityKit';
import { picker } from '@kit.CoreFileKit';
import { PetApi } from '../service/PetApi';
import BuildProfile from '../../../../build/default/generated/profile/default/BuildProfile';
import { NativePreview } from '../components/NativePreview';
import { NativeDenNode } from '../components/NativeDenNode';
import { DenAck, parseDenFrame, isDenPage } from '../model/NativeDenProtocol';

// Render the existing site directly: no replacement UI, injected CSS or copied business logic.
@Entry
@Component
struct WebPage {
  @State private address: string = 'http://192.168.43.6:5005';
  @State private source: string = '';
  @State private settings: boolean = true;
  @State private allowLan: boolean = true;
  @State private error: string = '';
  @State private nativePreview: boolean = false;
  @State private petMode: boolean = false;
  @State private foreground: boolean = true;
  @State private denAttached: boolean = false;
  @State private denWidth: number = 0;
  @State private denHeight: number = 0;
  @State private denX: number = 0;
  @State private denY: number = 0;
  private denNode: NativeDenNode | null = null;
  private denEmbedId: string = '';
  private denTimer: number = -1;
  private denEpoch: number = 0;
  private denPending: boolean = false;
  private controller: webview.WebviewController = new webview.WebviewController();
  private fullScreen: FullScreenExitHandler | null = null;

  aboutToAppear(): void {
    webview.WebviewController.setWebDebuggingAccess(BuildProfile.DEBUG);
    this.restore();
  }

  onPageShow(): void { this.foreground = true; this.denNode?.setActive(true); }
  onPageHide(): void { this.foreground = false; this.denNode?.setActive(false); }
  aboutToDisappear(): void { this.stopDen(); }

  private denOrigin(): string { return this.source.replace(/\/$/, ''); }
  private trustedDen(): boolean {
    try { return !this.settings && !this.nativePreview && isDenPage(this.controller.getUrl(), this.denOrigin()); }
    catch (_) { return false; }
  }
  private stopDen(): void {
    this.denEpoch++; this.denPending = false;
    if (this.denTimer !== -1) { clearInterval(this.denTimer); this.denTimer = -1; }
    this.denAttached = false; this.denNode?.dispose(); this.denNode = null; this.denEmbedId = '';
  }
  private startDen(): void {
    if (!this.trustedDen() || this.denTimer !== -1) { return; }
    this.denTimer = setInterval(() => { this.pollDen(); }, 33);
    this.pollDen();
  }
  private async pollDen(): Promise<void> {
    if (!this.foreground || this.denPending || !this.trustedDen()) { return; }
    const epoch = this.denEpoch; this.denPending = true;
    const ack: DenAck = this.denNode?.ack() || { session: '', key: '', ready: false };
    try {
      if (ack.status?.startsWith('unavailable:')) {
        await this.controller.runJavaScript('window.PaitNativeDen?.unavailable()');
        if (epoch === this.denEpoch) { this.stopDen(); }
        return;
      }
      const raw = await this.controller.runJavaScript('window.PaitNativeDen ? window.PaitNativeDen.exchange(' + JSON.stringify(ack) + ') : null');
      if (epoch !== this.denEpoch || !this.trustedDen()) { return; }
      const frame = parseDenFrame(raw);
      if (frame) { this.denNode?.accept(frame); }
      else { this.denNode?.setActive(false); }
      if (frame && this.foreground) { this.denNode?.setActive(true); }
    } catch (_) { this.denNode?.setActive(false); }
    finally { if (epoch === this.denEpoch) { this.denPending = false; } }
  }
  private embedChanged(event: NativeEmbedDataInfo): void {
    if (event.status === NativeEmbedStatus.DESTROY) {
      if (event.embedId === this.denEmbedId) {
        this.denAttached = false; this.denNode?.dispose(); this.denNode = null; this.denEmbedId = '';
      }
      return;
    }
    if (!this.trustedDen() || event.info?.id !== 'pait-native-pet' || event.info?.type !== 'native/paitpet') { return; }
    const context = this.getUIContext();
    const width = context.px2vp(event.info.width || 0); const height = context.px2vp(event.info.height || 0);
    if (width <= 0 || height <= 0 || width > 8000 || height > 8000) { return; }
    this.denWidth = width; this.denHeight = height;
    this.denX = context.px2vp(Number(event.info.position?.x || 0));
    this.denY = context.px2vp(Number(event.info.position?.y || 0));
    if (event.status === NativeEmbedStatus.CREATE && event.surfaceId) {
      this.denNode?.dispose();
      const host = context.getHostContext(); if (!host) { return; }
      this.denNode = new NativeDenNode(event.surfaceId, width, height, this.denOrigin(), host.cacheDir);
      this.denEmbedId = event.embedId || ''; this.denAttached = true;
    } else if (event.embedId === this.denEmbedId) { this.denNode?.resize(width, height); }
  }

  private async restore(): Promise<void> {
    try {
      const context = this.getUIContext().getHostContext();
      if (!context) { return; }
      const store = await preferences.getPreferences(context, { name: 'website' });
      const saved = await store.get('address', '') as string;
      if (saved) {
        this.address = saved;
        this.allowLan = await store.get('allowLan', false) as boolean;
        await this.open();
      }
    } catch (_) { this.error = '无法读取上次地址，请重新打开。'; }
  }

  private async open(): Promise<void> {
    try {
      const address = this.address.trim().replace(/\/$/, '');
      new PetApi().configure(address, this.allowLan);
      this.error = '';
      this.source = address + '/';
      this.settings = false;
      const context = this.getUIContext().getHostContext();
      if (context) {
        const store = await preferences.getPreferences(context, { name: 'website' });
        await store.put('address', address);
        await store.put('allowLan', this.allowLan);
        await store.flush();
      }
    } catch (failure) { this.error = (failure as Error).message; }
  }

  onBackPress(): boolean {
    if (this.nativePreview) { this.nativePreview = false; return true; }
    if (this.settings) { return false; }
    if (this.fullScreen) { this.fullScreen.exitFullScreen(); this.fullScreen = null; return true; }
    try {
      if (this.controller.accessBackward()) { this.controller.backward(); return true; }
    } catch (_) { /* A failed page can still return to connection settings. */ }
    this.stopDen(); this.settings = true;
    return true;
  }

  private async chooseFile(event: OnShowFileSelectorEvent): Promise<void> {
    try {
      const context = this.getUIContext().getHostContext();
      if (!context) { event.result.handleFileList([]); return; }
      const options = new picker.DocumentSelectOptions();
      options.maxSelectNumber = event.fileSelector.getMode() === FileSelectorMode.FileOpenMultipleMode ? 20 : 1;
      const files = await new picker.DocumentViewPicker(context).select(options);
      event.result.handleFileList(files);
    } catch (_) { event.result.handleFileList([]); }
  }

  private async permission(request: PermissionRequest): Promise<void> {
    // Device permissions are granted only to the configured website, after the OS prompt.
    if (request.getOrigin().replace(/\/$/, '') !== this.source.replace(/\/$/, '')) {
      request.deny(); return;
    }
    const resources = request.getAccessibleResource();
    const permissions: Permissions[] = [];
    for (const resource of resources) {
      if (resource === ProtectedResourceType.AUDIO_CAPTURE) { permissions.push('ohos.permission.MICROPHONE'); }
      else if (resource === ProtectedResourceType.VIDEO_CAPTURE) { permissions.push('ohos.permission.CAMERA'); }
      else { request.deny(); return; }
    }
    try {
      const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
      const result = await abilityAccessCtrl.createAtManager().requestPermissionsFromUser(context, permissions);
      if (result.authResults.length === permissions.length && result.authResults.every((value: number) => value === 0)) {
        request.grant(resources);
      } else { request.deny(); }
    } catch (_) { request.deny(); }
  }

  build() {
    Column() {
      if (this.nativePreview) {
        NativePreview({ origin: this.address.trim().replace(/\/$/, ''), petMode: this.petMode,
          active: this.foreground, onClose: () => { this.nativePreview = false; } })
      } else if (this.settings) {
        Column({ space: 20 }) {
          Text('打开原版派特岛').fontSize(28).fontWeight(FontWeight.Bold)
          Text('连接电脑网页版，保留原有页面、3D 场景和功能。').fontSize(17)
          TextInput({ text: this.address, placeholder: '电脑网页版地址或 HTTPS 网站地址' })
            .onChange((value: string) => { this.address = value; })
          Row({ space: 12 }) {
            Toggle({ type: ToggleType.Switch, isOn: this.allowLan })
              .onChange((value: boolean) => { this.allowLan = value; })
            Text('允许可信局域网 HTTP').fontSize(16)
          }
          if (this.error) { Text(this.error).fontColor('#A32929') }
          Button('进入网页版').onClick(() => { this.open(); })
          Button('原生宠物互动').onClick(() => {
            try { new PetApi().configure(this.address, this.allowLan); this.petMode = true; this.nativePreview = true; }
            catch (failure) { this.error = (failure as Error).message; }
          })
          Button('原生 3D 对照入口').onClick(() => {
            try { new PetApi().configure(this.address, this.allowLan); this.petMode = false; this.nativePreview = true; }
            catch (failure) { this.error = (failure as Error).message; }
          })
          Text('登录使用网页原有账号。在首页按系统返回键可修改连接地址。摄像头和麦克风需要 HTTPS 与系统授权。')
            .fontSize(14).fontColor('#665D57')
        }.padding(28).constraintSize({ maxWidth: 720 }).width('100%')
      } else {
        if (this.error) {
          Row({ space: 12 }) {
            Text(this.error).layoutWeight(1).fontColor('#A32929')
            Button('连接设置').onClick(() => { this.settings = true; })
            Button('重试').onClick(() => { this.error = ''; this.controller.refresh(); })
          }.padding(12)
        }
        Stack({ alignContent: Alignment.TopStart }) {
          if (this.denAttached && this.denNode) {
            NodeContainer(this.denNode).width(this.denWidth).height(this.denHeight)
              .position({ x: this.denX, y: this.denY }).hitTestBehavior(HitTestMode.None)
          }
        Web({ src: this.source, controller: this.controller })
          .width('100%').height('100%')
          .enableNativeEmbedMode(true)
          .onNativeEmbedLifecycleChange((event: NativeEmbedDataInfo) => { this.embedChanged(event); })
          .javaScriptAccess(true).domStorageAccess(true).databaseAccess(true)
          .onlineImageAccess(true).fileAccess(true)
          .mixedMode(MixedMode.None).multiWindowAccess(false)
          .onShowFileSelector((event) => {
            if (!event) { return false; }
            this.chooseFile(event); return true;
          })
          .onPermissionRequest((event) => { if (event) { this.permission(event.request); } })
          .onFullScreenEnter((event) => { if (event) { this.fullScreen = event.handler; } })
          .onFullScreenExit(() => { this.fullScreen = null; })
          .onPageBegin(() => { this.error = ''; this.stopDen(); })
          .onPageEnd(() => { this.startDen(); })
          .onErrorReceive((event) => {
            if (event && event.request.isMainFrame()) { this.error = '网页加载失败，请检查电脑服务与网络连接。'; }
          })
        }.width('100%').layoutWeight(1)
      }
    }.width('100%').height('100%').justifyContent(FlexAlign.Center)
  }
}
