param([string]$OutputDirectory='')
# Full-size synthetic raw path only: no sensor init/top, PDS, COM or JTAG.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '..\tools\team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$approved=[System.IO.Path]::GetFullPath((Join-Path $root 'build\offline-20261024'))
if(!(Test-Path -LiteralPath $approved -PathType Container)){throw 'Approved scratch must already exist'}
if(!$OutputDirectory){$OutputDirectory=Join-Path $approved ('raw720-digital-sim-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))}
$work=[System.IO.Path]::GetFullPath($OutputDirectory)
if(!$work.StartsWith($approved+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $work)){throw 'Use a fresh output below approved scratch'}
$preparedPath=Join-Path $root 'board\raw_camera_capture_cam2_guarded-sources.json'
$prepared=Get-Content -Raw -Encoding UTF8 $preparedPath | ConvertFrom-Json
if(@($prepared.source_files).Count -ne 107){throw 'Main source107 binding differs'}
foreach($entry in $prepared.SourceSHA256.PSObject.Properties){if((Get-FileHash -LiteralPath (Join-Path $root $entry.Name)).Hash -ne $entry.Value){throw ('Main source changed: '+$entry.Name)}}
$names=@('rtl\raw_camera_capture.v','rtl\camera_live_bridge.v','rtl\dvp_rgb565_capture.v',
    'rtl\rgb565_burst_pack.v','rtl\video_async_fifo.v','rtl\ddr_video_writer.v','rtl\ddr_uart_frame.v',
    'rtl\video_crc32.vh','tools\frame_protocol.py','tests\tb_raw_camera_capture_720.sv',
    'tests\audit_raw_camera_capture_720.py','tests\run-raw-camera-capture-720-sim.ps1')
$hashes=@{};foreach($name in $names){$hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash}
New-Item -ItemType Directory -Path $work | Out-Null
$report=[ordered]@{Passed=$false;HardwareAccessed=$false;PDSAccessed=$false;SyntheticOnly=$true;
    SourceSHA256=$hashes;SourceFiles=$names;OutputDirectory=$work;ImageSize=@(1280,720);
    MainSource107SHA256=$prepared.SourceSHA256;PreparedSourceManifestSHA256=(Get-FileHash -LiteralPath $preparedPath).Hash;
    Pixels=921600;PayloadBytes=1843200;DDRWriteReadBeats=57600;CorePeriodNs=8;SyntheticDVPPeriodNs=22;
    UARTSink='Abstract byte-ready every6corecycles,5cycle byte-done delay,final stop ownership deliberately held through another source frame';
    Limits='Digital full-size raw data capacity only. No720sensor mode/physical input timing/fps,realUART export rate,corrected-image throughput,optics or stereo acceptance.'}
Push-Location $work
try{
    $files=$names | Where-Object {$_ -match '\.(v|sv)$'} | ForEach-Object {Join-Path $root $_}
    & (Join-Path $teamVivadoBin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 30;throw 'Full720 digital compile failed'}
    & (Join-Path $teamVivadoBin 'xelab.bat') tb_raw_camera_capture_720 -s tb_raw_camera_capture_720 *> elaboration.log
    if($LASTEXITCODE){Get-Content elaboration.log -Tail 30;throw 'Full720 digital elaboration failed'}
    & (Join-Path $teamVivadoBin 'xsim.bat') tb_raw_camera_capture_720 -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS raw720 digital:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 30;throw 'Full720 digital path failed'}
    foreach($name in $names){if((Get-FileHash -LiteralPath (Join-Path $root $name)).Hash -ne $hashes[$name]){throw 'Test/source changed during full720 simulation'}}
    foreach($entry in $prepared.SourceSHA256.PSObject.Properties){if((Get-FileHash -LiteralPath (Join-Path $root $entry.Name)).Hash -ne $entry.Value){throw 'Main source changed during full720 simulation'}}
    & $teamPython (Join-Path $root 'tests\audit_raw_camera_capture_720.py') $work *> independent-audit.log
    if($LASTEXITCODE){Get-Content independent-audit.log -Tail 30;throw 'Manual/host-parser full720 wire audit failed'}
    $report.Passed=$true;$report.SimulationLogSHA256=(Get-FileHash -LiteralPath simulation.log).Hash
    $report.WireSHA256=(Get-FileHash -LiteralPath 'raw-camera-capture-720-synthetic-stream.bin').Hash
    $report.IndependentAuditSHA256=(Get-FileHash -LiteralPath 'independent-720-digital-wire-audit.json').Hash
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'raw720-digital-simulation.json') -Encoding utf8
    Pop-Location
}
Write-Output ('Full720 digital evidence: '+(Join-Path $work 'raw720-digital-simulation.json'))
