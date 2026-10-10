# Synthesis/device mapping only; no PNR, bitstream or hardware access.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\pipeline_hit_mapping'
if(Test-Path -LiteralPath (Join-Path $work 'pipeline_hit_mapping.pds')){throw 'Existing mapping run retained; choose a new isolated directory rather than overwrite evidence'}
New-Item -ItemType Directory -Force -Path $work | Out-Null
$text=Get-Content -Raw -LiteralPath (Join-Path $root 'board\build-corrected_pipeline_hit.tcl')
$text=$text.Substring(0,$text.IndexOf('pnr -force_to_run'))
$tcl=Join-Path $work 'map-only.tcl'
$text | Set-Content -LiteralPath $tcl -Encoding ascii
$deps=Get-Content -Raw (Join-Path $root 'board\corrected_pipeline_hit-sources.json') | ConvertFrom-Json
$hashes=@{}
foreach($src in $deps){$hashes[$src]=(Get-FileHash -LiteralPath (Join-Path $root $src)).Hash}
$started=Get-Date
[pscustomobject]@{Started=$started.ToString('o');SourceSHA256=$hashes} | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $work 'mapping-run-start.json') -Encoding utf8
& (Join-Path $teamPdsBin 'pds_shell.exe') -file $tcl -work_dir $work -project_name pipeline_hit_mapping *> (Join-Path $work 'build.log')
$log=Get-Content -Raw (Join-Path $work 'build.log')
if($LASTEXITCODE -or $log -match '(?m)^E:' -or $log -notmatch '(?m)^Executing : dev_map\b[^\r\n]* successfully\.'){Get-Content (Join-Path $work 'build.log') -Tail 25;throw 'Pipeline board map failed'}
foreach($src in $deps){if($hashes[$src] -ne (Get-FileHash -LiteralPath (Join-Path $root $src)).Hash){throw "Source changed during mapping: $src"}}
foreach($name in @('synthesize\corrected_pipeline_hit_syn.adf','device_map\corrected_pipeline_hit_map.adf')){
    if((Get-Item (Join-Path $work $name)).LastWriteTime -lt $started){throw 'Mapping flow DB was stale'}
}
[pscustomobject]@{Passed=$true;HardwareAccessed=$false;Started=$started.ToString('o');Finished=(Get-Date).ToString('o');Top='corrected_pipeline_hit';Device='PG2L100H';Package='FBG676';SourceSHA256=$hashes;Limits='Synthesis/device mapping only; no routed timing, bitstream or physical FPS proof.'} |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $work 'mapping-proof.json') -Encoding utf8
Get-Content (Join-Path $work 'build.log') -Tail 12
