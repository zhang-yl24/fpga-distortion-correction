$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\short_burst_query_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
Push-Location $work
try {
    $files=@('rotated_remap_core','bounded_brown_inverse_mapper','pixel_inverse_rotation','mul32_pipe','ddr_remap_sample','bilinear_rgb') | ForEach-Object {Join-Path $root ('rtl\'+$_+'.v')}
    $files+=Join-Path $root 'rtl\experimental\ddr_short_burst_cache.v'
    $files+=Join-Path $root 'tests\tb_short_burst_query.sv'
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Composed query compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_short_burst_query -s tb_short_burst_query *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Composed query elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_short_burst_query -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS short burst composed rotation' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Composed query simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
