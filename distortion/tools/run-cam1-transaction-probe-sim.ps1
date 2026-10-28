param([string]$OutputDirectory='',[ValidateRange(1,10)][int]$MaximumMinutes=5)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$approved=[System.IO.Path]::GetFullPath((Join-Path $root 'build\offline-20261024'))
if(!(Test-Path -LiteralPath $approved -PathType Container)){throw 'Approved scratch must exist'}
$previousBytecode=$env:PYTHONDONTWRITEBYTECODE;$env:PYTHONDONTWRITEBYTECODE='1'
try{& $teamPython -B (Join-Path $PSScriptRoot 'build_cam1_transaction_probe.py') --prepare;$prepareExit=$LASTEXITCODE}finally{$env:PYTHONDONTWRITEBYTECODE=$previousBytecode}
if($prepareExit){throw 'Fixed diagnostic source8/pins6 validation failed'}
if(!$OutputDirectory){$OutputDirectory=Join-Path $approved ('cam1-transaction-uart-sim-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))}
$work=[System.IO.Path]::GetFullPath($OutputDirectory)
if(!$work.StartsWith($approved+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $work)){throw 'Fresh approved scratch output required'}
New-Item -ItemType Directory -Path $work | Out-Null
$preparedPath=Join-Path $root 'board/cam1_transaction_probe-sources.json'
$prepared=Get-Content -LiteralPath $preparedPath -Raw -Encoding UTF8 | ConvertFrom-Json
$preparedSHA=(Get-FileHash -LiteralPath $preparedPath).Hash
$names=@($prepared.source_files)+@('tests/tb_cam1_transaction_probe_uart.sv','tools/run-cam1-transaction-probe-sim.ps1','tools/build_cam1_transaction_probe.py')+@($prepared.ReferenceSourceSHA256.PSObject.Properties.Name)
if($names.Count -ne 13){throw 'Exact13 simulation source binding required'}
$hashes=@{};foreach($name in $names){$hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash}
$started=[DateTime]::UtcNow
$report=[ordered]@{Passed=$false;HardwareAccessed=$false;PDSAccessed=$false;Target='cam1_transaction_probe';
    Cases=@('complete_original_success','write4_read1_pending61');SourceSHA256=$hashes;SourceSHA256After=@{};
    PreparedSourceManifestSHA256=$preparedSHA;DiagnosticContract=$prepared.DiagnosticContract;OutputDirectory=$work;
    Limits='Actual six-pin top, SCCB open-drain model and real8N1 UART transmitter. Period accelerated to20000 cycles in TB only. Digital supplied sensor replies are not hardware ACK/voltage evidence. No RAW/DDR/HDMI/PDS/devices.'}
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
    $files=$names | Where-Object {$_ -match '\.(v|sv)$'} | ForEach-Object {Join-Path $root $_}
    Invoke-OwnedSimulationTool 'xvlog.bat' (@('--sv')+$files) 'compile'
    Invoke-OwnedSimulationTool 'xelab.bat' @('tb_cam1_transaction_probe_uart','-s','tb_cam1_transaction_probe_uart') 'elab'
    Invoke-OwnedSimulationTool 'xsim.bat' @('tb_cam1_transaction_probe_uart','-runall','-log','transaction-probe-simulation.log') 'run'
    $log=Get-Content -LiteralPath (Join-Path $work 'transaction-probe-simulation.log') -Raw
    if($log -notmatch '(?m)^PASS actual cam1_transaction_probe UART:' -or $log -match '(?im)fatal:|error:'){throw 'Actual-top UART two-case proof absent'}
    $prior=$env:PYTHONDONTWRITEBYTECODE;$env:PYTHONDONTWRITEBYTECODE='1'
    try{$auditText=& $teamPython -B (Join-Path $PSScriptRoot 'build_cam1_transaction_probe.py') --audit-uart-dir $work;$auditExit=$LASTEXITCODE}finally{$env:PYTHONDONTWRITEBYTECODE=$prior}
    if($auditExit){throw 'Independent struct/zlib UART wire audit failed'}
    $report.WireAudit=$auditText | ConvertFrom-Json
    $report.WireSHA256=@{};foreach($name in @('pgcamd01-success-wire.bin','pgcamd01-read-nack-wire.bin')){$report.WireSHA256[$name]=(Get-FileHash -LiteralPath (Join-Path $work $name)).Hash}
    foreach($name in $names){$report.SourceSHA256After[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash;if($report.SourceSHA256After[$name] -ne $hashes[$name]){throw 'Diagnostic source changed during simulation'}}
    if((Get-FileHash -LiteralPath $preparedPath).Hash -ne $preparedSHA){throw 'Prepared diagnostic source changed'}
    $report.LogSHA256=@{};foreach($name in @('compile-stdout.log','elab-stdout.log','transaction-probe-simulation.log')){$report.LogSHA256[$name]=(Get-FileHash -LiteralPath (Join-Path $work $name)).Hash}
    $report.Passed=$true
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}catch{$report.Error=$_.Exception.Message;throw}
finally{$report.EndedUtc=[DateTime]::UtcNow.ToString('o');$report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $work 'cam1-transaction-uart-simulation.json') -Encoding utf8}
Write-Output ('Diagnostic UART simulation: '+(Join-Path $work 'cam1-transaction-uart-simulation.json'))
