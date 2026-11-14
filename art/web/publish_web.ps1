# Builds the browser version and (with -Upload) publishes it to GitHub Pages.
#   powershell -File art/web/publish_web.ps1 [-Upload] [-Tag web-8]
#
# 1. Export: Godot's "Web" preset (made here if export_presets.cfg doesn't have it; that file
#    isn't in git). It leaves out the alternate skins to keep the download small: a skin
#    falls back to the hero's normal outfit. Needs Godot's web export templates in
#    ~/.vbd/godot_templates/<version> (from the official export_templates.tpz).
# 2. Split: the .pck goes up in pieces of 40 MB or less (art/web/loader.js puts them back
#    together in the browser), so no single file is too big for a host or an upload.
# 3. Upload (-Upload): the files go to a GitHub release (-Tag), and the "Web version"
#    workflow (.github/workflows/web.yml) copies them to GitHub Pages. Uses the GitHub CLI
#    (gh, signed in), from PATH or ~/.vbd/gh/bin.
param([switch]$Upload, [string]$Tag = "web-8", [string]$Version = "4.7.2.stable")
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $here "..\..")).Path
$out = Join-Path $root "build\web"
$godot = $env:GODOT
if (-not $godot) { $c = Get-Command godot -ErrorAction SilentlyContinue; if ($c) { $godot = $c.Source } }
if (-not $godot) {
    $godot = Get-ChildItem (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages") -Recurse -Filter "Godot_v4*_console.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $godot) { throw "Godot not found (set `$env:GODOT)" }

# --- the Web preset
$presets = Join-Path $root "export_presets.cfg"
$cfg = if (Test-Path $presets) { Get-Content $presets -Raw } else { "" }
if ($cfg -notmatch 'platform="Web"') {
    $tpl = (Join-Path $env:USERPROFILE ".vbd\godot_templates\$Version") -replace '\\', '/'
    if (-not (Test-Path "$tpl/web_nothreads_release.zip")) { throw "Web export templates missing: $tpl" }
    $keep = "mason", "james", "cole", "cam", "sam", "sarah", "cole_uw", "james_buff"  # heroes and forms
    $skins = Get-ChildItem (Join-Path $root "assets\models\heroes") -Filter *.glb | Where-Object { $keep -notcontains $_.BaseName } |
        ForEach-Object { "assets/models/heroes/" + $_.Name }
    $n = ([regex]::Matches($cfg, '\[preset\.\d+\]')).Count
    $cfg = $cfg.TrimEnd() + @"


[preset.$n]

name="Web"
platform="Web"
runnable=false
advanced_options=false
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter="art/*, tests/*, docs/*, build/*, $($skins -join ', ')"
export_path="build/web/index.html"
patches=PackedStringArray()
encryption_include_filters=""
encryption_exclude_filters=""
seed=0
encrypt_pck=false
encrypt_directory=false
script_export_mode=2

[preset.$n.options]

custom_template/debug="$tpl/web_nothreads_debug.zip"
custom_template/release="$tpl/web_nothreads_release.zip"
variant/extensions_support=false
variant/thread_support=false
vram_texture_compression/for_desktop=true
vram_texture_compression/for_mobile=false
html/export_icon=true
html/custom_html_shell=""
html/head_include=""
html/canvas_resize_policy=2
html/focus_canvas_on_start=true
html/experimental_virtual_keyboard=false
progressive_web_app/enabled=false
"@
    [IO.File]::WriteAllText($presets, $cfg + "`n")
    Write-Host "added the Web preset ($($skins.Count) skins left out)"
}

# --- export
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force $out | Out-Null
& $godot --headless --path $root --export-release "Web" (Join-Path $out "index.html") 2>&1 | Out-Null
if (-not (Test-Path (Join-Path $out "index.pck"))) { throw "the web export failed (no index.pck)" }

# --- split the pack and switch the page to the piece loader
$pck = Join-Path $out "index.pck"
$bytes = [IO.File]::ReadAllBytes($pck)
$chunk = 40MB
$parts = @()
for ($i = 0; $i * $chunk -lt $bytes.Length; $i++) {
    $len = [Math]::Min($chunk, $bytes.Length - $i * $chunk)
    $name = "index.pck.$i"
    $fs = [IO.File]::Create((Join-Path $out $name))
    $fs.Write($bytes, $i * $chunk, $len)
    $fs.Dispose()
    $parts += , @($name, $len)
}
Remove-Item $pck
$list = "[" + (($parts | ForEach-Object { '["{0}", {1}]' -f $_[0], $_[1] }) -join ", ") + "]"
$loader = (Get-Content (Join-Path $here "loader.js") -Raw).Replace("__VBD_PARTS__", $list)
$html = Get-Content (Join-Path $out "index.html") -Raw
$anchor = "const engine = new Engine(GODOT_CONFIG);"
if (-not $html.Contains($anchor) -or -not $html.Contains("engine.startGame(")) { throw "the page doesn't look like Godot's web template any more" }
$html = $html.Replace($anchor, $anchor + "`n" + $loader).Replace("engine.startGame(", "vbdStartGame(")
[IO.File]::WriteAllText((Join-Path $out "index.html"), $html)
Write-Host ("web build: {0} files, {1:N1} MB game data in {2} pieces" -f (Get-ChildItem $out).Count, ($bytes.Length / 1MB), $parts.Count)
if (-not $Upload) { return }

# --- publish
$gh = (Get-Command gh -ErrorAction SilentlyContinue).Source
if (-not $gh) { $gh = Join-Path $env:USERPROFILE ".vbd\gh\bin\gh.exe" }
if (-not $env:GH_CONFIG_DIR -and (Test-Path (Join-Path $env:USERPROFILE ".vbd\gh_config"))) { $env:GH_CONFIG_DIR = Join-Path $env:USERPROFILE ".vbd\gh_config" }
$repo = "NotCameronMitchell/VilliamBurginsonDorks"
$ErrorActionPreference = "Continue"
& $gh release view $Tag --repo $repo 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    & $gh release create $Tag --repo $repo --target main --prerelease --title "Web version files" `
        --notes "These files run the browser version at https://notcameronmitchell.github.io/VilliamBurginsonDorks/ (you don't need to download them)." | Out-Null
}
foreach ($f in Get-ChildItem $out -File) {
    for ($try = 1; $try -le 4; $try++) {  # big uploads from this PC sometimes drop: retry
        & $gh release upload $Tag $f.FullName --repo $repo --clobber 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { break }
        Write-Host "  retrying $($f.Name)"
    }
    if ($LASTEXITCODE -ne 0) { throw "couldn't upload $($f.Name)" }
}
& $gh workflow run web.yml --repo $repo -f tag=$Tag
Write-Host "uploaded; the Web version workflow is copying it to GitHub Pages"
