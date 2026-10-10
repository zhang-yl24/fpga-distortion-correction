$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\rotation_control_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
& 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'prepare-rotation-control-test.py')
if($LASTEXITCODE){throw 'Control references failed'}
Push-Location $work
try {
    $files=@('cordic_sincos','rotation_demo_control') | ForEach-Object {Join-Path $root ('rtl\'+$_+'.v')}
    $files+=Join-Path $root 'tests\tb_rotation_demo_control.sv'
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Control compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_rotation_demo_control -s tb_rotation_demo_control *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Control elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_rotation_demo_control -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS rotation control' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Control simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
