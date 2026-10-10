param([string]$Target='corrected_pipeline_cadence_seed4',[ValidateRange(1,60)][int]$Minutes=18)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
if($Target -notmatch '^[a-z0-9_]+$'){throw 'Invalid target name'}
$work=Join-Path $root ('build\'+$Target)
New-Item -ItemType Directory -Force -Path $work | Out-Null
$control=Join-Path $root ('build\bounded-control-'+$Target+'-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $control | Out-Null
$start=[DateTime]::UtcNow
$deadline=$start.AddMinutes($Minutes)
$env:PSModulePath=$null
$child=Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -WindowStyle Hidden -PassThru -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'build-pds.ps1'),'-Target',$Target) -RedirectStandardOutput (Join-Path $control 'bounded-stdout.log') -RedirectStandardError (Join-Path $control 'bounded-stderr.log')
$timedOut=$false
try {
    while(!$child.WaitForExit(10000)){
        if([DateTime]::UtcNow -ge $deadline){
            $timedOut=$true
            # Retain the exact owned process handle; no global PDS process kill.
            if(!$child.HasExited){
                & "$env:SystemRoot\System32\taskkill.exe" /PID $child.Id /T /F | Out-File (Join-Path $work 'bounded-stop.log')
                if($LASTEXITCODE -ne 0 -and !$child.HasExited){throw 'Owned PDS process tree did not terminate'}
            }
            $child.WaitForExit()
            break
        }
    }
    $child.Refresh()
    $valid=(!$timedOut -and $child.ExitCode -eq 0 -and (Test-Path -LiteralPath (Join-Path $work 'validated-build.json')))
    [pscustomobject]@{Target=$Target;StartedUtc=$start.ToString('o');EndedUtc=[DateTime]::UtcNow.ToString('o');DeadlineUtc=$deadline.ToString('o');OwnedPID=$child.Id;TimedOut=$timedOut;ExitCode=$child.ExitCode;Passed=$valid;HardwareAccessed=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $work 'bounded-result.json') -Encoding utf8
    if(!$valid){throw 'Bounded PDS attempt did not produce a validated bitstream; hardware remains idle'}
} finally {
    if(!$child.HasExited){
        & "$env:SystemRoot\System32\taskkill.exe" /PID $child.Id /T /F | Out-File (Join-Path $work 'bounded-stop.log')
    }
    $child.Dispose()
    # The build helper may preserve and replace its work directory. Keep open
    # redirected handles outside that directory, then copy them after exit.
    foreach($name in @('bounded-stdout.log','bounded-stderr.log')){
        Copy-Item -LiteralPath (Join-Path $control $name) -Destination (Join-Path $work $name)
    }
}
