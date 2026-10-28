param([string]$OutputDirectory='')
# Digital xsim only; no COM, JTAG, PDS build or programming.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$approved=[System.IO.Path]::GetFullPath((Join-Path $root 'build\offline-20261024'))
if(!$OutputDirectory){$OutputDirectory=Join-Path $approved ('guarded-command-sim-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))}
$work=[System.IO.Path]::GetFullPath($OutputDirectory)
if(!(Test-Path -LiteralPath $approved) -or !$work.StartsWith($approved+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $work)){throw 'Use fresh output below approved scratch'}
New-Item -ItemType Directory -Path $work | Out-Null
$names=@('rtl\guarded_command_engine.v','rtl\guarded_capture_controller.v','rtl\guarded_status_uart.v','rtl\guarded_uart_arbiter.v',
    'rtl\raw_capture_lease.v','rtl\raw_camera_capture_guarded.v','rtl\raw_camera_capture.v','rtl\camera_live_bridge.v',
    'rtl\dvp_rgb565_capture.v','rtl\rgb565_burst_pack.v','rtl\video_async_fifo.v','rtl\ddr_video_writer.v','rtl\ddr_uart_frame.v',
    'rtl\video_crc32.vh','tests\tb_guarded_command_engine.sv','tests\tb_guarded_counter.sv','tools\run-guarded-command-sim.ps1')
$hashes=@{};foreach($name in $names){$hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash}
$report=[ordered]@{Passed=$false;HardwareAccessed=$false;SourceSHA256=$hashes;OutputDirectory=$work;
    Limits='RTL digital tests only; accelerated parser/feedback timeouts and forced completion events do not establish physical timing, ADC safety, camera identity or unattended acceptance.'}
Push-Location $work
try{
    $files=$names | Where-Object {$_ -match '\.(v|sv)$'} | ForEach-Object {Join-Path $root $_}
    & (Join-Path $teamVivadoBin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 25;throw 'Guarded command compile failed'}
    foreach($top in @('tb_guarded_command_engine','tb_guarded_counter')){
        & (Join-Path $teamVivadoBin 'xelab.bat') $top -s $top *> ($top+'-elab.log')
        if($LASTEXITCODE){Get-Content ($top+'-elab.log') -Tail 25;throw 'Guarded command elaboration failed'}
        & (Join-Path $teamVivadoBin 'xsim.bat') $top -runall -log ($top+'-simulation.log') *> ($top+'-run.log')
        $log=Get-Content -Raw ($top+'-simulation.log')
        if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content ($top+'-simulation.log') -Tail 30;throw 'Guarded command/counter regression failed'}
        ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
    }
    foreach($name in $names){if((Get-FileHash -LiteralPath (Join-Path $root $name)).Hash -ne $hashes[$name]){throw 'Source changed during regression'}}
    $report.Passed=$true;$report.LogSHA256=@{}
    foreach($path in Get-ChildItem -Filter '*-simulation.log'){$report.LogSHA256[$path.Name]=(Get-FileHash -LiteralPath $path.FullName).Hash}
}finally{
    $report | ConvertTo-Json -Depth 7 | Set-Content -Encoding utf8 -LiteralPath (Join-Path $work 'guarded-command-simulation.json')
    Pop-Location
}
Write-Output ('Guarded command simulation evidence: '+(Join-Path $work 'guarded-command-simulation.json'))
