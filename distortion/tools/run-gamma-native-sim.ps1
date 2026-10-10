$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\gamma_native_sim'
$bin=$teamVivadoBin
$files=@('bilinear_rgb','ddr_remap_sample','mul32_pipe','pixel_inverse_rotation','bounded_brown_inverse_mapper') | ForEach-Object {'rtl\'+$_+'.v'}
$files+=@('ddr_adaptive_cache','ddr_adaptive_result_writer','rotated_remap_core_gamma','adaptive_gamma_frame_engine','adaptive_gamma_tagged','adaptive_gamma_stream') | ForEach-Object {'rtl\experimental\'+$_+'.v'}
$files+='tests\tb_gamma_native.sv'
$deps=$files+@('rtl\experimental\gamma_curves.vh','rtl\video_crc32.vh','board\calibration-trial.vh','board\rotation-domain.vh','build\gamma_native_sim\source.mem','build\gamma_native_sim\result.mem','build\gamma_native_sim\masks.mem','build\gamma_native_sim\modes.mem','build\gamma_native_sim\rotations.mem','build\gamma_native_sim\crcs.mem','build\gamma_native_sim\reference.json')
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
    if($LASTEXITCODE){Get-Content compile.log -Tail 15;throw 'Gamma frame compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_gamma_native -s tb_gamma_native *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 15;throw 'Gamma frame elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_gamma_native -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS Gamma native regression:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 15;throw 'Gamma frame simulation failed'}
    foreach($f in $deps){if((Get-FileHash -LiteralPath (Join-Path $root $f)).Hash -ne $hashes[$f]){throw 'Gamma frame dependency changed'}}
    $log -split "`r?`n" | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
