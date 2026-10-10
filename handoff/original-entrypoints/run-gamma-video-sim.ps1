$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\gamma_video_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
Push-Location $work
try {
    $files=@('dvp_rgb565_capture','video_async_fifo','ddr_video_writer','ddr_video_reader','ddr_video_output','ddr_read_arbiter','ddr_write_arbiter','bounded_brown_inverse_mapper','pixel_inverse_rotation','mul32_pipe','ddr_remap_sample','bilinear_rgb') | ForEach-Object {Join-Path $root ('rtl\'+$_+'.v')}
    $files+=@('ddr_adaptive_cache','ddr_adaptive_result_writer','rgb565_burst_pack_early','camera_live_bridge_early','ddr_gamma_video','rotated_remap_core_gamma','adaptive_gamma_frame_engine','adaptive_gamma_stream','adaptive_gamma_tagged') | ForEach-Object {Join-Path $root ('rtl\experimental\'+$_+'.v')}
    $files+=Join-Path $root 'tests\tb_ddr_gamma_video.sv'
    $deps=$files+@((Join-Path $root 'rtl\video_crc32.vh'),(Join-Path $root 'rtl\experimental\gamma_curves.vh'))+(Get-ChildItem -LiteralPath $work -Filter '*.mem' | ForEach-Object {$_.FullName})
    $hashes=@{}
    foreach($f in $deps){
        $rel=$f.Substring($root.Length+1);$hashes[$rel]=(Get-FileHash -LiteralPath $f).Hash
        $dest=Join-Path $work ('source-snapshot\'+$rel)
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
        Copy-Item -LiteralPath $f -Destination $dest
    }
    @{started_at=(Get-Date).ToString('o');source_sha256=$hashes} | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 start-proof.json
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Rotated video compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_ddr_gamma_video -s tb_ddr_gamma_video *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Rotated video elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_ddr_gamma_video -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS Gamma bypass DDR video:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Rotated video simulation failed'}
    foreach($f in $deps){if((Get-FileHash -LiteralPath $f).Hash -ne $hashes[$f.Substring($root.Length+1)]){throw 'Gamma video source changed'}}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
