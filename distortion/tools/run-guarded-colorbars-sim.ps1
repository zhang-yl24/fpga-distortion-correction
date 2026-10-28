param([string]$OutputDirectory='',[ValidateRange(1,10)][int]$MaximumMinutes=3)
# Bounded offline SCCB RTL regression. Never touches COM/JTAG or the old
# camera_colorbars_sim directory. Testbench uses no analog/optical model.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$approved=[System.IO.Path]::GetFullPath((Join-Path $root 'build\offline-20261024'))
if(!(Test-Path -LiteralPath $approved -PathType Container)){throw 'Approved scratch root must exist'}
if(!$OutputDirectory){$OutputDirectory=Join-Path $approved ('guarded-colorbars-sim-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))}
$work=[System.IO.Path]::GetFullPath($OutputDirectory)
if(!$work.StartsWith($approved+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $work)){throw 'Use fresh output below approved scratch'}
New-Item -ItemType Directory -Path $work | Out-Null
$names=@('rtl/reg16_i2c.v','rtl/experimental/ov5640_colorbars_init.v','board/ov5640_colorbars_commands.vh',
    'tests/tb_ov5640_colorbars.sv','tests/tb_guarded_colorbars_init.sv','tools/run-guarded-colorbars-sim.ps1')
$hashes=@{};foreach($name in $names){$hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash}
if($hashes['rtl/experimental/ov5640_colorbars_init.v'] -ne 'BAC47AB4178A5ABC23EAA053808784C39676AC630A5EA5137CF1572C2EE00421' -or
   $hashes['board/ov5640_colorbars_commands.vh'] -ne '39049F0F5F99AEF45AB89A329BC743A639F350E344DCA5A9B4DADE624E040144'){throw 'Stable reviewed sensor colorbar sources differ'}
$started=[DateTime]::UtcNow
$report=[ordered]@{Passed=$false;HardwareAccessed=$false;PDSAccessed=$false;OutputDirectory=$work;
    SourceSHA256=$hashes;DynamicPadMask=1;TrialPadMask='7ff0';Fixture='tb_ov5640_colorbars';
    SourceSHA256After=@{};OpticalSceneVerified=$false;TemperatureSafetyVerified=$false}
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
    $files=@('rtl/reg16_i2c.v','rtl/experimental/ov5640_colorbars_init.v','tests/tb_ov5640_colorbars.sv','tests/tb_guarded_colorbars_init.sv') | ForEach-Object {Join-Path $root $_}
    Invoke-OwnedSimulationTool 'xvlog.bat' (@('--sv')+$files) 'compile'
    Invoke-OwnedSimulationTool 'xelab.bat' @('tb_guarded_colorbars_init','-s','tb_guarded_colorbars_init') 'elaborate'
    Invoke-OwnedSimulationTool 'xsim.bat' @('tb_guarded_colorbars_init','-runall','-log','simulation.log') 'run'
    $logPath=Join-Path $work 'simulation.log'
    $log=Get-Content -Raw -LiteralPath $logPath
    if($log -notmatch '(?m)^PASS camera colorbars: 265 writes, preserved RGB565, test-pattern readback and wrong-ID/NACK/pad/PLL/format/test-pattern failures rejected\s*$' -or $log -match '(?im)fatal:|error:'){throw 'Colorbar ready/readback/bad-pattern regression did not pass'}
    foreach($name in $names){
        $report.SourceSHA256After[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash
        if($report.SourceSHA256After[$name] -ne $hashes[$name]){throw 'Colorbar source changed during simulation'}
    }
    $report.SimulationLog=$logPath;$report.SimulationLogSHA256=(Get-FileHash -LiteralPath $logPath).Hash
    $report.Passed=$true
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}catch{$report.Error=$_.Exception.Message;throw}
finally{
    $report.EndedUtc=[DateTime]::UtcNow.ToString('o')
    $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $work 'guarded-colorbars-simulation.json') -Encoding utf8
}
Write-Output ('Colorbar simulation evidence: '+(Join-Path $work 'guarded-colorbars-simulation.json'))
