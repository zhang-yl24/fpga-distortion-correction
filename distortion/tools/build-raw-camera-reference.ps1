param([ValidateRange(1,30)][int]$MaximumMinutes=20,[string]$ValidateExistingDirectory='')
# A bounded offline build for the PREVIOUS physical CAM2 board port only.
# No hardware or configuration-server commands occur in this script.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$target='raw_camera_capture_cam2_ref'
$approved=[System.IO.Path]::GetFullPath((Join-Path $root 'build\offline-20261024'))
if(!(Test-Path -LiteralPath $approved -PathType Container)){throw 'Approved offline scratch directory must exist'}
if($ValidateExistingDirectory){
    $work=[System.IO.Path]::GetFullPath($ValidateExistingDirectory)
    if(!$work.StartsWith($approved+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or !(Test-Path -LiteralPath $work -PathType Container)){throw 'Existing build must be below approved scratch'}
    if(Test-Path -LiteralPath (Join-Path $work 'validated-build.json')){throw 'Existing validated artifact is immutable'}
    $prior=Get-Content -Raw -Encoding UTF8 (Join-Path $work 'raw-board-build-result.json') | ConvertFrom-Json
    if($prior.Target -ne $target -or $prior.HardwareAccessed -ne $false){throw 'Existing run identity differs'}
}else{
    $work=Join-Path $approved ('raw-board-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    New-Item -ItemType Directory -Path $work | Out-Null
}
$sourceManifest=Get-Content -Raw -Encoding UTF8 (Join-Path $root ('board\'+$target+'-sources.json')) | ConvertFrom-Json
$hashes=@{}
foreach($name in $sourceManifest.source_files){$hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash}
foreach($entry in $sourceManifest.SourceSHA256.PSObject.Properties){if($hashes[$entry.Name] -ne $entry.Value){throw 'Prepared candidate source no longer matches its manifest'}}
if($ValidateExistingDirectory){
    foreach($entry in $prior.SourceSHA256.PSObject.Properties){if($hashes[$entry.Name] -ne $entry.Value){throw 'Source differs from the original PDS run snapshot'}}
    if(@($prior.SourceSHA256.PSObject.Properties).Count -ne $hashes.Count){throw 'Source snapshot cardinality differs'}
}
$tcl=Join-Path $root ('board\build-'+$target+'.tcl')
$start=[DateTime]::UtcNow
$result=[ordered]@{Target=$target;Passed=$false;HardwareAccessed=$false;NewModuleCompatibilityVerified=$false;
    StartedUtc=$start.ToString('o');OutputDirectory=$work;SourceSHA256=$hashes;RawCaptureContract=$sourceManifest.RawCaptureContract}
$child=$null
try{
    if(!$ValidateExistingDirectory){
        $child=Start-Process -FilePath (Join-Path $teamPdsBin 'pds_shell.exe') -WindowStyle Hidden -PassThru -ArgumentList @('-file',$tcl,'-work_dir',$work,'-project_name',$target) -RedirectStandardOutput (Join-Path $work 'build-stdout.log') -RedirectStandardError (Join-Path $work 'build-stderr.log')
        # Retain the native handle before exit; otherwise Windows PowerShell
        # can lose access to ExitCode even though WaitForExit returned true.
        $ownedNativeHandle=$child.Handle
        while(!$child.WaitForExit(10000)){
            if([DateTime]::UtcNow -ge $start.AddMinutes($MaximumMinutes)){
                & "$env:SystemRoot\System32\taskkill.exe" /PID $child.Id /T /F | Out-File (Join-Path $work 'bounded-stop.log')
                throw 'Owned PDS build exceeded its bound; no candidate is validated'
            }
        }
        $child.Refresh();$result.ExitCode=$child.ExitCode
    }else{
        $result.ExitCode=$prior.ExitCode
        $result.OriginalWrapperError=$prior.Error
        $result.ValidationOnly=$true
    }
    $log=Get-Content -Raw (Join-Path $work 'build-stdout.log')
    if(($null -ne $result.ExitCode -and $result.ExitCode -ne 0) -or $log -match '(?m)^E:' -or $log -notmatch '(?m)^Executing : gen_bit_stream\b[^\r\n]* successfully\.'){
        throw 'PDS did not complete bitstream generation; see retained build logs'
    }
    $bit=Join-Path $work ('generate_bitstream\'+$target+'.sbit')
    $timing=Join-Path $work ('place_route\'+$target+'_timing_summary_after_hold_fix.txt')
    if(!(Test-Path -LiteralPath $timing)){throw 'Final after-hold-fix timing report is absent'}
    if((Get-Content -Raw $timing) -notmatch 'All Constraints Met'){throw 'Final timing did not meet all constraints'}
    $pins=Get-Content -Raw -Encoding UTF8 (Join-Path $root ('board\'+$target+'-pins.json')) | ConvertFrom-Json
    $pinReport=Get-Content -Raw (Join-Path $work ('place_route\'+$target+'_prr.prt'))
    foreach($entry in $pins.PSObject.Properties){
        if($pinReport -notmatch ('(?m)^'+[regex]::Escape($entry.Value)+'\|[^\r\n]*\|'+[regex]::Escape($entry.Name)+'\|')){throw ('Unverified old-board reference pin: '+$entry.Name)}
    }
    foreach($name in $sourceManifest.source_files){if((Get-FileHash -LiteralPath (Join-Path $root $name)).Hash -ne $hashes[$name]){throw 'Candidate source changed during PDS build'}}
    $validated=[ordered]@{Target=$target;Device='PG2L100H';SCBV='High Voltage';SHA256=(Get-FileHash -LiteralPath $bit).Hash;
        Bitstream=$bit;TimingReport=$timing;TimingSHA256=(Get-FileHash -LiteralPath $timing).Hash;
        SourceSHA256=$hashes;RawCaptureContract=$sourceManifest.RawCaptureContract;HardwareAccessed=$false;
        ProcessExitCode=$result.ExitCode;ProcessExitCodeAvailable=($null -ne $result.ExitCode);
        CompletionEvidence='Exact successful gen_bit_stream log, no PDS E: diagnostics, unchanged original source snapshot, final timing report, actual bitstream and routed pin report';
        NewModuleCompatibilityVerified=$false;ReferenceBoardPort='previous CAM2 wiring only; D5 AA23';
        Limits='Offline routed candidate for old board-port constraints. No download, new-module electrical/pinout confirmation, real sensor ID, eye assignment, timing measurement or optical acceptance.'}
    $validated | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'validated-build.json') -Encoding utf8
    $result.Passed=$true;$result.ValidatedBuild=Join-Path $work 'validated-build.json'
}catch{
    $result.Error=$_.Exception.Message
    throw
}finally{
    if($child -and !$child.HasExited){& "$env:SystemRoot\System32\taskkill.exe" /PID $child.Id /T /F | Out-File (Join-Path $work 'owned-stop.log')}
    if($child){$child.Dispose()}
    $result.EndedUtc=[DateTime]::UtcNow.ToString('o')
    $record=if($ValidateExistingDirectory){'raw-board-revalidation.json'}else{'raw-board-build-result.json'}
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work $record) -Encoding utf8
}
Write-Output ('Candidate evidence: '+(Join-Path $work 'validated-build.json'))
