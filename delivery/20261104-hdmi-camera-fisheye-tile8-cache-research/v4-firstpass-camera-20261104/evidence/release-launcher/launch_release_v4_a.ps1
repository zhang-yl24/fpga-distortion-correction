param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$AuthoritySHA,
    [string]$DeadlineUTC='2026-11-04T10:00:00Z'
)
$ErrorActionPreference='Stop'
$taskRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
$taskWork=Join-Path $taskRepo 'distortion/work/hdmi-camera-fisheye-assoc2way256-fastpipe-20261104-a'
$taskAuthorityPath=Join-Path $taskWork 'release-v4-authority-a.json'
$taskWorkerPath=Join-Path $taskWork 'run_release_v4_a.py'
$taskLaunch=Join-Path $PSScriptRoot 'release-launch-v4-a.json'
$taskExit=Join-Path $PSScriptRoot 'release-exit-v4-a.json'
$taskOut=Join-Path $PSScriptRoot 'release-v4-a.stdout.log'
$taskErr=Join-Path $PSScriptRoot 'release-v4-a.stderr.log'
foreach($taskPath in @($taskLaunch,$taskExit,$taskOut,$taskErr,(Join-Path $taskWork 'bit-v4-a'),(Join-Path $taskWork 'program-v4-a'),(Join-Path $taskWork 'fps-corrected-v4-a'))) {
    if(Test-Path -LiteralPath $taskPath){throw 'Fresh sole release outputs required'}
}
if((Get-FileHash -LiteralPath $taskAuthorityPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $AuthoritySHA){throw 'Exact approved release authority required'}
$taskAuthority=Get-Content -LiteralPath $taskAuthorityPath -Raw | ConvertFrom-Json
if($taskAuthority.Schema -ne 'fastpipe-saved-firstpass-release-authority-v4' -or $taskAuthority.RootHandoff.UserAuthorizedVolatileSRAM -ne $true -or $taskAuthority.RootHandoff.UserNotifiedBeforeExecution -ne $true -or $taskAuthority.FlashAuthorized -ne $false){throw 'Existing user SRAM authorization and notification required'}
$taskLauncherSHA=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
$taskWorkerSHA=(Get-FileHash -LiteralPath $taskWorkerPath -Algorithm SHA256).Hash.ToLowerInvariant()
if($taskAuthority.InputSHA256.$PSCommandPath -ne $taskLauncherSHA -or $taskAuthority.InputSHA256.$taskWorkerPath -ne $taskWorkerSHA){throw 'Exact fixed launcher and worker sources required'}
$taskStopPath=Join-Path $PSScriptRoot 'second-pass-stop-observation-v4-a.json'
if((Get-FileHash -LiteralPath $taskStopPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne '9a4b170674f8c2c34d195d55eeb81e52f3bf2f0333fa13cf36576467336ed089'){throw 'Exact actual interruption/cleanup observation required'}
$taskStop=Get-Content -LiteralPath $taskStopPath -Raw | ConvertFrom-Json
if($taskStop.ActualExitCode -ne -1 -or $taskStop.SecondPassIntentionallyInterrupted -ne $true -or $taskStop.SecondPassPassed -ne $false -or $taskStop.FirstPassProofPreserved -ne $true -or $taskStop.WorkerAbsent -ne $true -or $taskStop.PDSAbsent -ne $true -or $taskStop.PDriveReleased -ne $true){throw 'Preserve actual interrupted second pass and completed first pass'}
if(@(Get-CimInstance Win32_Process -Filter ('ProcessId = '+[int]$taskStop.PID)).Count -ne 0){throw 'Prior physical worker remains'}
if(@(Get-CimInstance Win32_Process -Filter "Name = 'PDS.exe' OR Name = 'pds_shell.exe' OR Name = 'cdt_js.exe' OR Name = 'cdt_cmd.exe' OR Name = 'cdt_cfg_shell.exe'").Count -ne 0 -or (Test-Path -LiteralPath 'P:/')){throw 'Existing EDA/JTAG owner or alias remains'}
$taskDeadline=[DateTimeOffset]::Parse($DeadlineUTC)
if(($taskDeadline-[DateTimeOffset]::UtcNow).TotalSeconds -lt 180){throw 'Insufficient actual release time budget'}
$taskArgs=@('-B','distortion/work/hdmi-camera-fisheye-assoc2way256-fastpipe-20261104-a/run_release_v4_a.py','--authority-sha',$AuthoritySHA,'--deadline-utc',$DeadlineUTC)
$taskWorker=Start-Process -FilePath 'D:/anaconda3/python.exe' -ArgumentList $taskArgs -WorkingDirectory $taskRepo -WindowStyle Hidden -RedirectStandardOutput $taskOut -RedirectStandardError $taskErr -PassThru
$taskHeldHandle=$taskWorker.Handle
if($taskHeldHandle -eq [IntPtr]::Zero){throw 'Retained actual release worker handle required'}
$taskCreation=$taskWorker.StartTime.ToUniversalTime().ToString('o')
[ordered]@{Schema='fastpipe-release-launch-v4';PID=$taskWorker.Id;CreationUTC=$taskCreation;AuthoritySHA256=$AuthoritySHA;WorkerSHA256=$taskWorkerSHA;LauncherSHA256=$taskLauncherSHA;ProcessHandleRetained=$true;DeadlineUTC=$DeadlineUTC;VolatileSRAMOnly=$true;FlashAuthorized=$false;OriginalSecondPassExitCode=-1} | ConvertTo-Json | Set-Content -LiteralPath $taskLaunch -Encoding UTF8
Write-Output ('Started sole saved-proof bitstream/SRAM/camera worker PID '+$taskWorker.Id)
$taskWorker.WaitForExit()
$taskWorker.Refresh()
$taskExitCode=$taskWorker.ExitCode
if($null -eq $taskExitCode){throw 'Actual release exit code unavailable; no success receipt written'}
[ordered]@{Schema='fastpipe-release-exit-v4';PID=$taskWorker.Id;CreationUTC=$taskCreation;ExitCode=$taskExitCode;ObservedUTC=[DateTime]::UtcNow.ToString('o');AuthoritySHA256=$AuthoritySHA;WorkerSHA256=$taskWorkerSHA;LauncherSHA256=$taskLauncherSHA;LaunchReceiptSHA256=(Get-FileHash -LiteralPath $taskLaunch -Algorithm SHA256).Hash.ToLowerInvariant();ProcessHandleRetained=$true;PDriveVisible=(Test-Path -LiteralPath 'P:/')} | ConvertTo-Json | Set-Content -LiteralPath $taskExit -Encoding UTF8
Write-Output ('Actual release worker exit '+$taskExitCode)
$taskWorker.Dispose()
exit $taskExitCode
