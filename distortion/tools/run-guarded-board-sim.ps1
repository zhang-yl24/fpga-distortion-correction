param([string]$OutputDirectory='',[switch]$IntegrationOnly)
# Digital simulation only. Never opens COM/JTAG or executes a programmer.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$approved=[System.IO.Path]::GetFullPath((Join-Path $root 'build\offline-20261024'))
if(!(Test-Path -LiteralPath $approved -PathType Container)){throw 'Approved scratch root must exist'}
if(!$OutputDirectory){$OutputDirectory=Join-Path $approved ('guarded-board-sim-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))}
$work=[System.IO.Path]::GetFullPath($OutputDirectory)
if(!$work.StartsWith($approved+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $work)){throw 'Use fresh output below approved scratch'}
New-Item -ItemType Directory -Path $work | Out-Null
$names=@('rtl\raw_capture_lease.v','rtl\raw_camera_capture_guarded.v','rtl\raw_camera_capture.v',
    'rtl\guarded_temperature_cdc.v','rtl\guarded_status_uart.v','rtl\guarded_uart_arbiter.v',
    'rtl\guarded_capture_controller.v','rtl\guarded_command_engine.v','rtl\experimental\uart_rx_control.v',
    'rtl\logos2_temperature_monitor.v','rtl\adc_temperature_reader.v','rtl\uart_tx.v',
    'rtl\camera_live_bridge.v','rtl\dvp_rgb565_capture.v','rtl\rgb565_burst_pack.v',
    'rtl\video_async_fifo.v','rtl\ddr_video_writer.v','rtl\ddr_uart_frame.v','rtl\video_crc32.vh',
    'tests\tb_raw_capture_lease.sv','tests\tb_guarded_raw_camera_capture.sv',
    'tests\tb_guarded_temperature_cdc.sv','tests\tb_guarded_status_uart.sv','tests\tb_guarded_board_pipeline.sv',
    'board\raw_camera_capture_cam2_guarded.v','tools\run-guarded-board-sim.ps1')
$hashes=@{};foreach($name in $names){$hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash}
$baseline=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'board\raw_camera_capture_cam2_ref-sources.json') | ConvertFrom-Json
foreach($entry in $baseline.SourceSHA256.PSObject.Properties){
    if((Get-FileHash -LiteralPath (Join-Path $root $entry.Name)).Hash -ne $entry.Value){throw 'Original raw97 source changed'}
}
$report=[ordered]@{Passed=$false;HardwareAccessed=$false;PDSAccessed=$false;SourceSHA256=$hashes;
    OriginalRaw97SourceBindingPreserved=$true;OutputDirectory=$work;ImageSize=@(32,16);SourceTemperatureClockHaltTested=$true;
    Limits='Digital RTL simulation only, accelerated clocks/timeouts and deterministic DDR/UART sink. Does not establish physical ADC accuracy, actual thermal safety, hardware clock continuity or unattended acceptance.'}
Push-Location $work
try{
    $files=$names | Where-Object {$_ -match '\.(v|sv)$' -and $_ -notmatch '^board\\'} | ForEach-Object {Join-Path $root $_}
    & (Join-Path $teamVivadoBin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 30;throw 'Guarded board compile failed'}
    $tops=if($IntegrationOnly){@('tb_guarded_board_pipeline')}else{@('tb_raw_capture_lease','tb_guarded_raw_camera_capture','tb_guarded_temperature_cdc','tb_guarded_status_uart','tb_guarded_board_pipeline')}
    $report.RegressionTops=@($tops)
    foreach($top in $tops){
        & (Join-Path $teamVivadoBin 'xelab.bat') $top -s $top *> ($top+'-elab.log')
        if($LASTEXITCODE){Get-Content ($top+'-elab.log') -Tail 30;throw ('Elaboration failed: '+$top)}
        & (Join-Path $teamVivadoBin 'xsim.bat') $top -runall -log ($top+'-simulation.log') *> ($top+'-run.log')
        $log=Get-Content -Raw ($top+'-simulation.log')
        if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){
            Get-Content ($top+'-simulation.log') -Tail 35;throw ('Guarded regression failed: '+$top)
        }
        ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
    }
    foreach($name in $names){if((Get-FileHash -LiteralPath (Join-Path $root $name)).Hash -ne $hashes[$name]){throw 'Source changed during simulation'}}
    $report.Passed=$true;$report.LogSHA256=@{}
    foreach($logFile in Get-ChildItem -Filter '*-simulation.log'){$report.LogSHA256[$logFile.Name]=(Get-FileHash -LiteralPath $logFile.FullName).Hash}
    $report.MixedStream=Join-Path $work 'guarded-board-mixed-stream.bin'
    $report.MixedStreamSHA256=(Get-FileHash -LiteralPath $report.MixedStream).Hash
}finally{
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'guarded-board-simulation.json') -Encoding utf8
    Pop-Location
}
Write-Output ('Guarded simulation evidence: '+(Join-Path $work 'guarded-board-simulation.json'))
