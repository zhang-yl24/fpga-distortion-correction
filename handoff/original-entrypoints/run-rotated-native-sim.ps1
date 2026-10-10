$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\rotated_native_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
& 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'prepare-rotated-native-test.py')
if($LASTEXITCODE){throw 'Rotated real-frame oracle failed'}
Push-Location $work
try {
    $files=@('bilinear_rgb','ddr_remap_sample','mul32_pipe','pixel_inverse_rotation','bounded_brown_inverse_mapper','rotated_remap_core','ddr_result_writer','rotated_frame_engine') | ForEach-Object {Join-Path $root ('rtl\'+$_+'.v')}
    $files+=Join-Path $root 'rtl\experimental\ddr_neighbour_cache_fast.v'
    $files+=Join-Path $root 'tests\tb_rotated_native_regression.sv'
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Rotated native compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_rotated_native_regression -s tb_rotated_native_regression *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Rotated native elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_rotated_native_regression -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS rotated native regression:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Rotated native regression failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
