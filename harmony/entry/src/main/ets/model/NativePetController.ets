import { Animation, Node } from '@kit.ArkGraphics3D';

import { PetAction, NATIVE_ACTIONS } from './NativeActions';
export interface PetSnapshot {
  version: number;
  petId: string;
  x: number;
  z: number;
  yaw: number;
  action: string;
}

function aliases(action: PetAction): string[] {
  return NATIVE_ACTIONS.find((item): boolean => item.id === action)?.clips || [];
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
  private desired: PetAction = 'idle';
  private posture: string = 'stand';
  private transition: boolean = false;
  private velocity: number = 0;
  private pendingCompletion: (() => void) | null = null;

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

  supports(action: PetAction): boolean {
    const item = NATIVE_ACTIONS.find((entry): boolean => entry.id === action);
    return !!item && this.find(item.clips) !== null && (!item.enter ||
      (this.find([item.enter]) !== null && this.find([item.exit || 'stand_up']) !== null));
  }

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
    if (this.paused || speed === 0) { clip.pause(); } else if (!clip.running && (loop || phase < 0.999)) { clip.start(); }
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
    this.startClip(aliases(action), action, once, () => { this.perform(next); });
  }
  private startClip(names: string[], action: PetAction, once: boolean, done: () => void): void {
    const token = ++this.sequence; this.pendingCompletion = null;
    const old = this.active; this.active = null;
    old?.stop(); if (old) { old.enabled = false; }
    const clip = this.find(names);
    if (!clip) { this.moving = false; this.changed('当前模型不支持此动作'); return; }
    this.action = action; this.active = clip; clip.enabled = true; clip.speed = 1;
    clip.onFinished(() => {
      if (this.disposed || this.sequence !== token || this.active !== clip) { return; }
      if (this.paused) { this.pendingCompletion = () => { if (once) { done(); } else { clip.restart(); } }; return; }
      if (once) { done(); } else { clip.restart(); }
    });
    if (!this.paused) { clip.restart(); }
    this.changed(this.label());
  }
  private begin(): void {
    if (this.transition || this.disposed) { return; }
    const action = this.desired;
    if (this.posture !== 'stand' && this.posture !== action) {
      this.transition = true;
      this.startClip(['stand_up'], 'wake', true, () => {
        this.transition = false; this.posture = 'stand'; if (this.desired === 'wake') { this.desired = 'idle'; } this.begin();
      }); return;
    }
    const item = NATIVE_ACTIONS.find((entry): boolean => entry.id === action);
    if (!item) { return; }
    if (item.enter && this.posture !== action) {
      this.transition = true;
      this.startClip([item.enter], action, true, () => {
        this.transition = false; this.posture = action; this.begin();
      }); return;
    }
    if (action === 'walk' || action === 'run' || action === 'trot') {
      if (!this.greeting) { this.roaming = true; this.pickTarget(); }
      this.moving = true;
    }
    this.play(action, !item.loop);
  }
  perform(action: PetAction): void {
    if (this.disposed) { return; }
    if (!this.supports(action)) { this.moving = false; this.changed('当前模型不支持此动作'); return; }
    this.following = false; this.desired = action;
    this.moving = false; this.roaming = false; this.greeting = false; this.velocity = 0;
    this.begin();
  }
  come(): void {
    if (this.disposed || !this.supports('walk')) { return; }
    this.following = false; this.desired = 'walk';this.roaming = false; this.greeting = true;
    this.targetX = 0; this.targetZ = 0.55; this.moving = false; this.velocity = 0; this.begin();
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
    const dt = Math.min(seconds, 0.05);
    const difference = distance > 0.0001 ? Math.atan2(Math.sin(Math.atan2(dx, dz) - this.yaw), Math.cos(Math.atan2(dx, dz) - this.yaw)) : 0;
    this.yaw += Math.max(-2.8 * dt, Math.min(2.8 * dt, difference));
    const limit = this.action === 'run' ? 1.2 : this.action === 'trot' ? 0.75 : 0.45;
    const target = Math.min(limit, Math.sqrt(2 * 1.6 * distance)) * Math.pow(Math.max(0, Math.cos(difference)), 2);
    this.velocity += Math.max(-1.6 * dt, Math.min(1.6 * dt, target - this.velocity));
    const advance = this.velocity * dt;
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
    this.paused = false;
    if (this.pendingCompletion) { const complete = this.pendingCompletion; this.pendingCompletion = null; complete(); }
    else { this.active?.start(); }
  }
  dispose(): void {
    this.disposed = true; this.sequence++; this.pendingCompletion = null; this.moving = false;
    this.active?.stop(); this.active = null;
  }
  private label(): string {
    if (this.greeting && this.action === 'walk') { return '正在走过来'; }
    return NATIVE_ACTIONS.find((item): boolean => item.id === this.action)?.label || '待机';
  }
}
