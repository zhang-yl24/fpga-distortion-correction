$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\adc_reader_sim'
$bin=$teamVivadoBin
New-Item -ItemType Directory -Force -Path $work | Out-Null
Push-Location $work
try {
    & (Join-Path $bin 'xvlog.bat') --sv (Join-Path $root 'rtl\adc_temperature_reader.v') (Join-Path $root 'tests\tb_adc_temperature_reader.sv') *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'ADC adapter compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_adc_temperature_reader -s tb_adc_temperature_reader *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'ADC adapter elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_adc_temperature_reader -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ADC readback' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'ADC adapter regression failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
