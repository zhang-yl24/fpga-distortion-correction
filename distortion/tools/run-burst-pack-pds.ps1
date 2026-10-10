$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\burst_pack_pds'
New-Item -ItemType Directory -Force $work | Out-Null
$logFile=Join-Path $work 'build.log'
& (Join-Path $teamPdsBin 'pds_shell.exe') -file (Join-Path $root 'board\synthesize-burst-pack.tcl') -work_dir $work -project_name burst_pack *> $logFile
$code=$LASTEXITCODE
$log=Get-Content -Raw $logFile
if($code -ne 0 -or $log -match '(?m)^E:' -or $log -notmatch '(?m)^Executing : dev_map[^\r\n]* successfully\.') {
    Get-Content $logFile -Tail 18
    throw 'Burst pack device mapping failed'
}
Write-Output 'PASS burst_pack PG2L100H FBG676 device map with internal 256-bit bus; no bitstream generated.'
