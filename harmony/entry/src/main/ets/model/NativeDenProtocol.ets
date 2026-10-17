import { NATIVE_PETS } from './NativeAssets';

export interface DenVector { x: number; y: number; z: number; }
export interface DenRotation extends DenVector { w: number; }
export interface DenFrame {
  version: number;
  session: string;
  key: string;
  path: string;
  visible: boolean;
  position: DenVector;
  rotation: DenRotation;
  scale: DenVector;
  cameraPosition: DenVector;
  cameraRotation: DenRotation;
  fov: number;
  near: number;
  far: number;
  clip: string;
  phase: number;
  speed: number;
  loop: boolean;
}
export interface DenAck { session: string; key: string; ready: boolean; status?: string; }

function vector(v: DenVector): boolean {
  return !!v && [v.x, v.y, v.z].every((n: number): boolean => Number.isFinite(n) && Math.abs(n) <= 10000);
}
function rotation(q: DenRotation): boolean {
  return vector(q) && Number.isFinite(q.w) &&
    Math.abs(q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w - 1) < 0.02;
}
export function parseDenFrame(raw: string): DenFrame | null {
  if (raw.length > 8192) { return null; }
  try {
    const decoded = raw.startsWith('"') ? JSON.parse(raw) as string : raw;
    const frame = JSON.parse(decoded) as DenFrame;
    if (!frame || frame.version !== 1 || typeof frame.session !== 'string' || frame.session.length > 100 ||
      typeof frame.key !== 'string' || frame.key.length > 250 || typeof frame.visible !== 'boolean') { return null; }
    if (!frame.key && !frame.visible) { return frame; }
    if (!NATIVE_PETS.some((pet): boolean => pet.path === frame.path) ||
      !vector(frame.position) || !rotation(frame.rotation) || !vector(frame.scale) ||
      [frame.scale.x, frame.scale.y, frame.scale.z].some((v: number): boolean => v <= 0 || v > 100) ||
      !vector(frame.cameraPosition) || !rotation(frame.cameraRotation) ||
      !Number.isFinite(frame.fov) || frame.fov <= 0 || frame.fov >= Math.PI ||
      !Number.isFinite(frame.near) || !Number.isFinite(frame.far) || frame.near <= 0 || frame.far <= frame.near || frame.far > 10000 ||
      typeof frame.clip !== 'string' || frame.clip.length > 100 ||
      !Number.isFinite(frame.phase) || frame.phase < 0 || frame.phase > 1 ||
      !Number.isFinite(frame.speed) || frame.speed < 0 || frame.speed > 10 || typeof frame.loop !== 'boolean') { return null; }
    return frame;
  } catch (_) { return null; }
}

export function isDenPage(url: string, origin: string): boolean {
  const path = url.slice(origin.length);
  return url.startsWith(origin) && /^\/den\/?(?:[?#].*)?$/.test(path);
}
