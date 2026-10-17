import { BuilderNode, FrameNode, NodeController, NodeRenderType, UIContext } from '@kit.ArkUI';
import { Scene, Node, Camera, LightType, EnvironmentBackgroundType } from '@kit.ArkGraphics3D';
import { http } from '@kit.NetworkKit';
import { fileIo as fs } from '@kit.CoreFileKit';
import { NativePetController } from '../model/NativePetController';
import { DenFrame, DenAck } from '../model/NativeDenProtocol';

interface DenView {
  options: SceneOptions | null;
  width: number;
  height: number;
}

@Builder
function denView(view: DenView) {
  Stack() {
    if (view.options) { Component3D(view.options).width('100%').height('100%').backgroundColor(Color.Transparent) }
  }.width(view.width).height(view.height).backgroundColor(Color.Transparent)
}

// Exports a transparent texture into ArkWeb's <embed>, so HTML keeps ownership
// of layout, hit testing, dialogs and controls. No separate full-screen pet UI.
export class NativeDenNode extends NodeController {
  private builder: BuilderNode<[DenView]> | null = null;
  private surfaceId: string;
  private width: number;
  private height: number;
  private origin: string;
  private cacheDir: string;
  private scene: Scene | null = null;
  private content: Scene | null = null;
  private model: Node | null = null;
  private camera: Camera | null = null;
  private pet: NativePetController | null = null;
  private request: http.HttpRequest | null = null;
  private file: string = '';
  private serial: number = 0;
  private wanted: string = '';
  private session: string = '';
  private loaded: string = '';
  private failed: string = '';
  private latest: DenFrame | null = null;
  private active: boolean = true;
  private ready: boolean = false;
  private status: string = 'waiting';

  constructor(surfaceId: string, width: number, height: number, origin: string, cacheDir: string) {
    super(); this.surfaceId = surfaceId; this.width = width; this.height = height;
    this.origin = origin; this.cacheDir = cacheDir;
  }

  makeNode(context: UIContext): FrameNode | null {
    if (!this.builder) {
      this.builder = new BuilderNode<[DenView]>(context, { surfaceId: this.surfaceId, type: NodeRenderType.RENDER_TYPE_TEXTURE });
      this.builder.build(wrapBuilder(denView), this.view());
    }
    return this.builder.getFrameNode();
  }
  private view(): DenView {
    return { options: this.scene ? { scene: this.scene, modelType: ModelType.TEXTURE } : null,
      width: this.width, height: this.height };
  }
  resize(width: number, height: number): void {
    this.width = width; this.height = height; this.builder?.update(this.view());
  }
  ack(): DenAck { return { session: this.session, key: this.loaded, ready: this.ready && this.active && this.builder !== null, status: this.status }; }

  accept(frame: DenFrame): void {
    this.latest = frame;
    if (this.wanted !== frame.key || this.session !== frame.session) {
      this.serial++; this.request?.destroy(); this.request = null; this.clear();
      this.wanted = frame.key; this.session = frame.session; this.failed = '';
      if (frame.key) { this.load(frame, this.serial); }
    }
    if (!frame.key || this.loaded !== frame.key || this.failed === frame.key) { return; }
    this.apply(frame);
  }

  private apply(frame: DenFrame): void {
    if (!this.model || !this.camera || !this.pet) { return; }
    this.model.position = frame.position; this.model.rotation = frame.rotation; this.model.scale = frame.scale;
    this.camera.position = frame.cameraPosition; this.camera.rotation = frame.cameraRotation;
    this.camera.fov = frame.fov; this.camera.nearPlane = frame.near; this.camera.farPlane = frame.far;
    if (!this.active || !frame.visible) { this.pet.suspend(); this.model.visible = false; this.ready = false; return; }
    this.pet.resume();
    this.ready = this.pet.follow(frame.clip, frame.phase, frame.speed, frame.loop);
    this.model.visible = this.ready;
  }
  setActive(active: boolean): void {
    this.active = active;
    if (!active) { this.ready = false; this.pet?.suspend(); if (this.model) { this.model.visible = false; } }
    else if (this.latest && this.loaded === this.latest.key) { this.apply(this.latest); }
  }

  private async load(frame: DenFrame, token: number): Promise<void> {
    const request = http.createHttp(); this.request = request;
    let result: Scene | null = null; let source: Scene | null = null; let path = '';
    try {
      // Probe runtime support before downloading any model. Some emulator images
      // expose the SDK types but do not export the Scene runtime at all.
      this.status = 'capability'; result = await Scene.load();
      if (token !== this.serial) { return; }
      this.status = 'download';
      const response = await request.request(this.origin + frame.path, {
        method: http.RequestMethod.GET, expectDataType: http.HttpDataType.ARRAY_BUFFER,
        connectTimeout: 15000, readTimeout: 60000, maxLimit: 32 * 1024 * 1024, usingCache: true
      });
      if (token !== this.serial) { return; }
      if (response.responseCode !== 200) { throw new Error('Model HTTP failure'); }
      const bytes = response.result as ArrayBuffer;
      if (bytes.byteLength < 20 || bytes.byteLength > 32 * 1024 * 1024) { throw new Error('Invalid model length'); }
      const header = new DataView(bytes);
      if (header.getUint32(0, true) !== 0x46546c67 || header.getUint32(4, true) !== 2 ||
        header.getUint32(8, true) !== bytes.byteLength) { throw new Error('Invalid GLB'); }
      path = this.cacheDir + '/den-' + Date.now().toString() + '-' + token.toString() + '.glb';
      const file = fs.openSync(path, fs.OpenMode.CREATE | fs.OpenMode.TRUNC | fs.OpenMode.WRITE_ONLY);
      try { fs.writeSync(file.fd, bytes); } finally { fs.closeSync(file); }
      const factory = result.getResourceFactory();
      this.status = 'parse'; source = await factory.createScene(path);
      if (token !== this.serial) { return; }
      const parent = await factory.createNode({ name: 'den-pet' });
      const model = result.importScene('original', source, parent);
      const camera = await factory.createCamera({ name: 'den-camera' });
      camera.enabled = true; camera.clearColor = { r: 0, g: 0, b: 0, a: 0 };
      if (result.environment) { result.environment.backgroundType = EnvironmentBackgroundType.BACKGROUND_NONE; }
      const key = await factory.createLight({ name: 'sun' }, LightType.DIRECTIONAL);
      key.enabled = true; key.color = { r: 1, g: .965, b: .91, a: 1 }; key.intensity = 1.5;
      key.rotation = { x: -.35, y: -.2, z: 0, w: Math.sqrt(1 - .35 * .35 - .2 * .2) };
      const fill = await factory.createLight({ name: 'fill' }, LightType.DIRECTIONAL);
      fill.enabled = true; fill.color = { r: .75, g: .85, b: 1, a: 1 }; fill.intensity = 1;
      fill.rotation = { x: 0, y: 1, z: 0, w: 0 };
      if (token !== this.serial) { return; }
      this.scene = result; this.content = source; this.file = path; this.model = model; this.camera = camera;
      this.pet = new NativePetController(frame.path, model, result.animations, () => {});
      this.loaded = frame.key;
      if (this.latest) { this.apply(this.latest); }
      this.status = 'attach'; this.builder?.update(this.view()); this.status = 'ready';
      result = null; source = null; path = '';
    } catch (failure) {
      if (token === this.serial) {
        const detail = (this.status === 'capability' ? 'unavailable' : this.status) + ': ' +
          ((failure as Error).message || 'unknown').slice(0, 160);
        if (this.scene === result && result) { this.clear(); result = null; source = null; path = ''; }
        this.failed = frame.key; this.ready = false; this.status = detail;
        console.warn('Native den model unavailable: ' + detail);
      }
    } finally {
      result?.destroy(); source?.destroy();
      if (path) { try { fs.unlinkSync(path); } catch (_) {} }
      request.destroy(); if (token === this.serial) { this.request = null; }
    }
  }

  private clear(): void {
    this.ready = false; this.loaded = ''; this.pet?.dispose(); this.pet = null;
    this.model = null; this.camera = null;
    const scene = this.scene; this.scene = null; this.builder?.update(this.view());
    scene?.destroy(); this.content?.destroy(); this.content = null;
    if (this.file) { try { fs.unlinkSync(this.file); } catch (_) {} this.file = ''; }
  }
  dispose(): void {
    this.serial++; this.request?.destroy(); this.request = null;
    this.clear(); this.builder?.dispose(); this.builder = null;
  }
}
