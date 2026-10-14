"""Original deterministic instrumental loops, no third-party recordings."""
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import lfilter

ROOT = Path(__file__).resolve().parents[1]
SR = 24000
BEAT = .75
LENGTH = 32 * BEAT * 4
N = int(SR * LENGTH)
SCORES = {
    'sakura': ([50, 55, 57, 50], [0, 4, 7, 11], [12, 16, 19, 16, 14, 12, 7, 9], 'pluck'),
    'snow': ([57, 53, 48, 55], [0, 3, 7, 10], [19, 15, 12, 10, 7, 12, 15, 14], 'bell'),
    'camp': ([43, 48, 40, 45], [0, 4, 7, 9], [12, 14, 16, 19, 16, 14, 9, 7], 'strings'),
    'room': ([48, 45, 53, 55], [0, 4, 7, 11], [16, 19, 14, 12, 11, 9, 7, 12], 'keys'),
}

def build(theme, roots, chord, melody, voice):
    out = np.zeros((N, 2), np.float64)
    def note(start, midi, duration, amp, kind, pan=0):
        t = np.arange(int(duration * SR)) / SR
        f = 440 * 2 ** ((midi - 69) / 12)
        if kind == 'pad':
            wave = sum(np.sin(2*np.pi*f*r*t)*a for r,a in [(1,.7),(1.002,.2),(2,.1)])
            env = np.minimum(t/.7,1) * np.minimum((duration-t)/1.3,1)
        elif kind == 'bell':
            wave = sum(np.sin(2*np.pi*f*r*t)*a*np.exp(-t*k) for r,a,k in [(1,1,.8),(2.003,.3,1.5),(3.98,.1,3)])
            env = np.minimum(t/.012,1)*np.minimum((duration-t)/.3,1)
        else:
            wave = sum(np.sin(2*np.pi*f*h*t)*(.42**(h-1)) for h in range(1,5))
            env = np.minimum(t/(.18 if kind=='strings' else .012),1)*np.exp(-t/(1.3 if kind=='strings' else .65))*np.minimum((duration-t)/.3,1)
        mono = wave * env * amp
        indices = (int(start*SR)+np.arange(len(t))) % N
        out[indices,0] += mono*np.sqrt((1-pan)/2)
        out[indices,1] += mono*np.sqrt((1+pan)/2)
    for bar in range(32):
        root = roots[(bar//2)%4]
        start = bar*4*BEAT
        for j,interval in enumerate(chord):
            note(start,root+interval,4*BEAT+1.3,.045,'pad',(j-1.5)*.23)
        note(start,root-12,2.8,.085,'keys')
        for j in range(8):
            note(start+j*BEAT/2,root+chord[j%4]+12,2.3,.045,voice,(-1 if j%2 else 1)*.3)
        if bar%4!=3:
            for j in range(2):
                note(start+(j*2+.5)*BEAT,root+melody[(bar*2+j)%len(melody)]+12,3.0,.09,voice,.1)
    # Circular reflections preserve the tail across the exact loop boundary.
    dry = out.copy()
    for delay, gain in [(.127,.16),(.293,.13),(.449,.09),(.733,.055)]:
        out += np.roll(dry[:,::-1],int(delay*SR),axis=0)*gain
    # Wrapped filter warm-up prevents a discontinuity at sample zero.
    extended=np.concatenate([out[-SR:],out])
    out=lfilter([.35],[1,-.65],extended,axis=0)[SR:]
    out *= .72 / max(np.max(np.abs(out)),.001)
    target=ROOT/'static/audio/islands'/f'{theme}.flac'
    target.parent.mkdir(parents=True,exist_ok=True)
    sf.write(target,out,SR,format='FLAC',subtype='PCM_16')
    print(theme, '96s stereo', target.stat().st_size, 'bytes')

if __name__ == '__main__':
    for theme, score in SCORES.items(): build(theme,*score)
