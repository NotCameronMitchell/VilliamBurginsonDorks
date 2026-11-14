"""
Makes the game's music and sound effects from code, like the models, so they can be changed
and remade:

    python art/audio/make_audio.py --out DIR [--only title,hit]

- **Music:** five loops (title, office, battle, boss, final) and two jingles (victory,
  gameover). Each is an original chiptune-style piece, written out note by note below.
  Loops are seamless: whatever rings past the end is folded back to the start.
- **Sounds:** hits, heals, status effects, UI clicks, the "!" alert, the elevator ding...
- **Output:** DIR/music/*.wav (44.1 kHz stereo) and DIR/sfx/*.wav (mono).
  art/audio/make_audio.ps1 runs this, copies the sounds to assets/audio/sfx and turns the
  music into OGG Vorbis in assets/audio/music with Blender's encoder.

Needs Python with numpy and scipy (the Kimodo venv has both).
"""

import argparse
import os
import re
import wave

import numpy as np
from scipy import signal

SR = 44100
rng = np.random.default_rng(11)


# --------------------------------------------------------------------------- basics
def hz(midi):
    return 440.0 * 2 ** ((np.asarray(midi, dtype=float) - 69) / 12)


def ns(dur):
    return max(1, int(round(dur * SR)))


def secs(n):
    return np.arange(n) / SR


def filt(x, kind, f, order=2):
    nyq = SR / 2
    if kind == "band":
        wn = [max(20.0, f[0]) / nyq, min(f[1], nyq * 0.95) / nyq]
    else:
        wn = min(max(f, 20.0), nyq * 0.95) / nyq
    return signal.sosfilt(signal.butter(order, wn, btype=kind, output="sos"), x)


def moving_filter(x, fc, kind="low", q=0.5, block=256):
    """A filter whose cutoff (fc, one value per sample) moves over time."""
    out = np.zeros_like(x)
    zi = None
    for i in range(0, len(x), block):
        f = float(np.clip(fc[min(i + block // 2, len(fc) - 1)], 40, SR * 0.42))
        if kind == "band":
            wn = [max(30.0, f * (1 - q)) / (SR / 2), min(f * (1 + q), SR * 0.45) / (SR / 2)]
        else:
            wn = f / (SR / 2)
        sos = signal.butter(2, wn, btype=kind, output="sos")
        if zi is None:
            zi = np.zeros((sos.shape[0], 2))
        out[i:i + block], zi = signal.sosfilt(sos, x[i:i + block], zi=zi)
    return out


def adsr(n, a=0.005, d=0.1, s=0.7, r=0.05):
    """Attack, decay, sustain level and release over n samples (the release ends at n)."""
    a_n, d_n, r_n = ns(a), ns(d), ns(r)
    if a_n + d_n + r_n > n:  # a short note: squeeze the envelope to fit
        k = n / (a_n + d_n + r_n)
        a_n, d_n = max(1, int(a_n * k)), max(1, int(d_n * k))
        r_n = max(1, n - a_n - d_n)
    s_n = max(0, n - a_n - d_n - r_n)
    e = np.concatenate([np.linspace(0, 1, a_n, endpoint=False), np.linspace(1, s, d_n, endpoint=False),
                        np.full(s_n, s), np.linspace(s, 0, r_n)])
    return np.pad(e, (0, max(0, n - len(e))))[:n]


def perc(n, decay, a=0.002):
    """A quick attack, then an exponential decay, faded to zero at the end."""
    t = secs(n)
    e = np.exp(-t / decay) * (np.minimum(1, t / a) if a > 0 else 1)
    f = min(ns(0.004), n)
    e[n - f:] *= np.linspace(1, 0, f)
    return e


def _blep(t, dt):
    out = np.zeros_like(t)
    m = t < dt
    x = t[m] / dt[m]
    out[m] = x + x - x * x - 1
    m = t > 1 - dt
    x = (t[m] - 1) / dt[m]
    out[m] = x * x + x + x + 1
    return out


def osc(kind, freq, n, duty=0.5, vib=0.0, vib_rate=5.5, vib_delay=0.0):
    """An oscillator. freq is in Hz (one value, or one per sample); vib is the vibrato depth
    as a fraction of the pitch. Saw and pulse waves are band-limited (polyBLEP)."""
    t = secs(n)
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,)).copy()
    if vib:
        f *= 1 + vib * np.clip((t - vib_delay) / 0.15, 0, 1) * np.sin(2 * np.pi * vib_rate * t)
    dt = f / SR
    ph = np.cumsum(dt) % 1.0
    if kind == "sine":
        return np.sin(2 * np.pi * ph)
    if kind == "tri":
        return 1 - 4 * np.abs(ph - 0.5)
    if kind == "saw":
        return 2 * ph - 1 - _blep(ph, dt)
    if kind == "pulse":
        x = np.where(ph < duty, 1.0, -1.0) + _blep(ph, dt) - _blep((ph + 1 - duty) % 1.0, dt)
        return x - (2 * duty - 1)
    raise ValueError(kind)


def glide(f0, f1, n, tau=None):
    """A pitch curve from f0 to f1 Hz: exponential over n samples, or settling with time
    constant tau (seconds)."""
    t = secs(n)
    if tau:
        return f1 + (f0 - f1) * np.exp(-t / tau)
    return f0 * (f1 / f0) ** (t / t[-1] if n > 1 else 0)


# --------------------------------------------------------------------------- notes and chords
NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
QUAL = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11), "m7": (0, 3, 7, 10),
        "m6": (0, 3, 7, 9), "dim": (0, 3, 6), "sus4": (0, 5, 7)}


def pc(name):
    return (NOTE[name[0]] + {"b": -1, "#": 1}.get(name[1:2], 0)) % 12


def note(name):
    """'C4' -> 60, 'F#5' -> 78, 'Bb3' -> 58."""
    m = re.fullmatch(r"([A-G][b#]?)(-?\d)", name)
    return 12 * (int(m.group(2)) + 1) + (NOTE[m.group(1)[0]] + {"b": -1, "#": 1}.get(m.group(1)[1:2], 0))


def chord(sym):
    """'Am7', 'G/B', 'Bbmaj7' -> bass note (E2..D#3), root (same range), third and a close
    voicing around C4..B4."""
    m = re.fullmatch(r"([A-G][b#]?)(maj7|m7|m6|m|7|dim|sus4)?(?:/([A-G][b#]?))?", sym)
    root, qual, slash = m.group(1), m.group(2) or "", m.group(3)
    r = pc(root)
    return {"root": 40 + (r - 4) % 12, "bass": 40 + (pc(slash or root) - 4) % 12, "third": QUAL[qual][1],
            "tones": sorted(60 + (r + iv) % 12 for iv in QUAL[qual])}


def melody(text):
    """'G4:.5 C5:.5 r:1 ... | next bar' -> [(start beat, beats, midi)]. Every bar must add
    up to 4 beats."""
    out, beat = [], 0.0
    for i, bar in enumerate(text.split("|")):
        total = 0.0
        for tok in bar.split():
            name, ln = tok.split(":")
            if name != "r":
                out.append((beat, float(ln), note(name)))
            beat += float(ln)
            total += float(ln)
        assert abs(total - 4) < 1e-6, "bar %d has %g beats" % (i + 1, total)
    return out


# --------------------------------------------------------------------------- instruments
def lead(m, dur, duty=0.5, vib=0.006, bright=5000):
    n = ns(dur)
    x = osc("pulse", hz(m), n, duty, vib, 5.5, 0.18)
    return filt(x, "low", bright) * adsr(n, 0.004, 0.08, 0.7, 0.05)


def saw_lead(m, dur, vib=0.007, bright=3800):
    n = ns(dur)
    x = osc("saw", hz(m), n, vib=vib, vib_delay=0.15) + 0.5 * osc("saw", hz(m) * 1.004, n, vib=vib, vib_delay=0.15)
    return filt(x, "low", bright) * adsr(n, 0.006, 0.12, 0.75, 0.06) * 0.7


def tri_bass(m, dur, s=0.8):
    n = ns(dur)
    return (osc("tri", hz(m), n) + 0.3 * osc("sine", hz(m), n)) * adsr(n, 0.003, 0.08, s, 0.03)


def pulse_bass(m, dur, duty=0.25, cutoff=1400):
    n = ns(dur)
    return filt(osc("pulse", hz(m), n, duty), "low", cutoff) * adsr(n, 0.003, 0.09, 0.6, 0.03)


def grit_bass(m, dur):
    n = ns(dur)
    x = osc("saw", hz(m), n) + osc("saw", hz(m) * 0.998, n) + 0.8 * osc("sine", hz(m - 12), n)
    return np.tanh(1.8 * filt(x, "low", 900)) * adsr(n, 0.003, 0.1, 0.7, 0.03) * 0.8


def upright(m, dur):
    n = ns(dur)
    x = osc("sine", hz(m), n) + 0.35 * osc("tri", hz(m), n) + 0.1 * osc("sine", hz(m) * 2, n)
    return x * perc(n, 0.35, a=0.006)


def arp(m, dur, duty=0.125):
    n = ns(dur)
    return filt(osc("pulse", hz(m), n, duty), "low", 6000) * perc(n, 0.09)


def epiano(m, dur, vel=1.0):
    n = ns(dur + 0.6)
    t = secs(n)
    f = float(hz(m))
    idx = 1.8 * vel * np.exp(-t / 0.35) + 0.2
    x = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t))
    x += 0.15 * np.sin(2 * np.pi * f * 7.02 * t) * np.exp(-t / 0.05)
    e = np.exp(-t / 1.2) * np.minimum(1, t / 0.002) * np.clip(1 - (t - dur) / 0.25, 0, 1)
    return x * e


def vibes(m, dur):
    n = ns(dur + 1.0)
    t = secs(n)
    f = float(hz(m))
    x = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 4.0 * f * t) * np.exp(-t / 0.08)
    trem = 1 - 0.25 * (0.5 + 0.5 * np.sin(2 * np.pi * 5.0 * t))
    e = np.exp(-t / 1.4) * np.minimum(1, t / 0.002) * np.clip(1 - (t - dur - 0.3) / 0.5, 0, 1)
    return x * trem * e


def flute(m, dur):
    n = ns(dur)
    x = osc("sine", hz(m), n, vib=0.008, vib_delay=0.2) + 0.15 * osc("sine", hz(m) * 2, n)
    breath = filt(rng.standard_normal(n), "band", (float(hz(m)), float(hz(m)) * 4)) * 0.05
    return (x + breath) * adsr(n, 0.04, 0.1, 0.8, 0.08)


def organ(m, dur):
    n = ns(dur)
    t = secs(n)
    ph = 2 * np.pi * np.cumsum(float(hz(m)) * (1 + 0.003 * np.sin(2 * np.pi * 6.2 * t))) / SR
    x = sum(g * np.sin(k * ph) for k, g in ((0.5, 0.5), (1, 1.0), (2, 0.6), (3, 0.35), (4, 0.25), (6, 0.12)))
    click = filt(rng.standard_normal(n), "high", 2000) * perc(n, 0.004) * 0.1
    return (x * adsr(n, 0.004, 0.05, 0.9, 0.04) + click) * 0.35


def brass(m, dur, cutoff=2400):
    n = ns(dur)
    f = float(hz(m))
    x = sum(osc("saw", f * (1 + d), n, vib=0.004, vib_delay=0.2) for d in (-0.004, 0.0, 0.005))
    t = secs(n)
    w = np.clip(t / 0.06, 0, 1) * (0.55 + 0.45 * np.exp(-t / 0.25))  # the filter opens, then settles
    return (filt(x, "low", 500) * (1 - w) + filt(x, "low", cutoff) * w) * adsr(n, 0.02, 0.15, 0.8, 0.06) * 0.4


def pad(tones, dur, cutoff=1600, a=0.25, r=0.3):
    n = ns(dur)
    x = np.zeros(n)
    for m in tones:
        for d in (-0.003, 0.003):
            x += osc("saw", float(hz(m)) * (1 + d), n)
    return filt(x, "low", cutoff) * adsr(n, a, 0.2, 0.85, r) / len(tones)


def trombone(m, dur, wobble=False):
    n = ns(dur)
    t = secs(n)
    f = float(hz(m)) * (1 + 0.03 * np.exp(-t / 0.05))  # slides in from a little sharp
    if wobble:
        f = f * (1 + 0.014 * np.clip((t - 0.25) / 0.3, 0, 1) * np.sin(2 * np.pi * 5.5 * t))
    x = osc("saw", f, n) + 0.4 * osc("pulse", f, n, 0.3)
    wah = 320 + 1500 * (1 - np.exp(-t / 0.09)) * np.exp(-t / (0.9 if wobble else 0.35))
    return moving_filter(x, wah) * adsr(n, 0.03, 0.1, 0.85, 0.12) * 0.6


# --------------------------------------------------------------------------- drums
def kick(vel=1.0, punch=1.0):
    n = ns(0.45)
    t = secs(n)
    x = np.sin(2 * np.pi * np.cumsum(48 + 110 * punch * np.exp(-t / 0.035)) / SR) * np.exp(-t / 0.22)
    click = filt(rng.standard_normal(n), "high", 3000) * perc(n, 0.004) * 0.25
    return np.tanh(1.5 * (x + click)) * vel


def snare(vel=1.0, decay=0.13):
    n = ns(0.4)
    t = secs(n)
    x = filt(rng.standard_normal(n), "band", (1200, 9000)) * np.exp(-t / decay)
    x += 0.6 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)
    return x * vel * 0.8


def hat(vel=1.0, open_=False):
    n = ns(0.5 if open_ else 0.08)
    return filt(rng.standard_normal(n), "high", 7500) * perc(n, 0.18 if open_ else 0.022) * vel * 0.5


def rim(vel=1.0):
    n = ns(0.06)
    t = secs(n)
    x = np.sin(2 * np.pi * 820 * t) * np.exp(-t / 0.012)
    x += filt(rng.standard_normal(n), "band", (1500, 5000)) * np.exp(-t / 0.006)
    return x * vel * 0.5


def brush(vel=1.0):
    n = ns(0.2)
    t = secs(n)
    e = np.minimum(1, t / 0.03) * np.exp(-np.maximum(0, t - 0.03) / 0.06)
    return filt(rng.standard_normal(n), "band", (2000, 9000)) * e * vel * 0.35


def ride(vel=1.0):
    n = ns(0.9)
    t = secs(n)
    x = filt(rng.standard_normal(n), "band", (4000, 12000)) * np.exp(-t / 0.35) * 0.35
    x += sum(np.sin(2 * np.pi * f * t) for f in (3150, 4420, 5230)) * np.exp(-t / 0.25) * 0.05
    return x * perc(n, 10) * vel


def tom(m=45, vel=1.0):
    n = ns(0.5)
    t = secs(n)
    f = float(hz(m)) * (1 + 0.6 * np.exp(-t / 0.03))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.2) * vel * 0.8


def crash(vel=1.0, decay=1.3):
    n = ns(decay * 3)
    t = secs(n)
    return filt(rng.standard_normal(n), "high", 3500) * np.exp(-t / decay) * np.minimum(1, t / 0.003) * vel * 0.4


# --------------------------------------------------------------------------- mixing
def reverb(stereo, rt60=1.5):
    n = ns(rt60)
    t = secs(n)
    out = []
    for ch in range(stereo.shape[0]):
        ir = filt(rng.standard_normal(n) * np.exp(-6.9 * t / rt60), "low", 6000)
        ir = np.concatenate([np.zeros(ns(0.012)), ir])
        ir /= np.sqrt((ir ** 2).sum())
        out.append(signal.fftconvolve(stereo[ch], ir))
    return np.stack(out)


def trim(x, pad_s=0.05):
    level = np.abs(x).max(axis=0)
    idx = np.nonzero(level > level.max() * 1e-3)[0]
    end = min(x.shape[1], (idx[-1] if len(idx) else 0) + ns(pad_s))
    x = x[:, :end].copy()
    f = min(ns(0.03), end)
    x[:, end - f:] *= np.linspace(1, 0, f)
    return x


def master(x, target_rms, loop):
    if loop:  # filter three copies and keep the middle, so the loop point stays seamless
        L = x.shape[1]
        x = np.stack([filt(np.tile(c, 3), "high", 28)[L:2 * L] for c in x])
    else:
        x = np.stack([filt(c, "high", 28) for c in x])
    x = x * (target_rms / (np.sqrt((x ** 2).mean()) + 1e-9))
    x = np.tanh(x * 1.1) / 1.1
    peak = np.abs(x).max()
    return x * (0.97 / peak) if peak > 0.97 else x


class Mix:
    """A stereo track with a reverb send. Loops fold their tail back to the start."""

    def __init__(self, seconds, tail=4.0):
        self.L = ns(seconds)
        self.n = self.L + ns(tail)
        self.dry = np.zeros((2, self.n))
        self.wet = np.zeros((2, self.n))

    def add(self, sig, t, gain=1.0, pan=0.0, send=0.12):
        i = int(round(t * SR))
        if i < 0:
            sig, i = sig[-i:], 0
        if i >= self.n or len(sig) == 0:
            return
        s = sig[:self.n - i] * gain
        a = (np.clip(pan, -1, 1) + 1) * np.pi / 4
        for ch, g in ((0, np.cos(a)), (1, np.sin(a))):
            self.dry[ch, i:i + len(s)] += s * g * np.sqrt(2)
            if send:
                self.wet[ch, i:i + len(s)] += s * g * np.sqrt(2) * send

    def render(self, loop=True, rt60=1.5, target_rms=0.16):
        rev = reverb(self.wet, rt60)
        out = np.zeros((2, max(self.n, rev.shape[1])))
        out[:, :self.n] += self.dry
        out[:, :rev.shape[1]] += rev
        if loop:
            folded = np.zeros((2, self.L))
            for k in range(0, out.shape[1], self.L):
                seg = out[:, k:k + self.L]
                folded[:, :seg.shape[1]] += seg
            out = folded
        else:
            out = trim(out)
        return master(out, target_rms, loop)


def rock_drums(mix, t0, B, kicks=(0, 1.5, 2), snares=(1, 3), sixteenths=False, crash_on=False, fill=False):
    """One bar of drums. kicks/snares are beat positions in the bar."""
    for k in kicks:
        mix.add(kick(), t0 + k * B, 0.55, 0, send=0)
    for s in snares:
        mix.add(snare(), t0 + s * B, 0.38, 0.05, send=0.1)
    step = 0.25 if sixteenths else 0.5
    for i in range(int(4 / step)):
        accent = 1.0 if (i * step) % 1 == 0.5 else 0.75
        mix.add(hat(accent), t0 + i * step * B, 0.2 if sixteenths else 0.26, 0.3, send=0)
    if crash_on:
        mix.add(crash(), t0, 0.35, -0.3, send=0.1)
    if fill:  # sixteenth snares on beat 4, getting louder
        for i in range(4):
            mix.add(snare(0.5 + 0.15 * i), t0 + (3 + i / 4) * B, 0.36, 0.05, send=0.1)


# --------------------------------------------------------------------------- music
def song_title():
    """Main menu: bouncy and heroic, C major."""
    B = 60 / 128
    prog = "C G/B Am F C G F G Am Em F C Dm G C G".split()
    mel = melody("""
        G4:.5 C5:.5 E5:1 D5:.5 C5:.5 E5:1 | D5:1.5 B4:.5 G4:1 B4:1 | C5:.5 E5:.5 A5:1.5 G5:.5 E5:1 |
        F5:1 E5:.5 D5:.5 C5:2 | G4:.5 C5:.5 E5:1 G5:1 E5:1 | D5:1 G5:1 F5:.5 E5:.5 D5:1 |
        C5:1 A4:.5 C5:.5 F5:1 A5:1 | G5:3 r:1 | E5:.5 A5:.5 C6:1 B5:.5 A5:.5 E5:1 |
        G5:1.5 E5:.5 B4:1 E5:1 | F5:.5 A5:.5 C6:1 A5:1 F5:1 | E5:1 G5:1 C6:2 |
        D5:.5 F5:.5 A5:1 G5:.5 F5:.5 D5:1 | B4:1 D5:1 G5:1 F5:1 | E5:1.5 D5:.5 C5:1 G4:1 |
        B4:1 D5:1 G5:.5 F5:.5 D5:1""")
    mix = Mix(len(prog) * 4 * B)
    for beat, ln, m in mel:
        mix.add(lead(m, ln * B * 0.92, duty=0.25), beat * B, 0.30, 0.0, send=0.18)
        mix.add(lead(m, ln * B * 0.92, duty=0.25), (beat + 0.75) * B, 0.08, 0.6, send=0.1)  # echo
    for i, sym in enumerate(prog):
        c = chord(sym)
        t0 = i * 4 * B
        mix.add(pad(c["tones"], 4 * B, 1400), t0, 0.10, 0.0, send=0.25)
        for k in range(8):  # bass bouncing between octaves
            mix.add(tri_bass(c["bass"] + (12 if k % 2 else 0), B * 0.45), t0 + k * B / 2, 0.42, 0, send=0.02)
        notes = c["tones"] + [c["tones"][0] + 12]
        for k in range(16):
            mix.add(arp(notes[k % len(notes)] + 12, B * 0.22), t0 + k * B / 4, 0.07, -0.5, send=0.15)
        rock_drums(mix, t0, B, kicks=(0, 2) if i % 4 != 3 else (0, 2, 3.5), crash_on=i % 8 == 0)
    return mix.render(loop=True, rt60=1.4)


def song_office():
    """The office (overworld): lazy elevator jazz with a swing, F major."""
    B = 60 / 96
    prog = ["Fmaj7", "Em7 A7", "Dm7", "Cm7 F7", "Bbmaj7", "Bbm6", "Am7 D7", "Gm7 C7"] * 2
    mel = melody("""
        A4:1 C5:.5 E5:1.5 D5:1 | D5:1 B4:.5 G4:.5 C#5:1 E5:1 | F5:1.5 E5:.5 D5:.5 C5:.5 A4:1 |
        Bb4:1 G4:.5 Eb5:.5 D5:1 C5:1 | D5:1 F5:1 A5:1.5 G5:.5 | F5:1 Db5:1 Bb4:1 G4:1 |
        C5:1 E5:1 F#5:1 A5:1 | G5:1.5 F5:.5 E5:1 C5:1""")

    def swing(beat):  # off-beat eighths land late
        return beat + (1 / 6 if abs(beat % 1 - 0.5) < 1e-6 else 0)

    mix = Mix(len(prog) * 4 * B)
    for pas in range(2):
        for beat, ln, m in mel:
            t = (pas * 32 + swing(beat)) * B
            mix.add(vibes(m, ln * B * 0.9), t, 0.30, 0.15, send=0.25)
            if pas == 1:
                mix.add(flute(m + 12, ln * B * 0.9), t, 0.09, -0.25, send=0.3)
    flat = []
    for i, bar in enumerate(prog):
        syms = bar.split()
        for j, sym in enumerate(syms):
            flat.append((i * 4 + j * 4 / len(syms), 4 / len(syms), sym))
    for k, (beat, per, sym) in enumerate(flat):
        c, nx = chord(sym), chord(flat[(k + 1) % len(flat)][2])
        for hb, hl in ([(0, 1.2), (1.5, 0.5)] if per == 4 else [(0, 0.9)]):  # Charleston comping
            for m in c["tones"]:
                mix.add(epiano(m, hl * B), (beat + swing(hb)) * B, 0.06, -0.2, send=0.2)
        r = c["root"]
        line = [r, r + c["third"], r + 7, nx["root"] - 1] if per == 4 else [r, nx["root"] + 1]
        for q, m in enumerate(line):  # walking bass
            mix.add(upright(m, B * 0.95), (beat + q) * B, 0.5, 0, send=0.03)
    for i in range(len(prog)):
        t0 = i * 4 * B
        for k in range(4):
            mix.add(ride(0.6), t0 + k * B, 0.12, 0.35, send=0.05)
            if k in (1, 3):
                mix.add(ride(0.45), t0 + (k + 0.5 + 1 / 6) * B, 0.10, 0.35, send=0.05)
                mix.add(rim(), t0 + k * B, 0.14, -0.1, send=0.1)
                mix.add(brush(), t0 + k * B, 0.18, 0.1, send=0.05)
            else:
                mix.add(kick(0.6, punch=0.5), t0 + k * B, 0.28, 0, send=0)
    return mix.render(loop=True, rt60=1.8, target_rms=0.13)


def song_battle():
    """Coworker fights: fast and driving, A minor."""
    B = 60 / 150
    prog = "Am F G Em Am F G E Dm Am Bb G F G E E".split()
    mel = melody("""
        A4:.5 C5:.5 E5:.5 A5:1 G5:.5 E5:1 | F5:.75 E5:.25 D5:.5 C5:.5 A4:1 C5:1 |
        B4:.5 D5:.5 G5:1 F5:.5 D5:.5 B4:1 | E5:1.5 G5:.5 B5:1 G5:1 |
        A5:.5 G5:.5 E5:.5 A5:.5 C6:1 B5:1 | A5:1 F5:.5 C5:.5 F5:1 A5:1 |
        G5:.5 F5:.5 G5:.5 B5:.5 D6:2 | G#5:1 B5:1 E6:1 D6:.5 B5:.5 |
        D5:1 F5:.5 A5:.5 D6:1 C6:1 | C6:1 A5:.5 E5:.5 A5:2 |
        Bb5:1 A5:.5 F5:.5 D5:1 F5:1 | G5:1 D5:.5 B4:.5 G5:1 B5:1 |
        C6:.5 A5:.5 F5:.5 A5:.5 C6:1 D6:1 | B5:.5 G5:.5 D5:.5 G5:.5 B5:1 D6:1 |
        E6:2 D6:.5 C6:.5 B5:1 | G#5:1 B5:1 E5:1 r:1""")
    mix = Mix(len(prog) * 2 * 4 * B)
    gallop = [0, 0, 12, 0, 0, 12, 0, 12]
    for pas in range(2):
        off = pas * len(prog) * 4
        for beat, ln, m in mel:
            t = (off + beat) * B
            mix.add(lead(m, ln * B * 0.9, duty=0.5, vib=0.008), t, 0.26, 0.1, send=0.15)
            mix.add(lead(m - 12, ln * B * 0.9, duty=0.25), t, 0.10, -0.25, send=0.1)
            if pas == 1:
                mix.add(lead(m + 12, ln * B * 0.85, duty=0.125), t, 0.05, 0.4, send=0.2)
        for i, sym in enumerate(prog):
            c = chord(sym)
            t0 = (off + i * 4) * B
            for k in range(8):
                mix.add(pulse_bass(c["bass"] + gallop[k], B * 0.42), t0 + k * B / 2, 0.36, 0, send=0.02)
            tones = c["tones"]
            for k in range(16):  # up then down
                idx = k % 4 if (k // 4) % 2 == 0 else 3 - k % 4
                mix.add(arp(tones[idx % len(tones)] + 12, B * 0.2), t0 + k * B / 4, 0.06, -0.5, send=0.15)
            mix.add(pad(tones, 4 * B, 1200), t0, 0.06, 0, send=0.2)
            rock_drums(mix, t0, B, kicks=(0, 1.5, 2), sixteenths=pas == 1, crash_on=i % 4 == 0, fill=i in (7, 15))
    return mix.render(loop=True, rt60=1.2)


def song_boss():
    """Boss fights: heavier and darker, D minor."""
    B = 60 / 160
    prog = "Dm Dm Bb C Dm Dm Gm A Bb C Dm Bb Gm A Dm A".split()
    mel = melody("""
        D5:1.5 A4:.5 D5:.5 E5:.5 F5:1 | E5:.5 D5:.5 C#5:.5 D5:.5 A5:2 |
        Bb5:1 A5:.5 G5:.5 F5:1 D5:1 | E5:1 G5:1 C6:1 Bb5:.5 G5:.5 |
        A5:1.5 F5:.5 D5:1 F5:1 | A5:.5 Bb5:.5 A5:.5 G5:.5 F5:.5 E5:.5 D5:1 |
        G5:1 Bb5:1 D6:1.5 C6:.5 | C#6:2 E6:1 A5:1 |
        D6:1 Bb5:.5 F5:.5 Bb5:1 D6:1 | E6:1 C6:.5 G5:.5 C6:1 E6:1 |
        F6:2 E6:.5 D6:.5 A5:1 | D6:1.5 C6:.5 Bb5:1 F5:1 |
        G5:.5 A5:.5 Bb5:.5 C6:.5 D6:1 Bb5:1 | C#6:1 A5:.5 E5:.5 C#6:1 E6:1 |
        D6:3 A5:1 | E6:.5 D6:.5 C#6:.5 D6:.5 E6:1 A5:1""")
    mix = Mix(len(prog) * 2 * 4 * B)
    drive = [0, 0, 12, 0, 0, 12, 0, 7]
    for pas in range(2):
        off = pas * len(prog) * 4
        mix.add(brass(38, 8 * B, 900) + brass(45, 8 * B, 900), off * B, 0.35, 0, send=0.3)  # opening hit
        mix.add(crash(1.0, 2.0), off * B, 0.4, 0, send=0.2)
        for beat, ln, m in mel:
            t = (off + beat) * B
            mix.add(saw_lead(m - 12, ln * B * 0.92), t, 0.30, 0.05, send=0.15)
            mix.add(lead(m, ln * B * 0.9, duty=0.25), t, 0.07 if pas == 0 else 0.11, -0.3, send=0.2)
        for i, sym in enumerate(prog):
            c = chord(sym)
            t0 = (off + i * 4) * B
            for k in range(8):
                mix.add(grit_bass(c["root"] + drive[k], B * 0.45), t0 + k * B / 2, 0.34, 0, send=0)
            power = [c["root"] + 12, c["root"] + 19, c["root"] + 24]
            for hb in (0, 1.5):
                for m in power:
                    mix.add(brass(m, 0.45 * B, 1800), t0 + hb * B, 0.12, 0, send=0.15)
            mix.add(pad(c["tones"], 4 * B, 1000, a=0.4), t0, 0.07, 0, send=0.3)
            rock_drums(mix, t0, B, kicks=(0, 0.75, 1.5, 2, 2.75), sixteenths=True, crash_on=i % 4 == 0 and i > 0)
            if i in (7, 15):  # tom fill
                for q, m in enumerate((52, 50, 47, 45, 43, 40)):
                    mix.add(tom(m), t0 + (2.5 + q * 0.25) * B, 0.5, -0.4 + 0.16 * q, send=0.1)
    return mix.render(loop=True, rt60=1.3)


def song_final():
    """Villiam Burginson's: the menu theme turned into a minor-key anthem, E minor."""
    B = 60 / 120
    prog = "Em C D B7 Em C Am B7 C D Em Em/D C Am B7 B7".split()
    mel = melody("""
        B4:.5 E5:.5 G5:1 F#5:.5 E5:.5 G5:1 | E5:1.5 C5:.5 G4:1 C5:1 |
        D5:.5 F#5:.5 A5:1.5 G5:.5 F#5:1 | D#5:1 F#5:1 B5:2 |
        B5:.5 A5:.5 G5:.5 E5:.5 G5:1 B5:1 | C6:1.5 B5:.5 G5:1 E5:1 |
        A5:1 C6:1 E6:1 D6:.5 C6:.5 | B5:2 A5:.5 G5:.5 F#5:1 |
        G5:.5 E5:.5 C5:.5 E5:.5 G5:1 C6:1 | A5:.5 F#5:.5 D5:.5 F#5:.5 A5:1 D6:1 |
        B5:2 G5:1 E5:1 | F#5:1 G5:1 A5:1 B5:1 |
        C6:1.5 B5:.5 A5:1 G5:1 | E5:1 A5:1 C6:1 E6:1 |
        D#6:2 B5:1 F#5:1 | A5:.5 G5:.5 F#5:.5 D#5:.5 B4:2""")
    mix = Mix(len(prog) * 2 * 4 * B)
    for pas in range(2):
        off = pas * len(prog) * 4
        for beat, ln, m in mel:
            t = (off + beat) * B
            mix.add(brass(m - 12, ln * B * 0.95, 2800), t, 0.34, 0, send=0.2)
            mix.add(lead(m, ln * B * 0.9, duty=0.25), t, 0.10, 0.35, send=0.2)
            if pas == 1:
                mix.add(organ(m - 24, ln * B * 0.95), t, 0.25, -0.35, send=0.15)
                mix.add(saw_lead(m, ln * B * 0.9), t, 0.08, 0.2, send=0.25)
        for i, sym in enumerate(prog):
            c = chord(sym)
            t0 = (off + i * 4) * B
            for k in range(8):
                mix.add(grit_bass(c["bass"] + (12 if k % 4 == 2 else 0), B * 0.45), t0 + k * B / 2, 0.32, 0, send=0)
                for m in c["tones"]:
                    mix.add(organ(m - 12, B * 0.4), t0 + k * B / 2, 0.05, -0.15, send=0.1)
            mix.add(pad(c["tones"], 4 * B, 1400, a=0.5), t0, 0.08, 0, send=0.35)
            rock_drums(mix, t0, B, kicks=(0, 0.5, 2.5), snares=(2,), sixteenths=True,
                       crash_on=i % 4 == 0, fill=i in (7, 15))
            mix.add(tom(38, 1.0), t0, 0.45, 0, send=0.15)
    return mix.render(loop=True, rt60=1.6)


def jingle_victory():
    B = 60 / 150
    mix = Mix(5.0, tail=1.0)
    for beat, ln, name in ((0, 1 / 3, "G4"), (1 / 3, 1 / 3, "A4"), (2 / 3, 1 / 3, "B4"), (1, 1, "C5"),
                           (2, 0.5, "E5"), (2.5, 0.5, "G5"), (3, 3, "C6")):
        m = note(name)
        mix.add(lead(m, ln * B * 0.95, duty=0.25), beat * B, 0.32, 0, send=0.2)
        mix.add(lead(m - 12, ln * B * 0.95, duty=0.5), beat * B, 0.12, -0.3, send=0.15)
    for name in ("C4", "E4", "G4", "C5"):
        mix.add(brass(note(name), 3 * B), 3 * B, 0.16, 0, send=0.3)
    mix.add(tri_bass(note("C3"), 3 * B), 3 * B, 0.4)
    for k in range(12):  # snare roll into the big note
        mix.add(snare(0.3 + 0.05 * k), k * B / 4, 0.25, 0.1, send=0.1)
    mix.add(crash(1.0, 1.6), 3 * B, 0.4, 0, send=0.2)
    mix.add(kick(), 3 * B, 0.6)
    return mix.render(loop=False, rt60=1.6, target_rms=0.14)


def jingle_gameover():
    """Wah, wah, wah, waaah."""
    mix = Mix(4.5, tail=1.0)
    for i, (t, dur, name) in enumerate(((0.0, 0.42, "Bb3"), (0.5, 0.42, "A3"), (1.0, 0.42, "Ab3"), (1.5, 1.9, "G3"))):
        mix.add(trombone(note(name), dur, wobble=i == 3), t, 0.5, 0, send=0.2)
    return mix.render(loop=False, rt60=1.2, target_rms=0.14)


MUSIC = {"title": song_title, "office": song_office, "battle": song_battle, "boss": song_boss,
         "final": song_final, "victory": jingle_victory, "gameover": jingle_gameover}


# --------------------------------------------------------------------------- sounds
def bell(f, dur, ratio=1.41, index=2.0, decay=0.4):
    n = ns(dur)
    t = secs(n)
    x = np.sin(2 * np.pi * f * t + index * np.exp(-t / (decay * 0.5)) * np.sin(2 * np.pi * f * ratio * t))
    return x * perc(n, decay)


def chime(notes, gap, ring=0.5):
    out = np.zeros(ns(gap * len(notes) + ring))
    for k, m in enumerate(notes):
        f = float(hz(m))
        n = ns(ring)
        t = secs(n)
        x = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.1)) * perc(n, ring / 3)
        i = ns(k * gap)
        out[i:i + n] += x[:len(out) - i]
    return out


def noise_sweep(dur, f0, f1, f2=None, q=0.5):
    """Noise whose band glides f0 -> f1 (-> f2) Hz, swelling in and out."""
    n = ns(dur)
    t = secs(n)
    p = t / dur
    if f2 is None:
        fc = f0 * (f1 / f0) ** p
    else:
        fc = np.where(p < 0.5, f0 * (f1 / f0) ** (p * 2), f1 * (f2 / f1) ** ((p - 0.5) * 2))
    y = moving_filter(rng.standard_normal(n), fc, "band", q)
    return y / (np.abs(y).max() + 1e-9) * np.sin(np.pi * p) ** 2


def place(parts, length=None):
    """[(time, mono signal, gain)] -> one mono signal."""
    end = max(ns(t) + len(s) for t, s, _ in parts)
    out = np.zeros(length or end)
    for t, s, g in parts:
        i = ns(t) if t > 0 else 0
        out[i:i + len(s)] += s[:len(out) - i] * g
    return out


def thump(f0=160, f1=50, decay=0.09, dur=0.3):
    n = ns(dur)
    t = secs(n)
    return np.sin(2 * np.pi * np.cumsum(glide(f0, f1, n, tau=0.03)) / SR) * np.exp(-t / decay)


def sfx_hit():
    """A punch: a thump, a crack, and a low sub underneath so it lands with weight."""
    n = ns(0.36)
    t = secs(n)
    crack = filt(rng.standard_normal(n), "band", (700, 4000)) * np.exp(-t / 0.035)
    return np.tanh(2.0 * place([(0, thump(), 1.0), (0, crack, 0.8), (0, thump(95, 38, 0.15, 0.36), 0.9)], n))


def sfx_glint():
    """The 'ting' of an enemy's glint before it strikes."""
    n = ns(0.5)
    t = secs(n)
    shimmer = filt(rng.standard_normal(n), "high", 6500) * np.exp(-t / 0.06) * 0.25
    return place([(0, bell(2637, 0.5, 2.76, 1.4, 0.16), 0.8), (0.02, bell(3951, 0.4, 2.0, 0.7, 0.1), 0.4),
                  (0, shimmer, 1.0)], n)


def sfx_crit():
    n = ns(0.55)
    t = secs(n)
    snap = filt(rng.standard_normal(n), "high", 3000) * np.exp(-t / 0.05)
    zing = filt(osc("saw", glide(2600, 700, n, tau=0.12), n), "low", 6000) * np.exp(-t / 0.12) * 0.3
    return np.tanh(1.6 * (place([(0, sfx_hit(), 1.2)], n) + 0.7 * snap + zing))


def sfx_throw():
    n = ns(0.16)
    pew = osc("pulse", glide(1100, 260, n, tau=0.05), n, 0.5) * perc(n, 0.07)
    return filt(pew, "low", 5000) * 0.6 + noise_sweep(0.16, 900, 3500) * 0.35


def sfx_magic():
    parts = [(0, noise_sweep(0.45, 600, 5000), 0.25)]
    scale = [84, 86, 88, 91, 93, 96, 98]
    for k in range(7):
        parts.append((k * 0.055, bell(float(hz(scale[rng.integers(len(scale))])), 0.35, 2.0, 1.0, 0.12), 0.35))
    return place(parts)


def sfx_heal():
    return place([(0, chime([84, 88, 91, 96], 0.07, 0.6), 0.8), (0.05, noise_sweep(0.5, 2000, 8000), 0.12)])


def sfx_buff():
    n = ns(0.3)
    up = filt(osc("pulse", glide(330, 990, n), n, 0.5, vib=0.02, vib_rate=14), "low", 5000) * adsr(n, 0.01, 0.05, 0.8, 0.05)
    return place([(0, up, 0.5), (0.26, bell(1568, 0.4, 2.0, 0.8, 0.15), 0.4)])


def sfx_debuff():
    n = ns(0.4)
    f = glide(660, 170, n)
    x = osc("saw", f, n) + osc("saw", f * 1.06, n)
    return filt(x, "low", 2000) * adsr(n, 0.01, 0.05, 0.8, 0.1) * 0.5


def sfx_shield():
    n = ns(0.6)
    t = secs(n)
    shimmer = filt(rng.standard_normal(n), "high", 6000) * np.exp(-t / 0.15) * 0.2
    return bell(1200, 0.6, 1.41, 3.0, 0.3) + bell(1800, 0.6, 2.76, 1.5, 0.2) * 0.4 + shimmer


def sfx_stun():
    parts = []
    for k in range(4):
        n = ns(0.08)
        t = secs(n)
        f = 2600 + 900 * np.sin(np.pi * t / 0.08)
        parts.append((k * 0.1, osc("sine", f, n) * np.sin(np.pi * t / 0.08), 0.5))
    return place(parts)


def sfx_poison():
    parts = []
    for k in range(6):
        n = ns(0.06)
        f0 = 250 + 400 * rng.random()
        parts.append((k * 0.055 + 0.01 * rng.random(), osc("sine", glide(f0, f0 * 1.8, n), n) * perc(n, 0.03, 0.004), 0.5))
    return place(parts)


def sfx_burn():
    n = ns(0.5)
    t = secs(n)
    pops = (rng.random(n) < 0.02) * rng.standard_normal(n) * 4
    whoosh = filt(rng.standard_normal(n), "band", (400, 2000)) * np.exp(-t / 0.15) * 0.8
    x = filt(rng.standard_normal(n) * 0.6 + pops, "band", (1500, 6000)) + whoosh
    return x * np.minimum(1, t / 0.01) * np.exp(-t / 0.25)


def sfx_faint():
    n = ns(0.65)
    whistle = osc("sine", glide(1100, 280, n), n, vib=0.03, vib_rate=7) * adsr(n, 0.02, 0.1, 0.8, 0.08)
    return place([(0, whistle, 0.45), (0.6, thump(110, 40, 0.12, 0.3), 0.7)])


def sfx_revive():
    n = ns(0.4)
    slide = osc("sine", glide(300, 1100, n), n) * adsr(n, 0.02, 0.05, 0.8, 0.05)
    return place([(0, slide, 0.4), (0.35, chime([84, 91, 96], 0.06, 0.5), 0.6)])


def sfx_ult():
    n = ns(0.4)
    rise = noise_sweep(0.4, 400, 6000) * np.linspace(0.2, 1, n)
    boom_n = ns(1.0)
    t = secs(boom_n)
    boom = thump(90, 32, 0.4, 1.0) + filt(rng.standard_normal(boom_n), "low", 1500) * np.exp(-t / 0.25) * 0.6
    stab = sum(filt(osc("saw", float(hz(m)), boom_n), "low", 3500) for m in (72, 76, 79, 84)) * np.exp(-t / 0.35) * 0.2
    shine = filt(rng.standard_normal(boom_n), "high", 4000) * np.exp(-t / 0.5) * 0.25
    return np.tanh(1.4 * place([(0, rise, 0.5), (0.38, boom, 1.0), (0.38, stab, 1.0), (0.38, shine, 1.0)]))


def sfx_aoe():
    return place([(0, noise_sweep(0.45, 300, 3000, 500, 0.6), 0.8), (0.18, thump(120, 45, 0.15, 0.4), 0.6)])


def sfx_boom():
    n = ns(1.0)
    t = secs(n)
    body = filt(rng.standard_normal(n), "low", 1200) * np.exp(-t / 0.3)
    return np.tanh(1.5 * (body + thump(70, 30, 0.35, 1.0)))


def sfx_car():
    n = ns(0.9)
    t = secs(n)
    f = np.where(t < 0.45, 70 + 60 * (t / 0.45), 130 - 70 * ((t - 0.45) / 0.45))  # revs up, then drives past
    engine = filt(osc("saw", f, n) + 0.5 * osc("pulse", f * 2, n, 0.3), "low", 1500)
    level = np.exp(-((t - 0.45) / 0.25) ** 2)
    return np.tanh(1.5 * engine) * level * 0.7 + noise_sweep(0.9, 1500, 4000, 1200) * 0.25


def sfx_hearts():
    parts = []
    for k in range(3):
        n = ns(0.12)
        parts.append((k * 0.14, osc("sine", glide(420, 900, n), n) * perc(n, 0.06, 0.005), 0.5))
    return place(parts)


def sfx_popup():
    return place([(0, bell(1319, 0.25, 2.0, 0.6, 0.1), 0.5), (0.12, bell(988, 0.5, 2.0, 0.6, 0.2), 0.5)])


def sfx_spawn():
    n = ns(0.08)
    return osc("sine", glide(250, 900, n), n) * perc(n, 0.03, 0.002)


def sfx_alert():
    a = lead(note("B5"), 0.07, 0.25)
    b = lead(note("E6"), 0.18, 0.25)
    return place([(0, a, 0.6), (0.07, b, 0.6), (0, thump(200, 80, 0.05, 0.12), 0.3)])


def sfx_ding():
    return place([(0, bell(880, 1.8, 2.0, 1.2, 0.6), 1.0), (0, bell(1760, 1.2, 3.0, 0.4, 0.3), 0.15)])


def sfx_pick():
    return place([(0, noise_sweep(0.3, 800, 6000), 0.2), (0.08, chime([84, 88, 91], 0.0, 0.6), 0.5)])


def sfx_coin():
    n = ns(0.25)
    t = secs(n)
    rattle = filt(rng.standard_normal(n), "band", (3000, 9000)) * (0.5 + 0.5 * np.sin(2 * np.pi * 40 * t)) * np.exp(-t / 0.08)
    return place([(0, bell(1568, 0.4, 3.5, 1.0, 0.15), 0.5), (0.06, bell(2093, 0.5, 3.5, 1.0, 0.2), 0.5), (0, rattle, 0.2)])


def sfx_banner():
    n = ns(1.4)
    t = secs(n)
    low = (brass(38, 1.4, 900) + brass(45, 1.4, 900) + brass(50, 1.4, 900)) * np.exp(-t / 0.6)
    swell_n = ns(0.35)
    swell = filt(rng.standard_normal(swell_n), "high", 3000) * np.linspace(0, 1, swell_n) ** 2
    return place([(0, swell, 0.3), (0.33, low, 1.0), (0.33, thump(80, 35, 0.3, 0.8), 0.7), (0.33, crash(0.8, 0.8), 1.0)])


SFX = {  # name: (sound, level, room)
    "click": (lambda: filt(osc("pulse", 1500, ns(0.05)) * perc(ns(0.05), 0.012) * 0.5
                            + osc("sine", 2300, ns(0.05)) * perc(ns(0.05), 0.008) * 0.4, "low", 7000), 0.4, False),
    "blip": (lambda: filt(osc("pulse", 620, ns(0.045)), "low", 3500) * adsr(ns(0.045), 0.002, 0.02, 0.5, 0.015), 0.25, False),
    "hit": (sfx_hit, 0.9, True), "crit": (sfx_crit, 0.95, True),
    "swing": (lambda: noise_sweep(0.22, 500, 2500, 700), 0.45, True), "throw": (sfx_throw, 0.45, True),
    "magic": (sfx_magic, 0.5, True), "heal": (sfx_heal, 0.55, True), "buff": (sfx_buff, 0.5, True),
    "debuff": (sfx_debuff, 0.5, True), "shield": (sfx_shield, 0.5, True), "stun": (sfx_stun, 0.45, True),
    "poison": (sfx_poison, 0.45, True), "burn": (sfx_burn, 0.45, True),
    "miss": (lambda: noise_sweep(0.18, 1500, 4000), 0.4, True), "faint": (sfx_faint, 0.6, True),
    "revive": (sfx_revive, 0.55, True), "ult": (sfx_ult, 0.95, True), "aoe": (sfx_aoe, 0.6, True),
    "boom": (sfx_boom, 0.85, True), "car": (sfx_car, 0.7, True), "hearts": (sfx_hearts, 0.45, True),
    "popup": (sfx_popup, 0.5, False), "spawn": (sfx_spawn, 0.5, True), "alert": (sfx_alert, 0.6, False),
    "ding": (sfx_ding, 0.55, True), "pick": (sfx_pick, 0.5, False), "coin": (sfx_coin, 0.5, False),
    "banner": (sfx_banner, 0.8, True), "glint": (sfx_glint, 0.5, False),
}


def render_sfx(fn, level, room):
    x = np.asarray(fn(), dtype=float)
    if room:  # a little room so the sounds sit in the same space
        x = np.concatenate([x, np.zeros(ns(0.4))])
        x = x + reverb(x[None, :], 0.45)[0][:len(x)] * 0.12
        x = trim(x[None, :], 0.02)[0]
    x = filt(x, "high", 40)
    return x * (level / (np.abs(x).max() + 1e-9))


# --------------------------------------------------------------------------- files
def write_wav(path, x):
    x = np.atleast_2d(x)
    pcm = (np.clip(x.T, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(x.shape[0])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser(description="The game's music and sound effects")
    ap.add_argument("--out", required=True, help="folder for music/*.wav and sfx/*.wav")
    ap.add_argument("--only", help="comma-separated names (default: everything)")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None
    for sub, table in (("music", MUSIC), ("sfx", SFX)):
        os.makedirs(os.path.join(a.out, sub), exist_ok=True)
        for name, spec in table.items():
            if only and name not in only:
                continue
            x = spec() if sub == "music" else render_sfx(*spec)
            write_wav(os.path.join(a.out, sub, name + ".wav"), x)
            print("%s/%s.wav: %.2fs" % (sub, name, np.atleast_2d(x).shape[1] / SR), flush=True)


if __name__ == "__main__":
    main()
