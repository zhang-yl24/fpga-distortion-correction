param([string]$OutputDirectory='',[ValidateRange(1,10)][int]$MaximumMinutes=5)
# Offline only: complete SCCB68 register bus and inherited guarded pipeline.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$approved=[System.IO.Path]::GetFullPath((Join-Path $root 'build\offline-20261024'))
if(!(Test-Path -LiteralPath $approved -PathType Container)){throw 'Approved scratch root must exist'}
$oldBytecode=$env:PYTHONDONTWRITEBYTECODE;$env:PYTHONDONTWRITEBYTECODE='1'
try{& $teamPython (Join-Path $PSScriptRoot 'prepare_guarded_cam1_isolated.py');$factoryExit=$LASTEXITCODE}finally{$env:PYTHONDONTWRITEBYTECODE=$oldBytecode}
if($factoryExit){throw 'Exact SCCB trial clone/source validation failed'}
if(!$OutputDirectory){$OutputDirectory=Join-Path $approved ('cam1-isolated-sim-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))}
$work=[System.IO.Path]::GetFullPath($OutputDirectory)
if(!$work.StartsWith($approved+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $work)){throw 'Use fresh output below approved scratch'}
New-Item -ItemType Directory -Path $work | Out-Null
$names=@('rtl/raw_capture_lease.v','rtl/raw_camera_capture_guarded.v','rtl/raw_camera_capture.v',
    'rtl/guarded_temperature_cdc.v','rtl/guarded_status_uart.v','rtl/guarded_uart_arbiter.v',
    'rtl/guarded_capture_controller.v','rtl/guarded_command_engine.v','rtl/experimental/uart_rx_control.v',
    'rtl/logos2_temperature_monitor.v','rtl/adc_temperature_reader.v','rtl/uart_tx.v',
    'rtl/camera_live_bridge.v','rtl/dvp_rgb565_capture.v','rtl/rgb565_burst_pack.v',
    'rtl/video_async_fifo.v','rtl/ddr_video_writer.v','rtl/ddr_uart_frame.v','rtl/video_crc32.vh',
    'rtl/reg16_i2c.v','rtl/experimental/ov5640_cadence_trial_init.v','rtl/experimental/capture_warmup.v','rtl/camera_preview.v','rtl/video_pattern.v','board/hdmi_tx_init.v','board/ov5640_cadence_trial_commands.vh',
    'tests/tb_cam1_isolated_init.sv','tests/cam1_isolated_board_stubs.v','tests/tb_guarded_cam1_isolated_pipeline.sv',
    'board/raw_camera_capture_cam1_guarded_isolated.v','tools/prepare_guarded_cam1_isolated.py',
    'tools/prepare_guarded_cam1.py','tools/run-guarded-cam1-isolated-sim.ps1')
$hashes=@{};foreach($name in $names){$hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash}
$preparedPath=Join-Path $root 'board/raw_camera_capture_cam1_guarded_isolated-sources.json'
$prepared=Get-Content -LiteralPath $preparedPath -Raw -Encoding UTF8 | ConvertFrom-Json
$preparedSHA=(Get-FileHash -LiteralPath $preparedPath).Hash
$started=[DateTime]::UtcNow
$tops=@('tb_cam1_isolated_init','tb_guarded_cam1_isolated_pipeline')
$report=[ordered]@{Passed=$false;Target='raw_camera_capture_cam1_guarded_isolated';HardwareAccessed=$false;PDSAccessed=$false;
    SourceSHA256=$hashes;SourceSHA256After=@{};PreparedSourceManifestSHA256=$preparedSHA;
    OtherSensorResetTrialContract=$prepared.OtherSensorResetTrialContract;OutputDirectory=$work;RegressionTops=$tops;
    Limits='Digital SCCB waveform/initialization and 32x16 guarded packet tests only. Actual top constant-sink lifecycle with inert vendor DDR/PLL/ADC stubs, complete7FF0/default68 and all readback faults retained; separate real guarded digital pipeline. No measured physical SCCB timing, electrical diagnosis, CAM1 real frames, stereo, optics or hardware-fix acceptance.'}
function Invoke-OwnedSimulationTool([string]$Name,[string[]]$ToolArguments,[string]$LogStem){
    $tool=Join-Path $teamVivadoBin $Name
    foreach($token in (@($tool)+$ToolArguments)){
        if($token -match '["\r\n&|<>^%!]' ){throw 'Unsupported shell metacharacter in a fixed simulation argument'}
    }
    $command=(@('"'+$tool+'"')+@($ToolArguments | ForEach-Object {'"'+$_+'"'})) -join ' '
    $owned=$null
    try{
        $owned=Start-Process -FilePath $env:ComSpec -WindowStyle Hidden -PassThru -WorkingDirectory $work -ArgumentList @('/d','/s','/c',('"'+$command+'"')) -RedirectStandardOutput (Join-Path $work ($LogStem+'-stdout.log')) -RedirectStandardError (Join-Path $work ($LogStem+'-stderr.log'))
        $ownedHandle=$owned.Handle
        while(!$owned.WaitForExit(1000)){
            if([DateTime]::UtcNow -ge $started.AddMinutes($MaximumMinutes)){
                & "$env:SystemRoot\System32\taskkill.exe" /PID $owned.Id /T /F | Out-File (Join-Path $work ($LogStem+'-bounded-stop.log'))
                throw ('Owned offline simulator exceeded bound: '+$Name)
            }
        }
        $owned.Refresh()
        if($owned.ExitCode -ne 0){
            Get-Content -LiteralPath (Join-Path $work ($LogStem+'-stdout.log')) -Tail 25
            Get-Content -LiteralPath (Join-Path $work ($LogStem+'-stderr.log')) -Tail 10
            throw ('Offline simulator failed: '+$Name)
        }
    }finally{
        if($owned -and !$owned.HasExited){& "$env:SystemRoot\System32\taskkill.exe" /PID $owned.Id /T /F | Out-File (Join-Path $work ($LogStem+'-owned-stop.log'))}
        if($owned){$owned.Dispose()}
    }
}
try{
    $files=$names | Where-Object {$_ -match '\.(v|sv)$' -and ($_ -notmatch '^board/' -or $_ -match 'raw_camera_capture_cam1_guarded_isolated.v$|hdmi_tx_init.v$')} | ForEach-Object {Join-Path $root $_}
    Invoke-OwnedSimulationTool 'xvlog.bat' (@('--sv')+$files) 'compile'
    foreach($top in $tops){
        Invoke-OwnedSimulationTool 'xelab.bat' @($top,'-s',$top) ($top+'-elab')
        Invoke-OwnedSimulationTool 'xsim.bat' @($top,'-runall','-log',($top+'-simulation.log')) ($top+'-run')
        $log=Get-Content -LiteralPath (Join-Path $work ($top+'-simulation.log')) -Raw
        $required=if($top -eq 'tb_cam1_isolated_init'){'(?m)^PASS CAM1 isolated actual top: complete264 writes/full7FF0, PLL/format preserved, wrongID/ID NACK/3018 address NACK61/3018 mismatch70 fail closed\.'}else{'(?m)^PASS guarded board pipeline:'}
        if($log -notmatch $required -or $log -match '(?im)fatal:|error:'){throw ('SCCB trial RTL regression failed: '+$top)}
        ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
    }
    $buslog=Get-Content -LiteralPath (Join-Path $work 'tb_cam1_isolated_init-simulation.log') -Raw
    if($buslog -notmatch '(?m)^PASS SCCB68 actual consecutive TX bit period=274 core cycles'){throw 'Actual SCCB68 waveform period proof absent'}
    $report.MeasuredConsecutiveBitPeriodCoreCycles=274
    foreach($name in $names){$report.SourceSHA256After[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash;if($report.SourceSHA256After[$name] -ne $hashes[$name]){throw 'Source changed during SCCB trial simulation'}}
    if((Get-FileHash -LiteralPath $preparedPath).Hash -ne $preparedSHA){throw 'Prepared SCCB trial manifest changed'}
    $report.LogSHA256=@{};foreach($top in $tops){$name=$top+'-simulation.log';$report.LogSHA256[$name]=(Get-FileHash -LiteralPath (Join-Path $work $name)).Hash}
    $report.MixedStream=Join-Path $work 'guarded-cam1-isolated-mixed-stream.bin'
    $report.MixedStreamSHA256=(Get-FileHash -LiteralPath $report.MixedStream).Hash
    if($buslog -notmatch '(?m)^PASS actual board sink:'){throw 'Actual board sink lifecycle proof absent'}
    $report.Passed=$true
}catch{$report.Error=$_.Exception.Message;throw}
finally{$report.EndedUtc=[DateTime]::UtcNow.ToString('o');$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'cam1-isolated-simulation.json') -Encoding utf8}
Write-Output ('isolated simulation evidence: '+(Join-Path $work 'cam1-isolated-simulation.json'))
