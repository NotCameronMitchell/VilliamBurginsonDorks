# Makes the trailer end to end:
#   powershell -File art/trailer/make_trailer.ps1 [-Out DIR] [-Res 1280x720] [-Samples 32] [-Voice bm_george] [-Step all|vo|music|gameplay|frames|edit|stills]
# 1. vo:       the narration (timeline.py NARRATION), spoken by Kokoro (voice.py) if it's set up
#              in $env:KOKORO_HOME (default ~\.vbd\kokoro: .venv with kokoro-onnx + soundfile, and
#              models\ with kokoro-v1.0.onnx and voices-v1.0.bin); otherwise Windows' built-in voice
# 2. music:    the soundtrack, synthesized, with the narration mixed in (music.py; needs Python
#              with numpy and scipy: set $env:VBD_PYTHON, or the Kimodo venv is used, or "python")
# 3. gameplay: a fight against the ghost, recorded from the game itself with Godot's Movie Maker
#              into DIR\gameplay (Godot from $env:GODOT, PATH or winget). timeline.py
#              GAMEPLAY_CUTS picks which moments go into the montage.
# 4. frames:   every frame rendered in Blender (trailer.py; resumable)
# 5. edit:     titles, subtitles, fades, gameplay and the soundtrack cut together into DIR\trailer.mp4
param(
    [string]$Out = (Join-Path ([Environment]::GetFolderPath("MyVideos")) "VilliamBurginsonDorks_trailer"),
    [string]$Res = "1280x720",
    [int]$Samples = 32,
    [string]$Voice = "bm_george",
    [string]$Step = "all"
)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force $Out | Out-Null
$kokoro = if ($env:KOKORO_HOME) { $env:KOKORO_HOME } else { Join-Path $env:USERPROFILE ".vbd\kokoro" }
$kokoroPy = Join-Path $kokoro ".venv\Scripts\python.exe"
$useKokoro = (Test-Path $kokoroPy) -and (Test-Path (Join-Path $kokoro "models\kokoro-v1.0.onnx"))

function Run-Blender([string[]]$extra) {
    $blender = $env:BLENDER
    if (-not $blender) { $c = Get-Command blender -ErrorAction SilentlyContinue; if ($c) { $blender = $c.Source } }
    if (-not $blender) { $blender = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\blender-launcher.exe" }
    $log = Join-Path $Out "blender.log"
    if (Test-Path $log) { Remove-Item $log }
    $args0 = @("--factory-startup", "-b", "-P", "`"$here\trailer.py`"", "--", "--out", "`"$Out`"", "--res", $Res,
               "--samples", "$Samples", "--log", "`"$log`"") + $extra
    $before = @(Get-Process blender -ErrorAction SilentlyContinue | ForEach-Object Id)
    Start-Process -FilePath $blender -ArgumentList $args0 -WindowStyle Hidden -Wait
    Start-Sleep -Seconds 2  # the Store launcher returns at once; wait for the real Blender
    $procs = @(Get-Process blender -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id })
    if ($procs.Count -gt 0) { $procs | Wait-Process }
    if (Test-Path $log) { Get-Content $log | Select-Object -Last 8 }
}

if ($Step -in @("all", "vo") -and $useKokoro) {
    & $kokoroPy (Join-Path $here "voice.py") --models (Join-Path $kokoro "models") --out (Join-Path $Out "vo") --voice $Voice
    Write-Host "narration (Kokoro, $Voice): $(Join-Path $Out 'vo')"
} elseif ($Step -in @("all", "vo")) {
    Add-Type -AssemblyName System.Speech
    $vo = Join-Path $Out "vo"
    New-Item -ItemType Directory -Force $vo | Out-Null
    # The lines, with pauses (keep in step with timeline.py NARRATION).
    $lines = [ordered]@{
        "n1" = "Every office<break time='350ms'/> has its ghosts.";
        "n2" = "Some of them<break time='450ms'/> never clock out.";
        "n3" = "He gave this company everything.<break time='350ms'/> Even his lunch break.";
        "n4" = "Now<break time='400ms'/> he wants yours.";
        "n5" = "Clock in<break time='350ms'/> dorks.";
        "n6" = "Your shift<break time='400ms'/> starts now."
    }
    foreach ($k in $lines.Keys) {
        $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
        try { $s.SelectVoice("Microsoft David Desktop") } catch {}
        $s.Rate = $(if ($k -eq "n3") { -1 } else { -2 })
        $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(48000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
        $s.SetOutputToWaveFile((Join-Path $vo "$k.wav"), $fmt)
        $s.SpeakSsml("<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><prosody pitch='low'>" + $lines[$k] + "</prosody></speak>")
        $s.Dispose()
    }
    Write-Host "narration: $vo"
}
if ($Step -in @("all", "music")) {
    $py = $env:VBD_PYTHON
    if (-not $py) {
        $kim = Join-Path $env:LOCALAPPDATA "VilliamBurginsonDorks\kimodo\.venv\Scripts\python.exe"
        $py = $(if (Test-Path $kim) { $kim } else { "python" })
    }
    $pitch = $(if ($useKokoro) { "0.92" } else { "0.89" })  # how much to deepen the narration
    & $py (Join-Path $here "music.py") --vo (Join-Path $Out "vo") --pitch $pitch --out (Join-Path $Out "trailer_audio.wav")
}
if ($Step -in @("all", "gameplay")) {
    $godot = $env:GODOT
    if (-not $godot) { $c = Get-Command godot -ErrorAction SilentlyContinue; if ($c) { $godot = $c.Source } }
    if (-not $godot) {
        $godot = Get-ChildItem (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages") -Recurse -Filter "Godot_v4*_console.exe" -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName
    }
    if ($godot) {
        $gdir = Join-Path $Out "gameplay"
        Remove-Item -Recurse -Force $gdir -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force $gdir | Out-Null
        $w, $h = $Res -split "x"
        $root = (Resolve-Path (Join-Path $here "..\..")).Path
        # 480 frames at 24 fps: the ghost's entrance and the heroes' ultimates (ready from turn 1).
        & $godot --path $root --write-movie (Join-Path $gdir "gameplay.png") --fixed-fps 24 --resolution "${w}x${h}" `
            --quit-after 480 -- --fight=ghost --party=james,cole,cam,sam --auto --skip-story --ult-first --mute `
            --save-dir=user://trailer_movie/ 2>&1 | Out-Null
        Write-Host "gameplay: $((Get-ChildItem $gdir -Filter *.png).Count) frames in $gdir"
    } else {
        Write-Host "gameplay: Godot not found (set `$env:GODOT); the montage stays all cinematic"
    }
}
if ($Step -in @("all", "frames")) { Run-Blender @("--stage", "frames") }
if ($Step -eq "stills") { Run-Blender @("--stage", "stills") }
if ($Step -in @("all", "edit")) {
    Run-Blender @("--stage", "edit", "--audio", "`"$(Join-Path $Out 'trailer_audio.wav')`"")
    Write-Host "trailer: $(Join-Path $Out 'trailer.mp4')"
}
