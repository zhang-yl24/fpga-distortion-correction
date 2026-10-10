$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\gamma_frozen_capture_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
$files=@('dvp_rgb565_capture','rgb565_burst_pack','video_async_fifo','camera_live_bridge','ddr_video_writer','ddr_uart_frame','bilinear_rgb','ddr_remap_sample','mul32_pipe','pixel_inverse_rotation','bounded_brown_inverse_mapper') | ForEach-Object {'rtl\'+$_+'.v'}
$files+=@('ddr_adaptive_cache','ddr_adaptive_result_writer','rotated_remap_core_gamma','adaptive_gamma_frame_engine','adaptive_gamma_tagged','adaptive_gamma_stream','gamma_frozen_capture') | ForEach-Object {'rtl\experimental\'+$_+'.v'}
$files+='tests\tb_gamma_frozen_capture.sv'
$deps=$files+@('rtl\experimental\gamma_curves.vh','rtl\video_crc32.vh','build\gamma_frozen_capture_sim\source.mem','build\gamma_frozen_capture_sim\result.mem','build\gamma_frozen_capture_sim\tone.mem','build\gamma_frozen_capture_sim\reference.json')
$hashes=@{}
foreach($f in $deps){
    $hashes[$f]=(Get-FileHash -LiteralPath (Join-Path $root $f)).Hash
    $dest=Join-Path $work ('source-snapshot\'+$f)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
    Copy-Item -LiteralPath (Join-Path $root $f) -Destination $dest
}
@{started_at=(Get-Date).ToString('o');source_sha256=$hashes} | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $work 'start-proof.json')
Push-Location $work
try{
    $paths=$files | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @paths *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 15;throw 'Frozen Gamma capture compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_gamma_frozen_capture -s tb_gamma_frozen_capture *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 15;throw 'Frozen Gamma capture elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_gamma_frozen_capture -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS frozen Gamma capture:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 15;throw 'Frozen Gamma capture simulation failed'}
    foreach($f in $deps){if((Get-FileHash -LiteralPath (Join-Path $root $f)).Hash -ne $hashes[$f]){throw 'Frozen Gamma capture dependency changed'}}
    $log -split "`r?`n" | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
