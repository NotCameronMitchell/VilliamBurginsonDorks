# Makes the trailer end to end:
#   powershell -File art/trailer/make_trailer.ps1 [-Out DIR] [-Res 1280x720] [-Samples 32] [-Step all|vo|music|frames|edit|stills]
# 1. vo:     narration lines with Windows' built-in voice (timeline.py NARRATION)
# 2. music:  the soundtrack, synthesized, with the narration mixed in (music.py; needs Python
#            with numpy and scipy: set $env:VBD_PYTHON, or the Kimodo venv is used, or "python")
# 3. frames: every frame rendered in Blender (trailer.py; resumable)
# 4. edit:   titles, subtitles, fades and the soundtrack cut together into DIR\trailer.mp4
param(
    [string]$Out = (Join-Path ([Environment]::GetFolderPath("MyVideos")) "VilliamBurginsonDorks_trailer"),
    [string]$Res = "1280x720",
    [int]$Samples = 32,
    [string]$Step = "all"
)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force $Out | Out-Null

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

if ($Step -in @("all", "vo")) {
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
    & $py (Join-Path $here "music.py") --vo (Join-Path $Out "vo") --out (Join-Path $Out "trailer_audio.wav")
}
if ($Step -in @("all", "frames")) { Run-Blender @("--stage", "frames") }
if ($Step -eq "stills") { Run-Blender @("--stage", "stills") }
if ($Step -in @("all", "edit")) {
    Run-Blender @("--stage", "edit", "--audio", "`"$(Join-Path $Out 'trailer_audio.wav')`"")
    Write-Host "trailer: $(Join-Path $Out 'trailer.mp4')"
}
