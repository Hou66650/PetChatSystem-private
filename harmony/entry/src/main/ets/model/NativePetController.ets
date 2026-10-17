import { Animation, Node } from '@kit.ArkGraphics3D';

export type PetAction = 'idle' | 'walk' | 'run' | 'petting' | 'sleep' | 'wake' | 'happy';
export interface PetSnapshot {
  version: number;
  petId: string;
  x: number;
  z: number;
  yaw: number;
  action: string;
}

// These aliases follow PortalPets.play in the desktop client. Never play an
// arbitrary first clip when the requested semantic animation is unavailable.
function aliases(action: PetAction): string[] {
  switch (action) {
    case 'idle': return ['idle_breathe', 'Idle'];
    case 'walk': return ['motion_walk', 'Walk', 'walk'];
    case 'run': return ['run', 'motion_trot', 'Run'];
    case 'petting': return ['touch_head', 'happy', 'sniff'];
    case 'sleep': return ['sleep_loop', 'lie_down'];
    case 'wake': return ['stand_up', 'idle_breathe', 'Idle'];
    case 'happy': return ['happy', 'wave_paw'];
  }
}

export function readPetSnapshot(raw: string, petId: string): PetSnapshot | null {
  try {
    const value = JSON.parse(raw) as PetSnapshot;
    if (value.version !== 1 || value.petId !== petId ||
      !Number.isFinite(value.x) || !Number.isFinite(value.z) || !Number.isFinite(value.yaw) ||
      (value.action !== 'idle' && value.action !== 'sleep')) { return null; }
    return { version: 1, petId: petId, x: Math.max(-1.2, Math.min(1.2, value.x)),
      z: Math.max(-0.6, Math.min(0.6, value.z)), yaw: value.yaw % (2 * Math.PI), action: value.action };
  } catch (_) { return null; }
}

// Owns behavior and world transforms; ArkGraphics3D owns skeletal animation.
// step() advances simulation time, not measured render frames / FPS.
export class NativePetController {
  action: PetAction = 'idle';
  paused: boolean = false;
  moving: boolean = false;
  private x: number = 0;
  private z: number = 0;
  private yaw: number = 0;
  private targetX: number = 0;
  private targetZ: number = 0;
  private roaming: boolean = false;
  private greeting: boolean = false;
  private sequence: number = 0;
  private disposed: boolean = false;
  private active: Animation | null = null;
  private petId: string;
  private root: Node;
  private animations: Animation[];
  private changed: (message: string) => void;
  private following: boolean = false;
  private followLoop: boolean = false;

  constructor(petId: string, root: Node, animations: Animation[], changed: (message: string) => void) {
    this.petId = petId; this.root = root; this.animations = animations; this.changed = changed;
    for (const animation of animations) { animation.stop(); animation.enabled = false; }
  }

  restore(snapshot: PetSnapshot | null): void {
    if (snapshot) { this.x = snapshot.x; this.z = snapshot.z; this.yaw = snapshot.yaw; }
    this.transform();
    this.perform(snapshot?.action === 'sleep' ? 'sleep' : 'idle');
  }

  snapshot(): PetSnapshot {
    return { version: 1, petId: this.petId, x: this.x, z: this.z, yaw: this.yaw,
      action: this.action === 'sleep' ? 'sleep' : 'idle' };
  }

  supports(action: PetAction): boolean { return this.find(aliases(action)) !== null; }

  // Embedded mode follows the original den's animation state. It must not run
  // the standalone roaming controller or write a second set of business state.
  follow(name: string, phase: number, speed: number, loop: boolean): boolean {
    if (this.disposed) { return false; }
    const clip = this.find([name]);
    if (!clip) { return false; }
    this.moving = false; this.followLoop = loop;
    if (!this.following || this.active !== clip) {
      const token = ++this.sequence;
      this.active?.stop(); if (this.active) { this.active.enabled = false; }
      this.active = clip; this.following = true; clip.enabled = true;
      clip.onFinished(() => {
        if (!this.disposed && !this.paused && this.sequence === token && this.followLoop) { clip.restart(); }
      });
      clip.speed = speed; clip.restart(); clip.seek(phase);
    } else {
      clip.speed = speed;
      if (Math.abs(clip.progress - phase) > 0.12) { clip.seek(phase); }
    }
    if (this.paused || speed === 0) { clip.pause(); }
    return true;
  }

  private find(names: string[]): Animation | null {
    for (const name of names) {
      const animation = this.animations.find((clip: Animation): boolean => clip.name.split('|').pop() === name);
      if (animation) { return animation; }
    }
    return null;
  }

  private play(action: PetAction, once: boolean, next: PetAction = 'idle'): void {
    const token = ++this.sequence;
    const old = this.active; this.active = null;
    old?.stop(); if (old) { old.enabled = false; }
    const clip = this.find(aliases(action));
    if (!clip) {
      this.moving = false; this.action = 'idle';
      if (action !== 'idle') { this.play('idle', false); }
      this.changed('当前模型不支持此动作'); return;
    }
    this.action = action; this.active = clip; clip.enabled = true;
    clip.onFinished(() => {
      if (this.disposed || this.paused || this.sequence !== token || this.active !== clip) { return; }
      if (once) { this.perform(next); } else { clip.restart(); }
    });
    if (!this.paused) { clip.restart(); }
    this.changed(this.label());
  }

  perform(action: PetAction): void {
    if (this.disposed) { return; }
    this.following = false;
    this.moving = false; this.roaming = false; this.greeting = false;
    if (action === 'walk' || action === 'run') {
      this.roaming = true; this.pickTarget(); this.moving = true;
    }
    this.play(action, action === 'petting' || action === 'happy' || action === 'wake');
  }

  come(): void {
    if (this.disposed) { return; }
    this.roaming = false; this.greeting = true;
    this.targetX = 0; this.targetZ = 0.55; this.moving = true;
    this.play('walk', false);
  }

  private pickTarget(): void {
    // Alternate sides so a new destination cannot immediately equal this one.
    this.targetX = this.x >= 0 ? -1.1 : 1.1;
    this.targetZ = Math.random() * 1.0 - 0.5;
  }

  step(seconds: number): void {
    if (this.disposed || this.paused || !this.moving || !Number.isFinite(seconds) || seconds <= 0) { return; }
    const dx = this.targetX - this.x; const dz = this.targetZ - this.z;
    const distance = Math.sqrt(dx * dx + dz * dz);
    const advance = Math.min(seconds, 0.05) * (this.action === 'run' ? 1.2 : 0.45);
    if (distance > 0.0001) { this.yaw = Math.atan2(dx, dz); }
    if (distance <= advance) {
      this.x = this.targetX; this.z = this.targetZ;
      if (this.roaming) { this.pickTarget(); }
      else { this.moving = false; this.play(this.greeting ? 'happy' : 'idle', this.greeting); }
    } else {
      this.x += dx / distance * advance; this.z += dz / distance * advance;
    }
    this.transform();
  }

  private transform(): void {
    this.root.position = { x: this.x, y: 0, z: this.z };
    this.root.rotation = { x: 0, y: Math.sin(this.yaw / 2), z: 0, w: Math.cos(this.yaw / 2) };
  }

  suspend(): void { this.paused = true; this.active?.pause(); }
  resume(): void {
    if (this.disposed || !this.paused) { return; }
    this.paused = false; this.active?.restart();
  }
  dispose(): void {
    this.disposed = true; this.sequence++; this.moving = false;
    this.active?.stop(); this.active = null;
  }
  private label(): string {
    switch (this.action) {
      case 'idle': return '待机';
      case 'walk': return this.greeting ? '正在走过来' : '散步中';
      case 'run': return '跑动中';
      case 'petting': return '抚摸中';
      case 'sleep': return '睡眠中';
      case 'wake': return '正在醒来';
      case 'happy': return '开心回应';
    }
  }
}
