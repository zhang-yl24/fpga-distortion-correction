$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\host_control_sim'
$bin=$teamVivadoBin
Push-Location $work
try {
    $files=@('uart_rx_control','rotation_command_parser','rotation_host_control') | ForEach-Object {Join-Path $root ('rtl\experimental\'+$_+'.v')}
    $files+=Join-Path $root 'rtl\cordic_sincos.v'
    $files+=Join-Path $root 'tests\tb_host_control.sv'
    $files+=Join-Path $root 'tests\tb_host_control_concurrent.sv'
    $bound=$files+@(Get-ChildItem $work -File | Where-Object {$_.Extension -eq '.mem' -or $_.Name -in @('counts.vh','reference.json')} | ForEach-Object {$_.FullName})
    $hashes=[ordered]@{}
    foreach($file in $bound){$hashes[$file.Substring($root.Length+1).Replace('\','/')]=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash}
    @{started_at=(Get-Date).ToString('o');source_sha256=$hashes} | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 start-proof.json
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 15;throw 'Host control compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_host_control -s tb_host_control *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 15;throw 'Host control elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_host_control -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS host control:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 15;throw 'Host control simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
    foreach($file in $bound){$rel=$file.Substring($root.Length+1).Replace('\','/');if((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $hashes[$rel]){throw "Simulation dependency changed: $rel"}}
    & (Join-Path $bin 'xelab.bat') tb_host_control_concurrent -s tb_host_control_concurrent *> concurrent-elab.log
    if($LASTEXITCODE){throw 'Concurrent control elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_host_control_concurrent -runall -log concurrent-simulation.log *> concurrent-run.log
    $log=Get-Content -Raw concurrent-simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS concurrent host control:' -or $log -match '(?im)fatal:|error:'){Get-Content concurrent-simulation.log -Tail 15;throw 'Concurrent host control simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
