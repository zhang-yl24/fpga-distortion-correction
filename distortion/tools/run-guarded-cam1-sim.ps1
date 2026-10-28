param([string]$OutputDirectory='')
# CAM1 identity parameterization of the successful shared digital pipeline.
# No COM/JTAG/configuration server/programmer or physical device operation.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$approved=[System.IO.Path]::GetFullPath((Join-Path $root 'build\offline-20261024'))
if(!(Test-Path -LiteralPath $approved -PathType Container)){throw 'Approved scratch root must exist'}
& $teamPython (Join-Path $PSScriptRoot 'prepare_guarded_cam1.py')
if($LASTEXITCODE){throw 'CAM1 clone/source inheritance validation failed'}
if(!$OutputDirectory){$OutputDirectory=Join-Path $approved ('guarded-cam1-sim-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))}
$work=[System.IO.Path]::GetFullPath($OutputDirectory)
if(!$work.StartsWith($approved+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $work)){throw 'Use fresh output below approved scratch'}
$names=@('rtl\raw_capture_lease.v','rtl\raw_camera_capture_guarded.v','rtl\raw_camera_capture.v',
    'rtl\guarded_temperature_cdc.v','rtl\guarded_status_uart.v','rtl\guarded_uart_arbiter.v',
    'rtl\guarded_capture_controller.v','rtl\guarded_command_engine.v','rtl\experimental\uart_rx_control.v',
    'rtl\logos2_temperature_monitor.v','rtl\adc_temperature_reader.v','rtl\uart_tx.v',
    'rtl\camera_live_bridge.v','rtl\dvp_rgb565_capture.v','rtl\rgb565_burst_pack.v',
    'rtl\video_async_fifo.v','rtl\ddr_video_writer.v','rtl\ddr_uart_frame.v','rtl\video_crc32.vh',
    'tests\tb_guarded_cam1_pipeline.sv','board\raw_camera_capture_cam1_guarded.v',
    'tools\run-guarded-cam1-sim.ps1','tools\prepare_guarded_cam1.py')
$hashes=@{};foreach($name in $names){$hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash}
$prepared=Join-Path $root 'board\raw_camera_capture_cam1_guarded-sources.json'
$preparedSHA=(Get-FileHash -LiteralPath $prepared).Hash
New-Item -ItemType Directory -Path $work | Out-Null
$report=[ordered]@{Passed=$false;Target='raw_camera_capture_cam1_guarded';HardwareAccessed=$false;PDSAccessed=$false;
    BuildTag=0x52473101;CameraID=0x43414d31;CameraSlot=1;SourceSHA256=$hashes;
    PreparedSourceManifestSHA256=$preparedSHA;OutputDirectory=$work;ImageSize=@(32,16);
    RegressionTops=@('tb_guarded_cam1_pipeline');
    Limits='Digital CAM1 tag/ID/slot variant test of inherited mixed pipeline. Accelerated clocks and deterministic DDR/UART sink; no physical-eye, electrical, synchronization, optics, actual temperature, hardware or unattended acceptance.'}
Push-Location $work
try{
    $files=$names | Where-Object {$_ -match '\.(v|sv)$' -and $_ -notmatch '^board\\'} | ForEach-Object {Join-Path $root $_}
    & (Join-Path $teamVivadoBin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 30;throw 'CAM1 pipeline compile failed'}
    $top='tb_guarded_cam1_pipeline'
    & (Join-Path $teamVivadoBin 'xelab.bat') $top -s $top *> elaboration.log
    if($LASTEXITCODE){Get-Content elaboration.log -Tail 30;throw 'CAM1 pipeline elaboration failed'}
    & (Join-Path $teamVivadoBin 'xsim.bat') $top -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 30;throw 'CAM1 digital pipeline failed'}
    foreach($name in $names){if((Get-FileHash -LiteralPath (Join-Path $root $name)).Hash -ne $hashes[$name]){throw 'Source changed during CAM1 simulation'}}
    if((Get-FileHash -LiteralPath $prepared).Hash -ne $preparedSHA){throw 'Prepared CAM1 manifest changed during simulation'}
    $report.Passed=$true;$report.LogSHA256=(Get-FileHash -LiteralPath simulation.log).Hash
    $report.MixedStream=Join-Path $work 'guarded-cam1-mixed-stream.bin'
    $report.MixedStreamSHA256=(Get-FileHash -LiteralPath $report.MixedStream).Hash
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'guarded-cam1-simulation.json') -Encoding utf8
    Pop-Location
}
Write-Output ('CAM1 simulation evidence: '+(Join-Path $work 'guarded-cam1-simulation.json'))
