/* ArkWeb same-layer pet renderer. The existing den remains the business authority. */
(function (root) {
  'use strict';
  const PATHS = new Set([
    '/static/models/petchat-cat-v3/cat.glb', '/static/models/petchat-shiba-v4/qiuqiu.glb',
    '/static/models/petchat-husky-v3/xueqiu.glb', '/static/models/petchat-shepherd-v2/shepherd.glb'
  ]);
  const vec = v => ({ x: v.x, y: v.y, z: v.z });
  const quat = q => ({ x: q.x, y: q.y, z: q.z, w: q.w });
  class Bridge {
    constructor({ canvas, renderer, read, now = () => performance.now() }) {
      this.canvas = canvas; this.renderer = renderer; this.read = read; this.now = now;
      this.enabled = false; this.embed = null; this.packet = null; this.ready = '';
      this.heartbeat = 0; this.blocked = true; this.occlusionAt = -Infinity;
      this.session = root.crypto.randomUUID();
      this.onHide = () => { this.fallback(); this.occlusionIndex?.dispose(); this.occlusionIndex = null; };
      document.addEventListener('visibilitychange', this.onHide);
      root.addEventListener('pagehide', this.onHide);
    }
    enable() {
      if (this.enabled || this.unsupported) return;
      this.enabled = true;
      this.occlusionIndex = root.NativeOcclusion ? new root.NativeOcclusion.Index() : null;
      const embed = document.createElement('embed');
      embed.id = 'pait-native-pet'; embed.type = 'native/paitpet';
      embed.setAttribute('aria-hidden', 'true');
      // Same-layer composition keeps all original docks, dialogs and bubbles above it.
      embed.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;z-index:1;pointer-events:none;opacity:0;background:transparent';
      this.canvas.parentElement.insertBefore(embed, this.canvas.nextSibling);
      this.embed = embed;
    }
    fallback() {
      this.ready = ''; if (this.embed) this.embed.style.opacity = '0';
    }
    exchange(ack) {
      this.enable();
      this.lastAck = ack;
      this.heartbeat = this.now();
      this.ready = ack && ack.session === this.session && ack.ready ? ack.key : '';
      return JSON.stringify(this.packet);
    }
    mode() { return this.unsupported ? '宠物：网页（本机原生 3D 不可用）' : this.embed?.style.opacity === '1' ? '宠物：鸿蒙原生' : '宠物：网页'; }
    unavailable() {
      this.fallback(); this.unsupported = true; this.enabled = false;
      this.embed?.remove(); this.embed = null; this.packet = null;
      this.occlusionIndex?.dispose(); this.occlusionIndex = null;
    }
    occluded(state) {
      if (!this.occlusionIndex && root.NativeOcclusion) this.occlusionIndex = new root.NativeOcclusion.Index();
      const { camera, petModel: pet, scene } = state;
      const T = root.THREE;
      const origin = camera.getWorldPosition(new T.Vector3());
      const base = pet.getWorldPosition(new T.Vector3());
      const height = pet.userData.height || 1;
      // Prune excluded subtrees BEFORE triangle tests (especially the pet's
      // skinned meshes). The previous full-scene raycast discarded these only
      // after performing all intersection work.
      const candidates = [];
      const opaque = material => material && !material.transparent && material.opacity !== 0;
      const collect = object => {
        if (!object.visible || object === pet) return;
        if (object.isMesh && (Array.isArray(object.material) ? object.material.some(opaque) : opaque(object.material))) {
          candidates.push(object);
        }
        for (const child of object.children) collect(child);
      };
      collect(scene);
      this.occlusionIndex?.prepare(candidates);
      const ray = new T.Raycaster();
      const localRay = new T.Ray(), inverse = new T.Matrix4(), entry = new T.Vector3();
      // Separate native/web depth buffers cannot occlude each other. Keep the
      // original renderer whenever scenery is in front of any sampled body part.
      for (const y of [.12, .48, .86]) {
        const target = base.clone().add(new T.Vector3(0, height * y, 0));
        const direction = target.sub(origin); const distance = direction.length();
        ray.set(origin, direction.normalize()); ray.near = camera.near; ray.far = Math.max(0, distance - .08);
        for (const object of candidates) {
          const geometry = object.geometry;
          // Three r128 checks far only after testing every triangle. Reject
          // static bounds beyond the finite camera-to-pet segment first. An
          // origin inside the bounds must still test geometry, not just its exit.
          if (!object.isSkinnedMesh && !object.isInstancedMesh &&
              !geometry.morphAttributes.position?.length && geometry.boundingBox) {
            localRay.copy(ray.ray).applyMatrix4(inverse.copy(object.matrixWorld).invert());
            if (!geometry.boundingBox.containsPoint(localRay.origin)) {
              if (!localRay.intersectBox(geometry.boundingBox, entry) ||
                  entry.applyMatrix4(object.matrixWorld).distanceTo(origin) > ray.far) continue;
            }
          }
          const hits = this.occlusionIndex ? this.occlusionIndex.hits(object, ray) :
            (geometry.index?.count || geometry.attributes.position.count) < 15000 ? ray.intersectObject(object, false) : null;
          if (hits === null) return true; // keep web depth while indexing/unavailable
          for (const hit of hits) {
            const material = Array.isArray(object.material) ? object.material[hit.face?.materialIndex || 0] : object.material;
            if (opaque(material)) return true;
          }
        }
      }
      return false;
    }
    render(scene, camera) {
      if (!this.enabled) { this.renderer.render(scene, camera); return; }
      const state = this.read(), pet = state.petModel;
      let path = '';
      try { const url = new URL(state.spec?.glb, location.href); if (url.origin === location.origin) path = url.pathname; } catch (_) {}
      const supported = pet && pet.visible && PATHS.has(path) && !state.busy && !state.special &&
        !state.spec.custom && !pet.userData.accessories?.some(a => a.visible);
      const key = supported ? pet.uuid + ':' + path : '';
      if (key !== this.lastKey) { this.fallback(); this.occlusionAt = -Infinity; this.lastKey = key; }
      if (supported && this.now() - this.occlusionAt >= 180) {
        // A diagnostic/unsupported scene object must not abort the page's draw.
        // Keep the web depth buffer and bound retries to the normal interval.
        try { this.blocked = this.occluded(state); }
        catch (_) { this.blocked = true; }
        this.occlusionAt = this.now();
      }
      if (supported) {
        const action = state.action, clip = action?.getClip();
        // petModel is the locomotion wrapper; its first child carries authored
        // normalization and dynamic grounding. Send the combined world transform.
        const model = pet.children[0] || pet;
        this.packet = { version: 1, session: this.session, key, path,
          visible: !this.blocked && !document.hidden,
          position: vec(model.getWorldPosition(new root.THREE.Vector3())),
          rotation: quat(model.getWorldQuaternion(new root.THREE.Quaternion())),
          scale: vec(model.getWorldScale(new root.THREE.Vector3())),
          cameraPosition: vec(camera.position), cameraRotation: quat(camera.quaternion),
          fov: camera.fov * Math.PI / 180, near: camera.near, far: camera.far,
          clip: clip ? clip.name.split('|').pop() : 'idle_breathe',
          phase: clip?.duration > 0 ? Math.max(0, Math.min(1, action.time / clip.duration)) : 0,
          speed: action ? action.getEffectiveTimeScale() : 1, loop: action?.loop === root.THREE.LoopRepeat };
      } else { this.packet = { version: 1, session: this.session, key: '', visible: false }; }
      const active = !!key && this.packet.visible && this.ready === key && this.now() - this.heartbeat < 1000;
      this.embed.style.opacity = active ? '1' : '0';
      const wasVisible = pet?.visible;
      try {
        if (active) pet.visible = false;
        this.renderer.render(scene, camera);
      } finally { if (pet) pet.visible = wasVisible; }
    }
    dispose() {
      this.fallback(); this.enabled = false; this.embed?.remove(); this.embed = null;
      this.occlusionIndex?.dispose(); this.occlusionIndex = null;
      document.removeEventListener('visibilitychange', this.onHide); root.removeEventListener('pagehide', this.onHide);
    }
  }
  root.NativeDenBridge = { Bridge };
})(globalThis);
