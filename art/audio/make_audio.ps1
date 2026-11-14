# Makes the game's music and sound effects (make_audio.py) and puts them in assets/audio:
# sounds as WAV in assets/audio/sfx, music as OGG Vorbis in assets/audio/music (encoded by
# Blender, through to_ogg.py).
#   powershell -File art/audio/make_audio.ps1 [--only title,hit]
# Python with numpy and scipy comes from $env:VBD_PYTHON, the Kimodo venv, or "python".
# Blender comes from $env:BLENDER, PATH, or the Microsoft Store install.
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $here "..\..")).Path
$py = $env:VBD_PYTHON
if (-not $py) {
    $kim = Join-Path $env:LOCALAPPDATA "VilliamBurginsonDorks\kimodo\.venv\Scripts\python.exe"
    $py = $(if (Test-Path $kim) { $kim } else { "python" })
}
$tmp = Join-Path $env:TEMP "vbd_audio"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
& $py (Join-Path $here "make_audio.py") --out $tmp @args
if ($LASTEXITCODE -ne 0) { Write-Error "make_audio.py failed"; exit 1 }

$sfx = Join-Path $root "assets\audio\sfx"
$music = Join-Path $root "assets\audio\music"
New-Item -ItemType Directory -Force $sfx, $music | Out-Null
Copy-Item "$tmp\sfx\*.wav" $sfx -Force -ErrorAction SilentlyContinue
if (-not (Get-ChildItem "$tmp\music" -Filter *.wav -ErrorAction SilentlyContinue)) { exit 0 }

$blender = $env:BLENDER
if (-not $blender) { $c = Get-Command blender -ErrorAction SilentlyContinue; if ($c) { $blender = $c.Source } }
if (-not $blender) {
    $launcher = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\blender-launcher.exe"
    if (Test-Path $launcher) { $blender = $launcher }
}
if (-not $blender) { Write-Error "Blender not found. Install it or set `$env:BLENDER to blender.exe."; exit 1 }
$log = Join-Path $tmp "ogg.log"
$before = @(Get-Process blender -ErrorAction SilentlyContinue | ForEach-Object Id)
Start-Process -FilePath $blender -WindowStyle Hidden -Wait -ArgumentList @(
    "--factory-startup", "-b", "-P", "`"$here\to_ogg.py`"", "--", "`"$tmp\music`"", "`"$music`"", "--log", "`"$log`"")
# The Store launcher returns right away; wait for the real blender.exe it started.
Start-Sleep -Seconds 2
$procs = @(Get-Process blender -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id })
if ($procs.Count -gt 0) { $procs | Wait-Process }
if (Test-Path $log) { Get-Content $log } else { Write-Error "No log written (Blender didn't run the script)."; exit 1 }
