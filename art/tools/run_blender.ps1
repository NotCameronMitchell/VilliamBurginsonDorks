# Runs make_models.py in Blender (headless) and waits for it to finish.
#   powershell -File art/tools/run_blender.ps1 [-- make_models options]
# Finds Blender from the BLENDER env var, PATH, or the Microsoft Store install.
param([Parameter(ValueFromRemainingArguments = $true)] $Rest)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $here "make_models.py"
$log = Join-Path $env:TEMP "vbd_make_models.log"
if (Test-Path $log) { Remove-Item $log }

$blender = $env:BLENDER
if (-not $blender) { $c = Get-Command blender -ErrorAction SilentlyContinue; if ($c) { $blender = $c.Source } }
if (-not $blender) {
    $launcher = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\blender-launcher.exe"
    if (Test-Path $launcher) { $blender = $launcher }
}
if (-not $blender) { Write-Error "Blender not found. Install it or set `$env:BLENDER to blender.exe."; exit 1 }

$argList = @("--factory-startup", "-b", "-P", "`"$script`"", "--", "--log", "`"$log`"")
if ($Rest) { $argList += @($Rest | Where-Object { $_ -ne $null }) }
$before = @(Get-Process blender -ErrorAction SilentlyContinue | ForEach-Object Id)
Start-Process -FilePath $blender -ArgumentList $argList -WindowStyle Hidden -Wait
# The Store launcher returns right away; wait for the real blender.exe it started.
Start-Sleep -Seconds 2
$procs = @(Get-Process blender -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id })
if ($procs.Count -gt 0) { $procs | Wait-Process }
if (Test-Path $log) { Get-Content $log } else { Write-Error "No log written (Blender didn't run the script)."; exit 1 }
