$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\remap_pds'
New-Item -ItemType Directory -Force $work | Out-Null
& (Join-Path $teamPdsBin 'pds_shell.exe') -file (Join-Path $root 'board\synthesize-remap.tcl') -work_dir $work -project_name remap *> (Join-Path $work 'build.log')
$log=Get-Content -Raw (Join-Path $work 'build.log')
if($LASTEXITCODE -or $log -match '(?m)^E:' -or $log -notmatch 'Executing : dev_map.*successfully'){Get-Content (Join-Path $work 'build.log') -Tail 24;throw 'Remap device mapping failed'}
($log -split "`r?`n") | Where-Object {$_ -match 'Use of (DRM|LUT|REG|APM)|dev_map.*successfully'}
