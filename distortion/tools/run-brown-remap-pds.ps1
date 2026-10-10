$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\brown_remap_pds'
New-Item -ItemType Directory -Force $work | Out-Null
& (Join-Path $teamPdsBin 'pds_shell.exe') -file (Join-Path $root 'board\synthesize-brown-remap.tcl') -work_dir $work -project_name brown_remap *> (Join-Path $work 'build.log')
$log=Get-Content -Raw (Join-Path $work 'build.log')
if($LASTEXITCODE -or $log -match '(?m)^E:' -or $log -notmatch 'Executing : dev_map.*successfully'){Get-Content (Join-Path $work 'build.log') -Tail 24;throw 'Brown remap device mapping failed'}
Get-Content (Join-Path $work 'device_map\brown_remap_synthesis_top.dmr') | Select-String 'Device Utilization Summary:' -Context 0,12
