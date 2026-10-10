$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\brown_remap_probe'
New-Item -ItemType Directory -Force $work | Out-Null
& (Join-Path $teamPdsBin 'pds_shell.exe') -file (Join-Path $root 'board\route-brown-remap-probe.tcl') -work_dir $work -project_name brown_remap_probe *> (Join-Path $work 'build.log')
$log=Get-Content -Raw (Join-Path $work 'build.log')
if($LASTEXITCODE -or $log -match '(?m)^E:' -or $log -notmatch 'Executing : report_timing.*successfully'){Get-Content (Join-Path $work 'build.log') -Tail 24;throw 'Brown remap timing probe failed'}
$timing=Get-Content -Raw (Join-Path $work 'place_route\brown_remap_synthesis_top_timing_summary_after_hold_fix.txt')
if($timing -notmatch 'All Constraints Met'){Write-Output $timing;throw '125MHz standalone Brown remap timing failed'}
Write-Output 'PASS standalone Brown remap core 125MHz timing. No board bitstream generated; actual board integration still required.'
($timing -split "`r?`n") | Select-Object -First 17
