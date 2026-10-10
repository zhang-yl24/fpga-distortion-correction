$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\temperature_monitor_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
& 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'prepare-temperature-monitor-test.py')
if($LASTEXITCODE){throw 'Temperature wrapper fixture failed'}
Push-Location $work
try {
    $files=@((Join-Path $work 'digital-adc-stub.sv'),(Join-Path $root 'rtl\adc_temperature_reader.v'),(Join-Path $root 'rtl\logos2_temperature_monitor.v'),(Join-Path $root 'tests\tb_logos2_temperature_monitor.sv'))
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Temperature wrapper compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_logos2_temperature_monitor -s tb_logos2_temperature_monitor *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Temperature wrapper elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_logos2_temperature_monitor -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS temperature wrapper' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Temperature wrapper simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
