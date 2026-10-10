$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\uart_frame_sim'
$bin=$teamVivadoBin
& $teamPython (Join-Path $PSScriptRoot 'generate-uart-frame-test.py')
if($LASTEXITCODE){throw 'UART golden generation failed'}
Push-Location $work
try {
    $files=@('rtl\uart_tx.v','rtl\ddr_uart_frame.v','tests\tb_ddr_uart_frame.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'UART frame compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_ddr_uart_frame -s tb_ddr_uart_frame *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'UART frame elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_ddr_uart_frame -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'UART frame simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
