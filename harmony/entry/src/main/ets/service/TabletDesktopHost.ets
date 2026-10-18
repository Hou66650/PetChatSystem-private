import { window, display } from '@kit.ArkUI';
import { common, abilityAccessCtrl } from '@kit.AbilityKit';

export interface DesktopReply { id: number; ok: boolean; message: string; }
export interface DesktopRequest { id: number; op: string; code: string; }
export function parseDesktopRequest(raw: string): DesktopRequest | null {
  try {
    if (raw.length > 1024) { return null; }
    const decoded = raw.startsWith('"') ? JSON.parse(raw) as string : raw;
    if (decoded.length > 512) { return null; }
    const value = JSON.parse(decoded) as DesktopRequest;
    if (!value || !Number.isSafeInteger(value.id) || value.id <= 0 ||
      !['prepare', 'start', 'cancel'].includes(value.op) || typeof value.code !== 'string' ||
      (value.op === 'start' && !/^[A-Za-z0-9_-]{20,80}$/.test(value.code))) { return null; }
    return value;
  } catch (_) { return null; }
}

// Single owner. No background service, credential persistence or automatic resurrection.
export class TabletDesktopHost {
  private static instance: TabletDesktopHost = new TabletDesktopHost();
  static shared(): TabletDesktopHost { return TabletDesktopHost.instance; }
  private context: common.UIAbilityContext | null = null;
  private host: window.Window | null = null;
  private epoch: number = 0;
  private expiry: number = -1;
  private x: number = 80;
  private y: number = 180;
  private movePending: boolean = false;
  private targetX: number = 80;
  private targetY: number = 180;
  private origin: string = '';
  private closing: boolean = false;
  setContext(context: common.UIAbilityContext): void { this.context = context; }
  async prepare(origin: string): Promise<void> {
    if (this.host) { throw new Error('已有平板桌宠窗口，请先召回'); }
    if (!this.context) { throw new Error('应用窗口尚未就绪'); }
    const epoch = ++this.epoch;
    const granted = await abilityAccessCtrl.createAtManager().checkAccessToken(
      this.context.applicationInfo.accessTokenId, 'ohos.permission.SYSTEM_FLOAT_WINDOW');
    if (epoch !== this.epoch) { throw new Error('本次传送已取消'); }
    if (granted !== abilityAccessCtrl.GrantStatus.PERMISSION_GRANTED) {
      throw new Error('当前签名未获鸿蒙全局悬浮窗受控权限，暂不能显示系统桌宠。宠物仍留在小窝。');
    }
    let candidate: window.Window | null = null;
    try {
      candidate = await window.createWindow({ name: 'PaitDesktopPet', windowType: window.WindowType.TYPE_FLOAT, ctx: this.context });
      if (epoch !== this.epoch) { await candidate.destroyWindow(); return; }
      this.origin = origin;
      AppStorage.setOrCreate('paitDesktopOrigin', origin);
      AppStorage.setOrCreate('paitDesktopCode', '');
      AppStorage.setOrCreate('paitDesktopVisible', true);
      AppStorage.setOrCreate('paitDesktopClosing', false);
      const screen = display.getDefaultDisplaySync();
      await candidate.resize(Math.min(620, screen.width), Math.min(760, screen.height));
      await candidate.moveWindowTo(this.x, this.y);
      await candidate.setUIContent('pages/DesktopPet');
      candidate.setWindowBackgroundColor('#00000000');
      if (epoch !== this.epoch) { await candidate.destroyWindow(); return; }
      this.host = candidate;
      candidate.on('windowEvent', (event: window.WindowEventType) => {
        if (this.host !== candidate) { return; }
        if (event === window.WindowEventType.WINDOW_HIDDEN) { AppStorage.setOrCreate('paitDesktopVisible', false); }
        if (event === window.WindowEventType.WINDOW_SHOWN) { AppStorage.setOrCreate('paitDesktopVisible', true); }
        if (event === window.WindowEventType.WINDOW_DESTROYED) { this.host = null; this.cancel(); }
      });
      await candidate.showWindow();
      this.expiry = setTimeout(() => { this.cancel(); }, 20000);
    } catch (error) {
      if (candidate) { try { await candidate.destroyWindow(); } catch (_) {} }
      this.host = null;
      throw new Error('系统桌宠窗口未能创建：' + ((error as Error).message || '设备不支持'));
    }
  }
  start(origin: string, code: string): void {
    if (!this.host || this.origin !== origin || this.closing) { throw new Error('桌宠窗口已失效，请重新出发'); }
    if (this.expiry !== -1) { clearTimeout(this.expiry); this.expiry = -1; }
    AppStorage.setOrCreate('paitDesktopCode', code);
  }
  async command(origin: string, request: DesktopRequest): Promise<DesktopReply> {
    try {
      if (request.op === 'prepare') { await this.prepare(origin); }
      else if (request.op === 'start') { this.start(origin, request.code); }
      else { await this.cancel(); }
      return { id: request.id, ok: true, message: '' };
    } catch (error) { return { id: request.id, ok: false, message: (error as Error).message }; }
  }
  // Deltas are from a touch gesture in our own trusted companion page, in physical pixels.
  async move(dx: number, dy: number): Promise<void> {
    if (!this.host || !Number.isFinite(dx) || !Number.isFinite(dy)) { return; }
    const screen = display.getDefaultDisplaySync(), rect = this.host.getWindowProperties().windowRect;
    this.targetX = Math.max(0, Math.min(screen.width - rect.width, this.targetX + Math.max(-200, Math.min(200, dx))));
    this.targetY = Math.max(0, Math.min(screen.height - rect.height, this.targetY + Math.max(-200, Math.min(200, dy))));
    if (this.movePending) { return; }
    this.movePending = true;
    try { while (this.host && (this.x !== this.targetX || this.y !== this.targetY)) {
      this.x = this.targetX; this.y = this.targetY; await this.host.moveWindowTo(Math.round(this.x), Math.round(this.y));
    } } catch (_) {} finally { this.movePending = false; }
  }
  async cancel(): Promise<void> {
    ++this.epoch;
    if (this.expiry !== -1) { clearTimeout(this.expiry); this.expiry = -1; }
    if (this.closing) { return; } this.closing = true;
    AppStorage.setOrCreate('paitDesktopClosing', true);
    // Give the page a bounded opportunity to send return. Server leases handle process death/offline.
    await new Promise<void>((resolve) => { setTimeout(resolve, 1500); });
    const current = this.host; this.host = null;
    if (current) { try { await current.destroyWindow(); } catch (_) {} }
    AppStorage.setOrCreate('paitDesktopCode', ''); this.closing = false;
  }
}
