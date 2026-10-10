$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\pipeline_parity_stream_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
New-Item -ItemType Directory -Force -Path $work | Out-Null
Push-Location $work
try {
    $files=@('ddr_pipeline_parity_cache','ddr_pipeline_serial_cache') | ForEach-Object {Join-Path $root ('rtl\experimental\'+$_+'.v')}
    $files+=Join-Path $root 'tests\tb_pipeline_hit_stream.sv'
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Hit stream compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_pipeline_hit_stream -s tb_pipeline_hit_stream *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Hit stream elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_pipeline_hit_stream -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS pipeline hit stream:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Hit stream simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS |^INFO '}
}finally{Pop-Location}
