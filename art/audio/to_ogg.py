"""
Blender script: turns WAV files into OGG Vorbis with Blender's own encoder (so no extra
tools are needed). art/audio/make_audio.ps1 runs it:

    blender --factory-startup -b -P art/audio/to_ogg.py -- SRC_DIR DST_DIR [--log FILE]

The OGG is exactly as long as the WAV, so music loops stay seamless.
"""

import os
import sys
import traceback
import wave

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, DST = argv[0], argv[1]
LOG = argv[argv.index("--log") + 1] if "--log" in argv else None
_log = open(LOG, "w", encoding="utf-8") if LOG else None


def say(*a):
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    if _log:
        _log.write(msg + "\n")
        _log.flush()


def main():
    os.makedirs(DST, exist_ok=True)
    scene = bpy.context.scene
    se = scene.sequence_editor or scene.sequence_editor_create()
    done = 0
    for name in sorted(os.listdir(SRC)):
        if not name.lower().endswith(".wav"):
            continue
        src = os.path.join(SRC, name)
        with wave.open(src) as w:
            seconds = w.getnframes() / w.getframerate()
            channels = w.getnchannels()
        # Frames of 1/100 s, with the frame rate nudged so the length comes out exact.
        frames = max(1, round(seconds * 100))
        scene.render.fps = 100
        scene.render.fps_base = seconds * 100 / frames
        for s in list(se.strips):
            se.strips.remove(s)
        se.strips.new_sound(name, src, 1, 1)
        scene.frame_start, scene.frame_end = 1, frames
        out = os.path.join(DST, name[:-4] + ".ogg")
        bpy.ops.sound.mixdown(filepath=out, check_existing=False, relative_path=False, container="OGG",
                              codec="VORBIS", format="F32", mixrate=44100, bitrate=160,
                              channels="STEREO" if channels == 2 else "MONO")
        say("%s: %.2fs -> %d KB" % (name, seconds, os.path.getsize(out) // 1024))
        done += 1
    say("DONE %d files" % done)


try:
    main()
except Exception:
    say("FAILED\n" + traceback.format_exc())
