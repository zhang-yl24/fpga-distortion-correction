$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\rotated_query_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
& 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'prepare-rotated-query-test.py')
if($LASTEXITCODE){throw 'Composed query references failed'}
Push-Location $work
try {
    $files=@('rotated_remap_core','bounded_brown_inverse_mapper','pixel_inverse_rotation','mul32_pipe','ddr_remap_sample','bilinear_rgb') | ForEach-Object {Join-Path $root ('rtl\'+$_+'.v')}
    $files+=Join-Path $root 'rtl\experimental\ddr_neighbour_cache_fast.v'
    $files+=Join-Path $root 'tests\tb_rotated_ddr_remap.sv'
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Composed query compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_rotated_ddr_remap -s tb_rotated_ddr_remap *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Composed query elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_rotated_ddr_remap -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS composed rotation' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Composed query simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
