"""
Synthesizes the trailer's soundtrack from timeline.py and mixes in the narration.

    python art/trailer/music.py --vo DIR --out trailer_audio.wav

Everything is generated with numpy/scipy: wind, drones, a choir pad, a music-box motif,
driving strings, taiko drums, brass "braams", risers, impacts and a hall reverb. The
narration WAVs (Kokoro via voice.py, or Windows' voice; see make_trailer.ps1) are trimmed, deepened and
placed at their timeline cues, with the music ducking under them.
"""

import argparse
import os
import sys
import wave

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timeline as TL  # noqa: E402

SR = 48000
N = int(SR * TL.LENGTH)
rng = np.random.default_rng(7)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def tax(dur):
    return np.arange(int(dur * SR)) / SR


def sos_filter(x, kind, f, order=2):
    nyq = SR / 2
    if kind == "band":
        sos = signal.butter(order, [max(20, f[0]) / nyq, min(f[1], nyq * 0.95) / nyq], btype="band", output="sos")
    else:
        sos = signal.butter(order, min(f, nyq * 0.95) / nyq, btype=kind, output="sos")
    return signal.sosfilt(sos, x)


def env_adsr(n, a, d, s, r, sustain_len=None):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    total = n
    s_n = max(0, total - a_n - d_n - r_n) if sustain_len is None else int(sustain_len * SR)
    e = np.concatenate([np.linspace(0, 1, max(1, a_n)), np.linspace(1, s, max(1, d_n)),
                        np.full(s_n, s), np.linspace(s, 0, max(1, r_n))])
    if len(e) < total:
        e = np.concatenate([e, np.zeros(total - len(e))])
    return e[:total]


def saw_osc(freq, dur, vib_rate=0.0, vib_depth=0.0, phase=None):
    t = tax(dur)
    f = freq * (1 + vib_depth * np.sin(2 * np.pi * vib_rate * t + rng.random() * 6.28))
    ph = np.cumsum(f) / SR + (rng.random() if phase is None else phase)
    return 2 * (ph % 1.0) - 1


class Bus:
    def __init__(self):
        self.L = np.zeros(N)
        self.R = np.zeros(N)

    def add(self, sig, t0, gain=1.0, pan=0.0):
        i = int(t0 * SR)
        if i >= N or i + len(sig) <= 0:
            return
        if i < 0:
            sig, i = sig[-i:], 0
        s = sig[:N - i] * gain
        ang = (pan + 1) * np.pi / 4
        self.L[i:i + len(s)] += s * np.cos(ang) * np.sqrt(2)
        self.R[i:i + len(s)] += s * np.sin(ang) * np.sqrt(2)

    def stereo(self):
        return np.stack([self.L, self.R])


music, wet, drums, vo_bus = Bus(), Bus(), Bus(), Bus()


# --------------------------------------------------------------------------- instruments
def wind(t0, t1, gain=0.10):
    n = tax(t1 - t0)
    x = rng.standard_normal(len(n))
    x = sos_filter(x, "band", (250, 1400))
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.13 * n) * np.sin(2 * np.pi * 0.071 * n + 1)
    fade = np.minimum(1, np.minimum(n / 1.5, (n[-1] - n) / 1.5))
    for pan in (-0.6, 0.6):
        music.add(x * lfo * fade, t0, gain, pan)
        x = sos_filter(rng.standard_normal(len(n)), "band", (300, 1600))


def drone(t0, t1, midi, gain=0.12, cutoff=380):
    dur = t1 - t0
    x = sum(saw_osc(hz(midi) * (1 + d), dur, 0.2, 0.002) for d in (-0.0015, 0.0, 0.0017))
    x += 0.8 * np.sin(2 * np.pi * hz(midi - 12) * tax(dur))
    x = sos_filter(x, "low", cutoff)
    n = tax(dur)
    x *= np.minimum(1, np.minimum(n / 2.0, (dur - n) / 2.0))
    music.add(x, t0, gain, -0.2)
    music.add(x, t0 + 0.013, gain, 0.2)


def choir(t0, t1, chord, gain=0.07, attack=1.5, release=2.0):
    dur = t1 - t0
    voice = np.zeros(int(dur * SR))
    for m in chord:
        for d in (-0.004, -0.0015, 0.0012, 0.0035):
            voice += saw_osc(hz(m) * (1 + d), dur, 5.0 + rng.random(), 0.004)
    form = (sos_filter(voice, "band", (630, 850)) * 1.0 + sos_filter(voice, "band", (980, 1220)) * 0.55 +
            sos_filter(voice, "band", (2300, 2650)) * 0.22)
    form = sos_filter(form, "low", 3800)
    e = env_adsr(len(form), attack, 0.5, 0.85, release)
    s = form * e
    music.add(s, t0, gain, -0.3)
    music.add(np.roll(s, 300), t0, gain, 0.3)
    wet.add(s, t0, gain * 1.4)


def music_box(t, midi, gain=0.16, pan=0.0):
    n = tax(2.4)
    f = hz(midi)
    x = (np.sin(2 * np.pi * f * n) + 0.32 * np.sin(2 * np.pi * 2.0 * f * n) * np.exp(-n / 0.5) +
         0.12 * np.sin(2 * np.pi * 3.01 * f * n) * np.exp(-n / 0.25))
    x *= np.exp(-n / 1.1) * np.minimum(1, n / 0.003)
    music.add(x, t, gain, pan)
    wet.add(x, t, gain * 1.8)


MOTIF = [(0.0, 81), (0.5, 77), (1.0, 76), (1.5, 74), (2.5, 69), (3.0, 72), (3.5, 74), (4.5, 70), (5.0, 69)]


def play_motif(t0, transpose=0, gain=0.16, step=1.0):
    for dt, m in MOTIF:
        music_box(t0 + dt * step, m + transpose, gain, pan=0.25 * np.sin(dt))


def taiko(t, gain=0.6, pitch=1.0, pan=0.0):
    n = tax(1.2)
    f = (52 + 95 * np.exp(-n / 0.028)) * pitch
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-n / 0.32)
    nz = sos_filter(rng.standard_normal(len(n)), "low", 900) * np.exp(-n / 0.045) * 0.6
    drums.add(np.tanh(1.6 * (x + nz)), t, gain, pan)
    wet.add(x * 0.5, t, gain * 0.5)


def snare(t, gain=0.25, pan=0.1):
    n = tax(0.5)
    x = sos_filter(rng.standard_normal(len(n)), "high", 1600) * np.exp(-n / 0.11)
    x += 0.5 * np.sin(2 * np.pi * 190 * n) * np.exp(-n / 0.04)
    drums.add(x, t, gain, pan)
    wet.add(x, t, gain * 0.4)


def tick(t, gain=0.07, pan=0.3):
    n = tax(0.08)
    x = sos_filter(rng.standard_normal(len(n)), "high", 7000) * np.exp(-n / 0.018)
    drums.add(x, t, gain, pan)


def cymbal(t, gain=0.22, decay=1.6):
    n = tax(decay * 2.5)
    x = sos_filter(rng.standard_normal(len(n)), "high", 4500) * np.exp(-n / decay)
    music.add(x, t, gain, -0.4)
    music.add(sos_filter(rng.standard_normal(len(n)), "high", 4500) * np.exp(-n / decay), t, gain, 0.4)


def sub(t, gain=0.55, dur=1.6):
    n = tax(dur)
    f = 44 - 10 * (n / dur)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-n / (dur * 0.45))
    drums.add(x, t, gain)


def braam(t, dur=3.0, gain=0.28, root=38):
    n = tax(dur)
    x = np.zeros(len(n))
    for m in (root - 12, root, root + 7, root + 12):
        for d in (-0.006, 0.0, 0.005):
            x += saw_osc(hz(m) * (1 + d), dur, 4.0, 0.002)
    x = np.tanh(0.45 * x)
    # The filter opens fast, then closes slowly: process in blocks with a moving cutoff.
    out = np.zeros_like(x)
    blk = 2400
    zi = None
    for i in range(0, len(x), blk):
        tt = i / SR
        fc = 180 + 1500 * min(1, tt / 0.25) * np.exp(-max(0, tt - 0.25) / (dur * 0.35))
        sos = signal.butter(2, fc / (SR / 2), btype="low", output="sos")
        if zi is None:
            zi = signal.sosfilt_zi(sos) * 0
        out[i:i + blk], zi = signal.sosfilt(sos, x[i:i + blk], zi=zi)
    out *= env_adsr(len(out), 0.04, 0.4, 0.7, dur * 0.55)
    music.add(out, t, gain, -0.15)
    music.add(np.roll(out, 200), t, gain, 0.15)
    wet.add(out, t, gain * 0.8)
    sub(t, 0.6, 2.2)
    taiko(t, 0.7, 0.85)


def sweep_noise(dur, f0, f1, width=0.35):
    """Noise whose band glides from f0 to f1 (Hz) over dur."""
    n = int(dur * SR)
    x = rng.standard_normal(n)
    f, tt, Z = signal.stft(x, SR, nperseg=2048)
    prog = np.clip(tt / dur, 0, 1)
    fc = f0 * (f1 / f0) ** prog
    band = np.exp(-((np.log(np.maximum(f[:, None], 1)) - np.log(fc[None, :])) ** 2) / (2 * width ** 2))
    _, y = signal.istft(Z * band, SR, nperseg=2048)
    y = y[:n]
    return y / (np.abs(y).max() + 1e-9)


def riser(t0, t1, gain=0.22):
    dur = t1 - t0
    y = sweep_noise(dur, 250, 7000)
    n = tax(dur)[:len(y)]
    y *= (n / dur) ** 2
    tone = np.sin(2 * np.pi * np.cumsum(220 * 2 ** (2.5 * n / dur)) / SR) * (n / dur) ** 3 * 0.35
    music.add(y + tone, t0, gain)
    wet.add(y, t0, gain * 0.5)


def whoosh(t, dur=0.7, gain=0.25, up=True):
    y = sweep_noise(dur, 300 if up else 5000, 5000 if up else 300, 0.5)
    n = tax(dur)[:len(y)]
    y *= np.sin(np.pi * n / dur) ** 2
    music.add(y, t, gain, -0.5 if up else 0.5)


def impact(t, big=False):
    taiko(t, 0.75 if big else 0.5)
    sub(t, 0.7 if big else 0.4, 2.0 if big else 1.2)
    cymbal(t, 0.25 if big else 0.12, 2.2 if big else 1.0)
    if big:
        snare(t, 0.35)


def strings_ostinato(t0, t1, gain=0.12):
    beat = 60.0 / TL.BPM
    six = beat / 4
    chords = [(50, [62, 65, 69]), (46, [62, 65, 70]), (43, [62, 67, 70]), (45, [61, 64, 69])]  # Dm Bb Gm A
    pattern = [0, 0, 2, 0, 1, 0, 2, 1]
    t = t0
    k = 0
    while t < t1 - 0.01:
        bar = int((t - t0) / (beat * 4))
        root, tones = chords[(bar // 1) % 4]
        m = tones[pattern[k % 8]]
        dur = six * 0.95
        for octave, pan, g in ((0, -0.35, 1.0), (12, 0.35, 0.55)):
            x = saw_osc(hz(m + octave), dur + 0.03)
            x = sos_filter(x, "low", 2600)
            x *= env_adsr(len(x), 0.004, 0.06, 0.55, 0.03)
            music.add(x, t, gain * g, pan)
        if k % 16 == 0:  # cellos and basses on the bar
            low = sum(saw_osc(hz(root) * (1 + d), beat * 4) for d in (-0.002, 0.002))
            low = sos_filter(low, "low", 700) * env_adsr(int(beat * 4 * SR), 0.05, 0.3, 0.7, 0.3)
            music.add(low, t, gain * 1.1, 0.0)
            wet.add(low, t, gain * 0.3)
        t += six
        k += 1


def action_drums(t0, t1):
    beat = 60.0 / TL.BPM
    t = t0
    i = 0
    while t < t1 - 0.01:
        b = i % 8  # eighth notes in a bar
        if b in (0, 3, 6):
            taiko(t, 0.42 if b else 0.55, 1.0 if b != 3 else 1.15, pan=-0.2 if b == 3 else 0.0)
        if b in (2, 6):
            snare(t, 0.16)
        tick(t, 0.05 + 0.03 * (b % 2 == 0), 0.35 if b % 2 else -0.35)
        t += beat / 2
        i += 1


# --------------------------------------------------------------------------- score
def score():
    # Intro: the frozen office.
    wind(0.0, 23.0, 0.08)
    drone(0.0, 21.0, 38, 0.10)  # D
    play_motif(1.6, 0, 0.12, 1.0)
    choir(4.0, 17.5, [62, 65, 69], 0.05, attack=3.0)
    for k in range(10):  # heartbeat that builds
        t = 7.0 + k * 1.0
        taiko(t, 0.18 + 0.03 * k, 0.8)
        taiko(t + 0.28, 0.12 + 0.02 * k, 0.75)
    play_motif(9.2, -12, 0.10, 0.8)
    riser(14.8, 17.3, 0.2)
    # The ghost.
    braam(17.3, 3.6, 0.32, 38)
    choir(17.3, 21.0, [50, 57, 62, 65], 0.08, attack=0.3, release=1.0)
    impact(18.4)
    whoosh(20.4, 0.6, 0.2)
    # The elevator: a breath of silence, then the doors.
    drone(21.4, 24.4, 45, 0.09, 600)  # A, tension
    riser(22.4, 24.4, 0.24)
    # Action.
    a0, a1 = TL.ACTION
    strings_ostinato(a0, a1, 0.10)
    action_drums(a0, a1)
    choir(36.4, 41.0, [62, 65, 69, 74], 0.07, attack=0.8, release=0.8)
    braam(41.0, 2.5, 0.3, 38)
    choir(44.0, 50.0, [62, 65, 70, 74], 0.07, attack=0.5, release=0.6)
    riser(50.0, 52.4, 0.3)
    for t in TL.HITS:
        impact(t)
    for t in TL.HITS_BIG:
        if t not in (17.3, 41.0, 53.0):
            impact(t, big=True)
    # Title.
    braam(53.0, 5.5, 0.34, 38)
    choir(53.0, 60.5, [50, 62, 65, 69, 74], 0.09, attack=0.6, release=2.0)
    cymbal(53.0, 0.3, 3.0)
    play_motif(56.4, 0, 0.14, 0.8)
    drone(57.0, 64.0, 38, 0.08)
    impact(60.0, big=True)
    choir(60.0, 64.0, [50, 57, 62], 0.05, attack=0.2, release=3.0)


# --------------------------------------------------------------------------- narration
def load_wav(path):
    with wave.open(path, "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float64) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    if sr != SR:
        x = signal.resample_poly(x, SR, sr)
    return x


PITCH = 0.95  # below 1 deepens (and slows) the narration a little


def voice(path, t):
    x = load_wav(path)
    idx = np.nonzero(np.abs(x) > 0.02)[0]
    if len(idx):
        x = x[max(0, idx[0] - 600): idx[-1] + 2400]
    if PITCH != 1.0:
        x = signal.resample_poly(x, 1000, int(round(1000 * PITCH)))
    x = sos_filter(x, "high", 70)
    x = x / (np.abs(x).max() + 1e-9) * 0.85
    vo_bus.add(x, t, 1.0)
    wet.add(x, t, 0.22)
    return len(x) / SR


def reverb(stereo, rt60=2.6):
    n = int(rt60 * SR)
    t = np.arange(n) / SR
    out = []
    for ch in range(2):
        ir = rng.standard_normal(n) * np.exp(-6.9 * t / rt60)
        ir = sos_filter(ir, "low", 5500)
        ir[:int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
        ir /= np.sqrt((ir ** 2).sum())
        out.append(signal.fftconvolve(stereo[ch], ir)[:N])
    return np.stack(out)


def write_wav(path, stereo):
    pcm = (np.clip(stereo.T, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vo", help="folder with n1.wav... (narration)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pitch", type=float, default=0.95,
                    help="narration pitch: 0.95 for Kokoro, about 0.89 for Windows' voice")
    a = ap.parse_args()
    global PITCH
    PITCH = a.pitch
    score()
    duck = np.ones(N)
    if a.vo:
        for vid, t, text in TL.NARRATION:
            p = os.path.join(a.vo, vid + ".wav")
            if os.path.exists(p):
                d = voice(p, t)
                print("narration %s at %.1fs: %.2fs  %s" % (vid, t, d, text))
                i0, i1 = int((t - 0.15) * SR), int((t + d + 0.2) * SR)
                ramp = int(0.15 * SR)
                seg = np.full(max(0, i1 - i0), 0.5)
                seg[:ramp] = np.linspace(1, 0.5, min(ramp, len(seg)))
                seg[-ramp:] = np.linspace(0.5, 1, min(ramp, len(seg)))
                duck[max(0, i0):i1] = np.minimum(duck[max(0, i0):i1], seg[:len(duck[max(0, i0):i1])])
    for s0, s1 in TL.SILENCE:  # drops before big moments
        i0, i1 = int(s0 * SR), int(s1 * SR)
        duck[i0:i1] *= np.linspace(0.15, 0.4, i1 - i0)
    mus = music.stereo() * duck + drums.stereo() * np.maximum(duck, 0.7)
    mix = mus + vo_bus.stereo() + reverb(wet.stereo()) * 0.35
    t = np.arange(N) / SR
    mix *= np.clip((TL.LENGTH - t) / 2.0, 0, 1)  # fade out
    mix /= np.abs(mix).max() + 1e-9
    mix = np.tanh(1.4 * mix) / np.tanh(1.4) * 0.93
    write_wav(a.out, mix)
    print("wrote %s (%.1fs)" % (a.out, TL.LENGTH))


if __name__ == "__main__":
    main()
