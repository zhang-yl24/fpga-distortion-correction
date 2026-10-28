param([switch]$ExecuteBuild,[ValidateRange(1,20)][int]$MaximumMinutes=10,[string]$SimulationEvidence='')
# Default only writes an offline build plan. -ExecuteBuild invokes PDS compile,
# route and SRAM-file generation; no programmer/Flash/hardware command exists.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$target='thermal_idle'
$approved=[System.IO.Path]::GetFullPath((Join-Path $root 'build\offline-20261024'))
if(!(Test-Path -LiteralPath $approved -PathType Container)){throw 'Approved scratch root must already exist'}
$preparedPath=Join-Path $root 'board\thermal_idle-sources.json'
$prepared=Get-Content -Raw -Encoding UTF8 $preparedPath | ConvertFrom-Json
$expected=@('rtl/logos2_temperature_monitor.v','rtl/adc_temperature_reader.v','rtl/uart_tx.v','rtl/thermal_idle_telemetry.v',
    'board/thermal_idle.v','board/thermal_idle.fdc','board/thermal_idle-pins.json','board/build-thermal_idle.tcl')
if($prepared.target -ne $target -or @($prepared.source_files).Count -ne $expected.Count -or
   @(Compare-Object $expected $prepared.source_files).Count -ne 0){throw 'Prepared thermal source closure differs from fixed eight-file design'}
$hashes=@{}
foreach($name in $expected){
    $hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash
    if($hashes[$name] -ne $prepared.SourceSHA256.$name){throw ('Prepared source changed: '+$name)}
}
$simulation=$null
if($SimulationEvidence){
    $simPath=[System.IO.Path]::GetFullPath($SimulationEvidence)
    if(!$simPath.StartsWith($approved+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Simulation evidence must be in approved scratch'}
    $simulation=Get-Content -Raw -Encoding UTF8 $simPath | ConvertFrom-Json
    if($simulation.Passed -ne $true -or $simulation.HardwareAccessed -ne $false){throw 'Require successful offline-only thermal simulation'}
    foreach($name in @('rtl\thermal_idle_telemetry.v','rtl\logos2_temperature_monitor.v','rtl\adc_temperature_reader.v','rtl\uart_tx.v','board\thermal_idle.v')){
        if((Get-FileHash -LiteralPath (Join-Path $root $name)).Hash -ne $simulation.SourceSHA256.$name){throw 'Simulation source differs from candidate'}
    }
}
if($ExecuteBuild -and !$simulation){throw 'Actual build requires fresh source-bound -SimulationEvidence'}
$work=Join-Path $approved ('thermal-idle-build-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $work | Out-Null
$tcl=Join-Path $root 'board\build-thermal_idle.tcl'
$plan=[ordered]@{Target=$target;HardwareAccessed=$false;ExecutedBuild=[bool]$ExecuteBuild;
    Operation='offline_compile_route_sram_file_only';OutputDirectory=$work;SourceSHA256=$hashes;
    ThermalIdleContract=$prepared.ThermalIdleContract;ThermalSafetyVerified=$false;
    SimulationEvidence=$SimulationEvidence;NoFlashOrProgrammingOperation=$true}
$plan | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'plan.json') -Encoding utf8
if(!$ExecuteBuild){Write-Output ('Offline plan only: '+(Join-Path $work 'plan.json'));return}
$start=[DateTime]::UtcNow;$child=$null
$result=[ordered]@{Target=$target;Passed=$false;HardwareAccessed=$false;ThermalSafetyVerified=$false;StartedUtc=$start.ToString('o');OutputDirectory=$work}
try{
    $child=Start-Process -FilePath (Join-Path $teamPdsBin 'pds_shell.exe') -WindowStyle Hidden -PassThru -ArgumentList @('-file',$tcl,'-work_dir',$work,'-project_name',$target) -RedirectStandardOutput (Join-Path $work 'build-stdout.log') -RedirectStandardError (Join-Path $work 'build-stderr.log')
    $ownedNativeHandle=$child.Handle
    while(!$child.WaitForExit(10000)){
        if([DateTime]::UtcNow -ge $start.AddMinutes($MaximumMinutes)){
            & "$env:SystemRoot\System32\taskkill.exe" /PID $child.Id /T /F | Out-File (Join-Path $work 'bounded-stop.log')
            throw 'Owned thermal PDS build exceeded bound'
        }
    }
    $child.Refresh();$result.ProcessExitCode=$child.ExitCode
    $log=Get-Content -Raw (Join-Path $work 'build-stdout.log')
    if(($null -ne $child.ExitCode -and $child.ExitCode -ne 0) -or $log -match '(?m)^E:' -or
       $log -notmatch '(?m)^Executing : gen_bit_stream -scbv \{High Voltage\} -unused_io_status UNUSED successfully\.\s*$'){
        throw 'Thermal PDS did not complete SRAM-file generation; retain diagnostic logs'
    }
    $timing=Join-Path $work 'place_route\thermal_idle_timing_summary_after_hold_fix.txt'
    if((Get-Content -Raw $timing) -notmatch '(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$'){throw 'Final thermal timing did not meet constraints'}
    $pinReport=Join-Path $work 'place_route\thermal_idle_prr.prt'
    $active=@{}
    foreach($line in Get-Content -LiteralPath $pinReport){
        $parts=$line -split '\|'
        if($parts.Count -ge 7 -and $parts[4]){
            if($active.ContainsKey($parts[4])){throw 'Duplicate active thermal pin'}
            $active[$parts[4]]=$parts[0]
            $direction=if($parts[4] -eq 'clk_27m'){'input'}else{'output'}
            if($parts[5] -ne $direction -or $parts[6] -ne 'YES'){throw 'Thermal pin direction/status differs'}
        }
    }
    $pins=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'board\thermal_idle-pins.json') | ConvertFrom-Json
    if($active.Count -ne 10 -or @($pins.PSObject.Properties).Count -ne 10){throw 'Thermal idle must have exactly ten active clock/LED/UART pins'}
    foreach($entry in $pins.PSObject.Properties){if($active[$entry.Name] -ne $entry.Value){throw ('Thermal pin differs: '+$entry.Name)}}
    foreach($name in $expected){if((Get-FileHash -LiteralPath (Join-Path $root $name)).Hash -ne $hashes[$name]){throw 'Thermal source changed during PDS build'}}
    $bit=Join-Path $work 'generate_bitstream\thermal_idle.sbit'
    $manifest=[ordered]@{Target=$target;Device='PG2L100H';Package='FBG676';SCBV='High Voltage';UnusedIO='UNUSED';
        Bitstream=$bit;SHA256=(Get-FileHash -LiteralPath $bit).Hash;TimingReport=$timing;
        TimingSHA256=(Get-FileHash -LiteralPath $timing).Hash;PinReport=$pinReport;PinReportSHA256=(Get-FileHash -LiteralPath $pinReport).Hash;
        SourceSHA256=$hashes;ThermalIdleContract=$prepared.ThermalIdleContract;
        PreparedSourceManifestSHA256=(Get-FileHash -LiteralPath $preparedPath).Hash;
        ProcessExitCode=$result.ProcessExitCode;HardwareAccessed=$false;ThermalSafetyVerified=$false;
        Limits='Offline static timing and exact pin/source/bitstream validation only. No measured temperature, ADC accuracy, cooling, alarm interpretation or unattended safety is established.'}
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'validated-build.json') -Encoding utf8
    $result.Passed=$true;$result.ValidatedBuild=Join-Path $work 'validated-build.json'
}catch{$result.Error=$_.Exception.Message;throw}
finally{
    if($child -and !$child.HasExited){& "$env:SystemRoot\System32\taskkill.exe" /PID $child.Id /T /F | Out-File (Join-Path $work 'owned-stop.log')}
    if($child){$child.Dispose()}
    $result.EndedUtc=[DateTime]::UtcNow.ToString('o')
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'thermal-idle-build-result.json') -Encoding utf8
}
Write-Output ('Thermal candidate evidence: '+(Join-Path $work 'validated-build.json'))
