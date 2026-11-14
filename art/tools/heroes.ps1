# Runs a step of the detailed-hero pipeline with the right program.
#   powershell -File art/tools/heroes.ps1 prompts                    print each hero's Gemini prompts
#   powershell -File art/tools/heroes.ps1 motions  [options]         Kimodo motions (kimodo_batch.py)
#   powershell -File art/tools/heroes.ps1 assemble [options]         rig + animate + export (hero_assemble.py, Blender)
#   powershell -File art/tools/heroes.ps1 meshy    <command> [opts]  the optional paid Meshy route (meshy.py)
# Kimodo lives in $env:KIMODO_HOME (default: %LOCALAPPDATA%\VilliamBurginsonDorks\kimodo).
# Blender comes from $env:BLENDER, PATH, or the Microsoft Store install.
# (No param block: an advanced script would read "--out" as PowerShell's own -OutVariable.)
$Step = if ($args.Count -gt 0) { "$($args[0])" } else { "" }
$args2 = @(if ($args.Count -gt 1) { $args[1..($args.Count - 1)] | ForEach-Object { "$_" } })

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$kimodo = if ($env:KIMODO_HOME) { $env:KIMODO_HOME } else { Join-Path $env:LOCALAPPDATA "VilliamBurginsonDorks\kimodo" }
$py = Join-Path $kimodo ".venv\Scripts\python.exe"

function Need-Python {
    if (-not (Test-Path $py)) { Write-Error "Kimodo's Python isn't at $py. See docs/ART_PIPELINE.md (Detailed heroes)."; exit 1 }
}

switch ($Step) {
    "prompts" { Need-Python; & $py (Join-Path $here "hero_specs.py") @args2; exit $LASTEXITCODE }
    "motions" { Need-Python; & $py (Join-Path $here "kimodo_batch.py") @args2; exit $LASTEXITCODE }
    "meshy" { Need-Python; & $py (Join-Path $here "meshy.py") @args2; exit $LASTEXITCODE }
    "assemble" {
        $script = Join-Path $here "hero_assemble.py"
        $log = Join-Path $env:TEMP "vbd_heroes.log"
        if (Test-Path $log) { Remove-Item $log }
        $blender = $env:BLENDER
        if (-not $blender) { $c = Get-Command blender -ErrorAction SilentlyContinue; if ($c) { $blender = $c.Source } }
        if (-not $blender) {
            $launcher = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\blender-launcher.exe"
            if (Test-Path $launcher) { $blender = $launcher }
        }
        if (-not $blender) { Write-Error "Blender not found. Install it or set `$env:BLENDER to blender.exe."; exit 1 }
        $argList = @("--factory-startup", "-b", "-P", "`"$script`"", "--", "--log", "`"$log`"")
        foreach ($a in $args2) { $argList += $(if ($a -match '\s') { "`"$a`"" } else { $a }) }
        $before = @(Get-Process blender -ErrorAction SilentlyContinue | ForEach-Object Id)
        Start-Process -FilePath $blender -ArgumentList $argList -WindowStyle Hidden -Wait
        # The Store launcher returns right away; wait for the real blender.exe it started.
        Start-Sleep -Seconds 2
        $procs = @(Get-Process blender -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id })
        if ($procs.Count -gt 0) { $procs | Wait-Process }
        if (Test-Path $log) { Get-Content $log } else { Write-Error "No log written (Blender didn't run the script)."; exit 1 }
    }
    default {
        Write-Host "Usage: heroes.ps1 prompts | motions [--only a,b] | assemble [--only a,b] [--mannequin] [--render DIR] | meshy <command>"
        exit 1
    }
}
