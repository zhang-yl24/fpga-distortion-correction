param([switch]$ExecuteBuild,[ValidateRange(1,30)][int]$MaximumMinutes=20,[string]$SimulationEvidence='')
# Default writes an offline plan only. PDS builds an SRAM file; this script has
# no COM/cable/programmer/Flash operation and never alters the old raw target.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$target='raw_camera_capture_cam2_guarded'
$approved=[System.IO.Path]::GetFullPath((Join-Path $root 'build\offline-20261024'))
if(!(Test-Path -LiteralPath $approved -PathType Container)){throw 'Approved scratch root must already exist'}
$preparedPath=Join-Path $root ('board\'+$target+'-sources.json')
$prepared=Get-Content -Raw -Encoding UTF8 $preparedPath | ConvertFrom-Json
$baseline=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'board\raw_camera_capture_cam2_ref-sources.json') | ConvertFrom-Json
foreach($entry in $baseline.SourceSHA256.PSObject.Properties){
    if((Get-FileHash -LiteralPath (Join-Path $root $entry.Name)).Hash -ne $entry.Value){throw 'Original raw97 source differs'}
}
$contract=(Get-Content -Raw -Encoding UTF8 (Join-Path $root 'output\project\guarded-protocol-v2.json') | ConvertFrom-Json).contract
if($prepared.target -ne $target -or @($prepared.source_files).Count -ne 107 -or
   ($prepared.GuardedControlContract | ConvertTo-Json -Compress) -ne ($contract | ConvertTo-Json -Compress) -or
   ($prepared.RawCaptureContract | ConvertTo-Json -Compress) -ne ($baseline.RawCaptureContract | ConvertTo-Json -Compress)){
    throw 'Prepared guarded source identity/closure/contracts differ'
}
$hashes=@{}
foreach($name in $prepared.source_files){
    if($hashes.ContainsKey($name)){throw 'Duplicate prepared source'}
    $resolved=[System.IO.Path]::GetFullPath((Join-Path $root $name))
    if(!$resolved.StartsWith($root+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Non-project prepared source'}
    $hashes[$name]=(Get-FileHash -LiteralPath $resolved).Hash
    if($hashes[$name] -ne $prepared.SourceSHA256.$name){throw ('Prepared source changed: '+$name)}
}
if(@($prepared.SourceSHA256.PSObject.Properties).Count -ne $hashes.Count){throw 'Prepared hash closure differs'}
$simPath=$null
if($SimulationEvidence){
    $simPath=[System.IO.Path]::GetFullPath($SimulationEvidence)
    if(!$simPath.StartsWith($approved+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Simulation must remain in approved scratch'}
    $sim=Get-Content -Raw -Encoding UTF8 $simPath | ConvertFrom-Json
    if($sim.Passed -ne $true -or $sim.HardwareAccessed -ne $false -or $sim.OriginalRaw97SourceBindingPreserved -ne $true){throw 'Require successful source-bound offline simulation'}
    $requiredTops=@('tb_raw_capture_lease','tb_guarded_raw_camera_capture','tb_guarded_temperature_cdc','tb_guarded_status_uart','tb_guarded_board_pipeline')
    if(@($sim.RegressionTops).Count -ne 5 -or @(Compare-Object $requiredTops $sim.RegressionTops).Count -ne 0){throw 'Build requires the complete five-top guarded regression'}
    foreach($name in @('rtl/raw_capture_lease.v','rtl/raw_camera_capture_guarded.v','rtl/raw_camera_capture.v',
        'rtl/guarded_temperature_cdc.v','rtl/guarded_status_uart.v','rtl/guarded_uart_arbiter.v',
        'rtl/guarded_capture_controller.v','rtl/guarded_command_engine.v','rtl/experimental/uart_rx_control.v',
        'rtl/logos2_temperature_monitor.v','rtl/adc_temperature_reader.v','rtl/uart_tx.v','board/raw_camera_capture_cam2_guarded.v')){
        $key=$name.Replace('/','\')
        if($hashes[$name] -ne $sim.SourceSHA256.$key){throw ('Simulation binding differs: '+$name)}
    }
    if((Get-FileHash -LiteralPath $sim.MixedStream).Hash -ne $sim.MixedStreamSHA256){throw 'Mixed simulation stream changed'}
}
if($ExecuteBuild -and !$simPath){throw 'Actual offline build requires -SimulationEvidence'}
$work=Join-Path $approved ('raw-guarded-board-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $work | Out-Null
$tcl=Join-Path $root ('board\build-'+$target+'.tcl')
$plan=[ordered]@{Target=$target;HardwareAccessed=$false;ExecuteBuild=[bool]$ExecuteBuild;NoFlashOrProgrammingOperation=$true;
    Operation='offline_compile_route_sram_file_only';SourceSHA256=$hashes;OutputDirectory=$work;
    RawCaptureContract=$prepared.RawCaptureContract;GuardedControlContract=$contract;SimulationEvidence=$simPath}
if($simPath){$plan.SimulationEvidenceSHA256=(Get-FileHash -LiteralPath $simPath).Hash}
$plan | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'plan.json') -Encoding utf8
if(!$ExecuteBuild){Write-Output ('Offline plan only: '+(Join-Path $work 'plan.json'));return}
$started=[DateTime]::UtcNow;$child=$null
$result=[ordered]@{Target=$target;Passed=$false;HardwareAccessed=$false;StartedUtc=$started.ToString('o');OutputDirectory=$work;SourceSHA256=$hashes}
try{
    $child=Start-Process -FilePath (Join-Path $teamPdsBin 'pds_shell.exe') -WindowStyle Hidden -PassThru -ArgumentList @('-file',$tcl,'-work_dir',$work,'-project_name',$target) -RedirectStandardOutput (Join-Path $work 'build-stdout.log') -RedirectStandardError (Join-Path $work 'build-stderr.log')
    $ownedNativeHandle=$child.Handle
    while(!$child.WaitForExit(10000)){
        if([DateTime]::UtcNow -ge $started.AddMinutes($MaximumMinutes)){
            & "$env:SystemRoot\System32\taskkill.exe" /PID $child.Id /T /F | Out-File (Join-Path $work 'bounded-stop.log')
            throw 'Owned guarded PDS build exceeded the finite build bound'
        }
    }
    $child.Refresh();$result.ProcessExitCode=$child.ExitCode
    $log=Get-Content -Raw (Join-Path $work 'build-stdout.log')
    if(($null -ne $child.ExitCode -and $child.ExitCode -ne 0) -or $log -match '(?m)^E:' -or
       $log -notmatch '(?m)^Executing : gen_bit_stream -scbv \{High Voltage\} -unused_io_status UNUSED successfully\.\s*$'){
        throw 'Guarded PDS did not complete SRAM file generation; retained logs are diagnostic evidence'
    }
    $timing=Join-Path $work ('place_route\'+$target+'_timing_summary_after_hold_fix.txt')
    if((Get-Content -Raw $timing) -notmatch '(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$'){throw 'Final guarded timing did not meet constraints'}
    $pinReport=Join-Path $work ('place_route\'+$target+'_prr.prt')
    $active=@{}
    foreach($line in Get-Content -LiteralPath $pinReport){
        $parts=$line -split '\|'
        if($parts.Count -ge 7 -and $parts[4]){
            $port=$parts[4]
            if($active.ContainsKey($port)){throw 'Duplicate routed port'}
            $active[$port]=$parts[0]
            $direction=if($port -match '^(clk_27m|clk_p|clk_n|cam_pclk|cam_vsync|cam_href|cam_data\[\d+\]|uart_rxd)$'){'input'}elseif($port -match '^(cam_rst_n|cam_scl|cam_sda|hd_scl|hd_sda|mem_dq\[\d+\]|mem_dqs(_n)?\[\d+\])$'){'inout'}else{'output'}
            if($parts[5] -ne $direction -or $parts[6] -ne 'YES'){throw ('Routed direction/status differs: '+$port)}
        }
    }
    $pins=Get-Content -Raw -Encoding UTF8 (Join-Path $root ('board\'+$target+'-pins.json')) | ConvertFrom-Json
    if($active.Count -ne 129 -or @($pins.PSObject.Properties).Count -ne 129){throw 'Guarded target must have exactly 129 active ports'}
    foreach($entry in $pins.PSObject.Properties){if($active[$entry.Name] -ne $entry.Value){throw ('Routed pin differs: '+$entry.Name)}}
    if($active['uart_rxd'] -ne 'B24' -or $active['cam_data[5]'] -ne 'AA23'){throw 'Guarded RX/CAM2 D5 differs'}
    foreach($name in $prepared.source_files){if((Get-FileHash -LiteralPath (Join-Path $root $name)).Hash -ne $hashes[$name]){throw 'Source changed during build'}}
    $bit=Join-Path $work ('generate_bitstream\'+$target+'.sbit')
    $manifest=[ordered]@{Target=$target;Device='PG2L100H';Package='FBG676';SCBV='High Voltage';UnusedIO='UNUSED';
        Bitstream=$bit;SHA256=(Get-FileHash -LiteralPath $bit).Hash;TimingReport=$timing;TimingSHA256=(Get-FileHash -LiteralPath $timing).Hash;
        PinReport=$pinReport;PinReportSHA256=(Get-FileHash -LiteralPath $pinReport).Hash;SourceSHA256=$hashes;
        RawCaptureContract=$prepared.RawCaptureContract;GuardedControlContract=$contract;
        PreparedSourceManifestSHA256=(Get-FileHash -LiteralPath $preparedPath).Hash;
        SimulationEvidence=$simPath;SimulationEvidenceSHA256=(Get-FileHash -LiteralPath $simPath).Hash;
        ProcessExitCode=$result.ProcessExitCode;HardwareAccessed=$false;ThermalSafetyVerified=$false;
        Limits='Offline digital candidate only. Native raw CAM2 connector slot, unassigned physical eye. Internal ADC approximate, not independently calibrated. Lease milliseconds are nominal 125MHz core cycles, not an independent wall-clock watchdog: core halt pauses lease/freshness timers, can silence UART and does not create a new session on resumption. Finite admission budget is not a power/clock cutoff. In-flight DDR/UART drains; failed partial raw holds UART until host timeout/reset. Host finite total batch and finally idle restoration remain required. No unattended, heavy-load thermal, optical or stereo acceptance.'}
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'validated-build.json') -Encoding utf8
    $result.Passed=$true;$result.ValidatedBuild=Join-Path $work 'validated-build.json'
}catch{$result.Error=$_.Exception.Message;throw}
finally{
    if($child -and !$child.HasExited){& "$env:SystemRoot\System32\taskkill.exe" /PID $child.Id /T /F | Out-File (Join-Path $work 'owned-stop.log')}
    if($child){$child.Dispose()}
    $result.EndedUtc=[DateTime]::UtcNow.ToString('o')
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'guarded-board-build-result.json') -Encoding utf8
}
Write-Output ('Guarded candidate evidence: '+(Join-Path $work 'validated-build.json'))
