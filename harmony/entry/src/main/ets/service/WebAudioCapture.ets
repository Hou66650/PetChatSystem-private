import { audio } from '@kit.AudioKit';
import { abilityAccessCtrl, common } from '@kit.AbilityKit';
import { util } from '@kit.ArkTS';

interface AudioPacket { state: string; chunks: string[]; }

// PCM only, in memory. The existing website owns the conversation and transport.
export class WebAudioCapture {
  private session: string = '';
  private state: string = 'stopped';
  private chunks: string[] = [];
  private capturer: audio.AudioCapturer | null = null;
  private generation: number = 0;
  private context: () => common.UIAbilityContext | null;
  private trusted: () => boolean;
  constructor(context: () => common.UIAbilityContext | null, trusted: () => boolean) {
    this.context = context; this.trusted = trusted;
  }

  start(session: string): string {
    if (!this.trusted() || !/^[a-zA-Z0-9-]{1,80}$/.test(session)) { return 'denied'; }
    this.close(); this.session = session; this.state = 'permission';
    this.prepare(this.generation);
    return 'pending';
  }
  read(session: string): string {
    if (!this.trusted() || session !== this.session) { return JSON.stringify({ state: 'stopped', chunks: [] } as AudioPacket); }
    if (this.state === 'ready' && this.capturer?.state !== audio.AudioState.STATE_RUNNING) { this.close(); }
    const packet: AudioPacket = { state: this.state, chunks: this.chunks.splice(0) };
    return JSON.stringify(packet);
  }
  stop(session: string): void { if (session === this.session) { this.close(); } }
  close(): void {
    this.generation++; this.session = ''; this.state = 'stopped'; this.chunks = [];
    const old = this.capturer; this.capturer = null;
    if (old) { this.release(old); }
  }
  private async release(capturer: audio.AudioCapturer): Promise<void> {
    try { capturer.off('readData'); } catch (_) {}
    try { if (capturer.state === audio.AudioState.STATE_RUNNING) { await capturer.stop(); } } catch (_) {}
    try { await capturer.release(); } catch (_) {}
  }
  private async prepare(token: number): Promise<void> {
    let created: audio.AudioCapturer | null = null;
    try {
      const context = this.context(); if (!context) { throw new Error('context'); }
      const permission = await abilityAccessCtrl.createAtManager().requestPermissionsFromUser(context, ['ohos.permission.MICROPHONE']);
      if (token !== this.generation || !this.trusted()) { return; }
      if (permission.authResults.length !== 1 || permission.authResults[0] !== 0) { this.state = 'denied'; return; }
      created = await audio.createAudioCapturer({
        streamInfo: { samplingRate: audio.AudioSamplingRate.SAMPLE_RATE_16000, channels: audio.AudioChannel.CHANNEL_1,
          sampleFormat: audio.AudioSampleFormat.SAMPLE_FORMAT_S16LE, encodingType: audio.AudioEncodingType.ENCODING_TYPE_RAW },
        capturerInfo: { source: audio.SourceType.SOURCE_TYPE_VOICE_COMMUNICATION, capturerFlags: 0 }
      });
      if (token !== this.generation || !this.trusted()) { return; }
      const encoder = new util.Base64Helper();
      created.on('readData', (buffer: ArrayBuffer) => {
        if (token !== this.generation || this.state !== 'ready') { return; }
        // Bounded queue: never accumulate microphone history while JS is busy.
        if (buffer.byteLength > 32000) { return; }
        this.chunks.push(encoder.encodeToStringSync(new Uint8Array(buffer)));
        while (this.chunks.length > 10) { this.chunks.shift(); }
      });
      await created.start();
      if (token !== this.generation || !this.trusted()) { return; }
      this.capturer = created; created = null; this.state = 'ready';
    } catch (_) { if (token === this.generation) { this.state = 'error'; } }
    finally { if (created) { await this.release(created); } }
  }
}
