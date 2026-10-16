import { Scene, Node, Camera, Animation, LightType, EnvironmentBackgroundType } from '@kit.ArkGraphics3D';
import { http } from '@kit.NetworkKit';
import { fileIo as fs } from '@kit.CoreFileKit';
import { NativeAsset, NATIVE_ASSETS } from '../model/NativeAssets';

@Component
export struct NativePreview {
  origin: string = '';
  onClose: () => void = () => {};
  @State private options: SceneOptions | null = null;
  @State private selected: number = 0;
  @State private status: string = '';
  @State private busy: boolean = false;
  @State private animationNames: string[] = [];
  @State private playing: boolean = false;
  @State private distance: number = 3.6;
  private scene: Scene | null = null;
  private content: Scene | null = null;
  private pivot: Node | null = null;
  private camera: Camera | null = null;
  private activeAnimation: Animation | null = null;
  private request: http.HttpRequest | null = null;
  private generation: number = 0;
  private yaw: number = 0.45;
  private pitch: number = -0.2;
  private startYaw: number = 0;
  private startPitch: number = 0;
  private file: string = '';

  aboutToAppear(): void { this.load(0); }
  aboutToDisappear(): void { this.generation++; this.request?.destroy(); this.request = null; this.clear(); }

  private clear(): void {
    this.options = null;
    this.playing = false; this.activeAnimation?.stop(); this.activeAnimation = null;
    this.camera = null; this.pivot = null;
    this.scene?.destroy(); this.scene = null;
    this.content?.destroy(); this.content = null;
    this.animationNames = [];
    if (this.file) { try { fs.unlinkSync(this.file); } catch (_) {} this.file = ''; }
  }

  private async load(index: number): Promise<void> {
    if (this.busy) { return; }
    const token = ++this.generation;
    this.clear(); this.busy = true; this.selected = index;
    const item: NativeAsset = NATIVE_ASSETS[index];
    const started = Date.now();
    let downloaded: Scene | null = null;
    let result: Scene | null = null;
    let path: string = '';
    const task = http.createHttp(); this.request = task;
    try {
      const context = this.getUIContext().getHostContext();
      if (!context) { throw new Error('应用上下文不可用'); }
      this.status = '正在下载原模型…';
      const response = await task.request(this.origin + item.path, {
        method: http.RequestMethod.GET, expectDataType: http.HttpDataType.ARRAY_BUFFER,
        connectTimeout: 15000, readTimeout: 60000, usingCache: false, maxLimit: 100 * 1024 * 1024
      });
      if (token !== this.generation) { return; }
      if (response.responseCode !== 200) { throw new Error('模型下载失败 HTTP ' + response.responseCode.toString()); }
      const bytes = response.result as ArrayBuffer;
      if (bytes.byteLength < 20 || bytes.byteLength > 100 * 1024 * 1024) { throw new Error('模型文件大小异常'); }
      const header = new DataView(bytes);
      if (header.getUint32(0, true) !== 0x46546C67 || header.getUint32(4, true) !== 2 ||
        header.getUint32(8, true) !== bytes.byteLength) { throw new Error('模型文件不完整或不是 GLB 2.0'); }
      path = context.cacheDir + '/native-' + started.toString() + '-' + token.toString() + '-' + item.id + '.glb';
      const file = fs.openSync(path, fs.OpenMode.CREATE | fs.OpenMode.TRUNC | fs.OpenMode.WRITE_ONLY);
      try { fs.writeSync(file.fd, bytes); } finally { fs.closeSync(file); }
      this.status = '正在由鸿蒙原生引擎解析模型…';
      result = await Scene.load();
      if (token !== this.generation) { return; }
      const factory = result.getResourceFactory();
      downloaded = await factory.createScene(path);
      if (token !== this.generation) { return; }
      const pivot = await factory.createNode({ name: 'preview-pivot' });
      const model = result.importScene('original-model', downloaded, pivot);
      model.scale = { x: item.scale, y: item.scale, z: item.scale };
      model.position = { x: -item.cx * item.scale, y: -item.cy * item.scale, z: -item.cz * item.scale };
      const camera = await factory.createCamera({ name: 'preview-camera' });
      camera.enabled = true; camera.nearPlane = 0.01; camera.farPlane = 100;
      camera.fov = Math.PI / 4; camera.position = { x: 0, y: 0, z: this.distance };
      camera.clearColor = { r: 0.89, g: 0.92, b: 0.9, a: 1 };
      if (result.environment) { result.environment.backgroundType = EnvironmentBackgroundType.BACKGROUND_NONE; }
      const key = await factory.createLight({ name: 'key' }, LightType.DIRECTIONAL);
      key.color = { r: 1, g: 0.95, b: 0.87, a: 1 }; key.intensity = 2.5; key.enabled = true;
      key.rotation = { x: -0.25, y: -0.25, z: 0, w: Math.sqrt(0.875) };
      const fill = await factory.createLight({ name: 'fill' }, LightType.DIRECTIONAL);
      fill.color = { r: 0.8, g: 0.9, b: 1, a: 1 }; fill.intensity = 1.2; fill.enabled = true;
      fill.rotation = { x: 0, y: 1, z: 0, w: 0 };
      if (token !== this.generation) { return; }
      this.scene = result; this.content = downloaded; this.file = path;
      this.pivot = pivot; this.camera = camera;
      this.animationNames = result.animations.map((a: Animation): string => a.name);
      this.rotateModel();
      this.options = { scene: result, modelType: ModelType.SURFACE };
      this.status = '原生模型已准备 · ' + (item.triangles / 10000).toFixed(1) + ' 万三角形 · 下载与解析 ' +
        ((Date.now() - started) / 1000).toFixed(1) + ' 秒';
      result = null; downloaded = null; path = '';
    } catch (failure) {
      if (token === this.generation) { this.status = '原生加载失败：' + ((failure as Error).message || '请返回网页版或重试'); }
    } finally {
      result?.destroy(); downloaded?.destroy();
      if (path) { try { fs.unlinkSync(path); } catch (_) {} }
      task.destroy();
      if (token === this.generation) { this.request = null; this.busy = false; }
    }
  }

  private rotateModel(): void {
    if (!this.pivot) { return; }
    const x = this.pitch / 2; const y = this.yaw / 2;
    this.pivot.rotation = { x: Math.sin(x) * Math.cos(y), y: Math.sin(y) * Math.cos(x),
      z: -Math.sin(x) * Math.sin(y), w: Math.cos(x) * Math.cos(y) };
  }

  private play(index: number): void {
    this.playing = false;
    this.activeAnimation?.stop();
    if (!this.scene) { return; }
    const animation = this.scene.animations[index];
    this.activeAnimation = animation; animation.enabled = true; animation.restart(); this.playing = true;
    animation.onFinished(() => {
      if (this.playing && this.activeAnimation === animation) { animation.restart(); }
    });
  }

  build() {
    Column({ space: 12 }) {
      Row() {
        Text('鸿蒙原生 3D 对照').fontSize(24).layoutWeight(1)
        Button('返回').onClick(() => { this.onClose(); })
      }.width('100%')
      Text('使用网页原 GLB，未减面。此入口验证原生渲染与动画，尚未接入小窝业务；加载耗时不是 FPS。')
        .fontSize(14).fontColor('#5C685F')
      Select(NATIVE_ASSETS.map((item: NativeAsset): SelectOption => ({ value: item.name })))
        .selected(this.selected).value(NATIVE_ASSETS[this.selected].name).enabled(!this.busy)
        .onSelect((index: number) => { this.load(index); })
      Text(this.status).fontSize(14)
      if (this.options) {
        Component3D(this.options).width('100%').layoutWeight(1)
          .gesture(PanGesture().onActionStart(() => { this.startYaw = this.yaw; this.startPitch = this.pitch; })
            .onActionUpdate((event: GestureEvent) => {
              this.yaw = this.startYaw + event.offsetX * 0.008;
              this.pitch = Math.max(-1.2, Math.min(1.2, this.startPitch + event.offsetY * 0.008)); this.rotateModel();
            }))
        Row({ space: 12 }) {
          Text('远近')
          Slider({ value: this.distance, min: 2, max: 8, step: 0.1 }).layoutWeight(1)
            .onChange((value: number) => { this.distance = value; if (this.camera) { this.camera.position = { x: 0, y: 0, z: value }; } })
          Button('复位').onClick(() => { this.yaw = 0.45; this.pitch = -0.2; this.rotateModel(); })
        }.width('100%')
        if (this.animationNames.length > 0) {
          Row({ space: 12 }) {
            Select(this.animationNames.map((name: string): SelectOption => ({ value: name })))
              .value('选择原模型动画').onSelect((index: number) => { this.play(index); })
            Button(this.playing ? '暂停动画' : '播放动画').onClick(() => {
              if (this.playing) { this.playing = false; this.activeAnimation?.pause(); }
              else if (this.activeAnimation) { this.playing = true; this.activeAnimation.start(); }
              else { this.play(0); }
            })
          }
        }
      } else {
        Blank().layoutWeight(1)
        if (!this.busy) { Button('重试').onClick(() => { this.load(this.selected); }) }
        Blank().layoutWeight(1)
      }
    }.padding(16).width('100%').height('100%').backgroundColor('#F6F7F3')
  }
}
