"""
The trailer's narration, spoken by Kokoro (an open-source text-to-speech model, Apache-2.0)
through kokoro-onnx, which runs on the CPU.

    python art/trailer/voice.py --models DIR --out VO_DIR [--voice bm_george] [--speed 0.86]

DIR holds kokoro-v1.0.onnx and voices-v1.0.bin (from the kokoro-onnx releases on GitHub).
Writes n1.wav ... n6.wav, one per line in timeline.NARRATION; music.py mixes them in.
--voice can blend voices: "bm_george:0.7,am_fenrir:0.3".
"""

import argparse
import os
import sys

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timeline as TL  # noqa: E402

# How each line is spoken: phrases, each followed by a pause (seconds). Kokoro's own pauses
# at "..." are short, so dramatic beats are put in by hand.
SPOKEN = {
    "n1": [("Every office", 0.5), ("has its ghosts.", 0.0)],
    "n2": [("Some of them", 0.55), ("never clock out.", 0.0)],
    "n3": [("He gave this company everything.", 0.45), ("Even his lunch break.", 0.0)],
    "n4": [("Now", 0.5), ("he wants yours.", 0.0)],
    "n5": [("Clock in,", 0.3), ("dorks.", 0.0)],
    "n6": [("Your shift", 0.5), ("starts now.", 0.0)],
}


def trim(x, thr=0.01, pad=0.03, sr=24000):
    idx = np.nonzero(np.abs(x) > thr)[0]
    if not len(idx):
        return x
    p = int(pad * sr)
    return x[max(0, idx[0] - p): idx[-1] + p]


def voice_style(k, spec):
    """A voice name, or a blend like "bm_george:0.7,am_fenrir:0.3"."""
    if ":" not in spec:
        return spec
    parts = [p.split(":") for p in spec.split(",")]
    total = sum(float(w) for _, w in parts)
    return sum(k.get_voice_style(n) * (float(w) / total) for n, w in parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice", default="bm_george")
    ap.add_argument("--speed", type=float, default=0.84)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    k = Kokoro(os.path.join(a.models, "kokoro-v1.0.onnx"), os.path.join(a.models, "voices-v1.0.bin"))
    style = voice_style(k, a.voice)
    lang = "en-gb" if a.voice.startswith("b") else "en-us"
    for vid, t, text in TL.NARRATION:
        parts, sr = [], 24000
        for phrase, pause in SPOKEN.get(vid, [(text, 0.0)]):
            samples, sr = k.create(phrase, voice=style, speed=a.speed, lang=lang)
            parts.append(trim(np.asarray(samples, dtype=np.float32), sr=sr))
            if pause > 0:
                parts.append(np.zeros(int(pause * sr), np.float32))
        line = np.concatenate(parts)
        line = line / (np.abs(line).max() + 1e-9) * 0.9
        sf.write(os.path.join(a.out, vid + ".wav"), line, sr, subtype="PCM_16")
        print("%s %.2fs  %s" % (vid, len(line) / sr, " / ".join(p for p, _ in SPOKEN.get(vid, [(text, 0)]))))


if __name__ == "__main__":
    main()
