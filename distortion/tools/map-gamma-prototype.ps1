# Isolated device mapping only; no constraints, bitstream or hardware access.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\gamma_mapping'
if(Test-Path -LiteralPath (Join-Path $work 'gamma_mapping.pds')){throw 'Preserve existing Gamma mapping evidence'}
New-Item -ItemType Directory -Force -Path $work | Out-Null
$deps=@('rtl\experimental\adaptive_gamma_stream.v','rtl\experimental\gamma_curves.vh')
$hashes=@{};foreach($rel in $deps){$hashes[$rel]=(Get-FileHash -LiteralPath (Join-Path $root $rel)).Hash}
@{started_at=(Get-Date).ToString('o');source_sha256=$hashes} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $work 'start-proof.json') -Encoding utf8
$tcl=@'
add_design {D:/English/FPGA/distortion/rtl/experimental/adaptive_gamma_stream.v}
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
compile -force_to_run -top_module adaptive_gamma_stream
synthesize -force_to_run -ads -selected_syn_tool_opt 2
dev_map -force_to_run
'@
$path=Join-Path $work 'map.tcl';$tcl | Set-Content -LiteralPath $path -Encoding ascii
& (Join-Path $teamPdsBin 'pds_shell.exe') -file $path -work_dir $work -project_name gamma_mapping *> (Join-Path $work 'build.log')
$log=Get-Content -Raw (Join-Path $work 'build.log')
if($LASTEXITCODE -or $log -match '(?m)^E:' -or $log -notmatch '(?m)^Executing : dev_map\b[^\r\n]* successfully\.'){Get-Content (Join-Path $work 'build.log') -Tail 20;throw 'Gamma device map failed'}
foreach($rel in $deps){if((Get-FileHash -LiteralPath (Join-Path $root $rel)).Hash -ne $hashes[$rel]){throw 'Gamma source changed during map'}}
Write-Output 'PASS isolated Gamma synthesis/device mapping; no routed timing or hardware claim.'
