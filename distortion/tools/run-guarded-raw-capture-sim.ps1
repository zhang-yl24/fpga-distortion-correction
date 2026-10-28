param([string]$OutputDirectory='')
# Offline only: no PDS, cable, COM, programming or status-file writes.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$approved=[System.IO.Path]::GetFullPath((Join-Path $root 'build\offline-20261024'))
if(!(Test-Path -LiteralPath $approved -PathType Container)){throw 'Approved scratch root must already exist'}
if(!$OutputDirectory){$OutputDirectory=Join-Path $approved ('guarded-raw-sim-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))}
$work=[System.IO.Path]::GetFullPath($OutputDirectory)
if(!$work.StartsWith($approved+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){
    throw 'Output must remain below the approved offline scratch directory'
}
if(Test-Path -LiteralPath $work){throw 'Use a fresh append-only scratch output'}
New-Item -ItemType Directory -Path $work | Out-Null
$names=@('rtl\raw_capture_lease.v','rtl\raw_camera_capture_guarded.v','rtl\raw_camera_capture.v',
    'rtl\camera_live_bridge.v','rtl\dvp_rgb565_capture.v','rtl\rgb565_burst_pack.v',
    'rtl\video_async_fifo.v','rtl\ddr_video_writer.v','rtl\ddr_uart_frame.v','rtl\video_crc32.vh',
    'tests\tb_raw_capture_lease.sv','tests\tb_guarded_raw_camera_capture.sv',
    'tools\run-guarded-raw-capture-sim.ps1')
$hashes=@{}
foreach($name in $names){$hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash}
$baseline=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'board\raw_camera_capture_cam2_ref-sources.json') | ConvertFrom-Json
foreach($entry in $baseline.SourceSHA256.PSObject.Properties){
    if((Get-FileHash -LiteralPath (Join-Path $root $entry.Name)).Hash -ne $entry.Value){throw 'Previously validated raw board source changed; do not mix candidate evidence'}
}
$report=[ordered]@{Passed=$false;HardwareAccessed=$false;PDSAccessed=$false;SourceSHA256=$hashes;
    PreviousRawBoardSourceBindingPreserved=$true;OutputDirectory=$work;ImageSize=@(32,16);
    TemperatureADCIntegrated=$false;HardwareClockPowerStopped=$false;
    Limits='Independent candidate RTL simulation only. Lease/budget/interlock gates new admissions and preserves in-flight DDR/UART ownership. It does not switch to heartbeat, prove physical cooling, provide a live host command receiver or establish unattended board safety.'}
Push-Location $work
try{
    $files=$names | Where-Object {$_ -match '\.(v|sv)$'} | ForEach-Object {Join-Path $root $_}
    & (Join-Path $teamVivadoBin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 25;throw 'Guarded raw compile failed'}
    foreach($top in @('tb_raw_capture_lease','tb_guarded_raw_camera_capture')){
        & (Join-Path $teamVivadoBin 'xelab.bat') $top -s $top *> ($top+'-elab.log')
        if($LASTEXITCODE){Get-Content ($top+'-elab.log') -Tail 25;throw ('Guarded raw elaboration failed: '+$top)}
        & (Join-Path $teamVivadoBin 'xsim.bat') $top -runall -log ($top+'-simulation.log') *> ($top+'-run.log')
        $log=Get-Content -Raw ($top+'-simulation.log')
        $pass=if($top -eq 'tb_raw_capture_lease'){'(?m)^PASS raw capture lease controller regression\.'}else{'(?m)^PASS guarded raw camera capture regression:'}
        if($LASTEXITCODE -or $log -notmatch $pass -or $log -match '(?im)fatal:|error:'){
            Get-Content ($top+'-simulation.log') -Tail 30;throw ('Guarded raw regression failed: '+$top)
        }
        ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
    }
    foreach($name in $names){if((Get-FileHash -LiteralPath (Join-Path $root $name)).Hash -ne $hashes[$name]){throw 'Source changed during simulation'}}
    $report.Passed=$true
    $report.ControllerLogSHA256=(Get-FileHash -LiteralPath 'tb_raw_capture_lease-simulation.log').Hash
    $report.IntegrationLogSHA256=(Get-FileHash -LiteralPath 'tb_guarded_raw_camera_capture-simulation.log').Hash
    $report.SyntheticStreamSHA256=(Get-FileHash -LiteralPath 'raw-camera-capture-synthetic-stream.bin').Hash
}finally{
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'guarded-raw-simulation.json') -Encoding utf8
    Pop-Location
}
Write-Output ('Candidate evidence: '+(Join-Path $work 'guarded-raw-simulation.json'))
