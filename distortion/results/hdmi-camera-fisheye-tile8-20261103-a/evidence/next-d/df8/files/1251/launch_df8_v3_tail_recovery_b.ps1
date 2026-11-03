param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{64}$')][string]$RecoveryManifestSha256,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{64}$')][string]$HandoffSha256
)
$ErrorActionPreference='Stop'
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$taskWork=(Resolve-Path -LiteralPath (Join-Path $taskRepo 'distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a')).Path
$taskManifest=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'df8-v3-tail-recovery-source-manifest-b.json')).Path
$taskHandoff=(Resolve-Path -LiteralPath (Join-Path $taskWork 'physical-tail-recovery-v3-b-go-a.json')).Path
$taskWorker=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'run_df8_v3_tail_recovery_b.py')).Path
$taskLaunch=Join-Path $PSScriptRoot 'df8-v3-tail-worker-launch-b.json'
$taskExit=Join-Path $PSScriptRoot 'df8-v3-tail-worker-exit-b.json'
$taskStdout=Join-Path $PSScriptRoot 'df8-v3-tail-worker-b.stdout.log'
$taskStderr=Join-Path $PSScriptRoot 'df8-v3-tail-worker-b.stderr.log'
foreach($taskPath in @($taskLaunch,$taskExit,$taskStdout,$taskStderr,(Join-Path $PSScriptRoot 'df8-v3-tail-recovery-start-b.json'),(Join-Path $PSScriptRoot 'df8-v3-tail-recovery-result-b.json'),(Join-Path $taskWork 'checks-scoped-v3-b-00'),(Join-Path $taskWork 'final-proof-v3-a.json'))){
    if(Test-Path -LiteralPath $taskPath){throw ('Fresh tail recovery outputs required: '+$taskPath)}
}
if((Get-FileHash -LiteralPath $taskManifest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $RecoveryManifestSha256){throw 'Independent recovery source manifest SHA256 differs'}
if((Get-FileHash -LiteralPath $taskHandoff -Algorithm SHA256).Hash.ToLowerInvariant() -ne $HandoffSha256){throw 'Independent root tail handoff SHA256 differs'}
$taskInputs=Get-Content -LiteralPath $taskManifest -Raw | ConvertFrom-Json
$taskReady=Get-Content -LiteralPath $taskHandoff -Raw | ConvertFrom-Json
if($taskInputs.Schema -ne 'tile8df8v3-supplemental-recovery-source-manifest-v1' -or $taskInputs.Passed -ne $true -or $taskInputs.RecoveryRevision -ne 'tile8df8v3-same-source-tail-recovery-b' -or $taskInputs.ReplacesOriginalProviderManifest -ne $false){throw 'Separate completed unchanged-provider recovery source freeze required'}
$taskWorkerPin=$taskInputs.InputSHA256.PSObject.Properties[$taskWorker]
if($null -eq $taskWorkerPin -or $taskWorkerPin.Value -ne (Get-FileHash -LiteralPath $taskWorker -Algorithm SHA256).Hash.ToLowerInvariant()){throw 'Actual tail worker must match the frozen input SHA256'}
$taskLauncherPin=$taskInputs.InputSHA256.PSObject.Properties[$PSCommandPath]
if($null -eq $taskLauncherPin -or $taskLauncherPin.Value -ne (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()){throw 'Actual tail launcher must match the frozen input SHA256'}
if($taskReady.RecoverySourceManifest.Path -ne $taskManifest -or $taskReady.RecoverySourceManifest.SHA256 -ne $RecoveryManifestSha256 -or $taskReady.RootAuthorizedTailRecovery -ne $true -or $taskReady.PriorWorkerEnded -ne $true -or $taskReady.PDriveReleased -ne $true){throw 'Explicit completed original-worker root recovery handoff required'}
if(Test-Path -LiteralPath 'P:/'){throw 'P: is already owned; preserve the checkpoint'}
if(Get-Process -Name pds_shell -ErrorAction SilentlyContinue){throw 'A PDS process is still running'}
if(Get-Process -Id 43412,2336 -ErrorAction SilentlyContinue){throw 'The original physical/query process still exists'}
$taskExisting=Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {$_.CommandLine -and ($_.CommandLine.Contains('run_physical_v3_a.py') -or $_.CommandLine.Contains('run_physical_v2_a.py') -or $_.CommandLine.Contains('run_df8_v3_tail_recovery_b.py'))}
if($taskExisting){throw 'Another physical or tail worker is running'}
$taskProcess=Start-Process -FilePath 'D:/anaconda3/python.exe' -ArgumentList @('-B',$taskWorker,'--execute',$taskHandoff,'--handoff-sha256',$HandoffSha256) `
    -WorkingDirectory $taskRepo -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskStdout -RedirectStandardError $taskStderr
$taskRecord=[ordered]@{
    Schema='tile8df8v3-tail-worker-launch-v1';PID=$taskProcess.Id;StartedUTC=$taskProcess.StartTime.ToUniversalTime().ToString('o')
    ProviderSourceManifest=$taskInputs.OriginalProviderManifest;RecoverySourceManifest=@{Path=$taskManifest;SHA256=$RecoveryManifestSha256}
    RootRecoveryHandoff=@{Path=$taskHandoff;SHA256=$HandoffSha256}
    WorkerSource=@{Path=$taskWorker;SHA256=(Get-FileHash -LiteralPath $taskWorker -Algorithm SHA256).Hash.ToLowerInvariant()}
    LauncherSource=@{Path=$PSCommandPath;SHA256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()}
    Stdout=$taskStdout;Stderr=$taskStderr;OriginalPhysicalWorkerClaimedSuccessful=$false;HardwareAccessPlanned=$false
}
$taskEncoding=New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($taskLaunch,($taskRecord|ConvertTo-Json -Depth 8)+"`n",$taskEncoding)
$taskRecord|ConvertTo-Json -Depth 8
while(-not $taskProcess.WaitForExit(30000)){Write-Output ('tile8df8v3 original tail worker '+$taskProcess.Id+' running at '+[DateTime]::UtcNow.ToString('o'))}
$taskProcess.Refresh()
$taskFinal=[ordered]@{Schema='tile8df8v3-tail-worker-exit-v1';PID=$taskProcess.Id;ObservedExitUTC=[DateTime]::UtcNow.ToString('o');ExitCode=$taskProcess.ExitCode;ObserverOnly=$true;CurrentContextPVisible=(Test-Path -LiteralPath 'P:/')}
[System.IO.File]::WriteAllText($taskExit,($taskFinal|ConvertTo-Json -Depth 8)+"`n",$taskEncoding)
$taskFinal|ConvertTo-Json -Depth 8
exit $taskProcess.ExitCode
