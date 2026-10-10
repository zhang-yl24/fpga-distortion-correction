param([string[]]$Frequencies=@('100KHz','500KHz','1MHz','5MHz','1MHz'),[int]$Repeats=3)
# Read-only scan and IDCODE checks. Never programs or erases a device.
$ErrorActionPreference='Stop'
$pdsBin='E:\Pango\PDS_2022.2-SP6.4\bin'
$runRoot=Join-Path $PSScriptRoot ('jtag-sweep-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $runRoot | Out-Null
$server=$null;$client=$null;$results=@()
try {
    if(Get-NetTCPConnection -LocalPort 65420 -State Listen -ErrorAction SilentlyContinue){throw 'JTAG server port is occupied; leaving existing server untouched'}
    $server=Start-Process -FilePath (Join-Path $pdsBin 'cdt_js.exe') -ArgumentList @('-port','65420','-work_dir',$runRoot) -WorkingDirectory $runRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runRoot 'server.out.txt') -RedirectStandardError (Join-Path $runRoot 'server.err.txt')
    Start-Sleep -Seconds 2
    $i=0
    foreach($freq in $Frequencies){
        if($freq -notin @('100KHz','500KHz','1MHz','5MHz','10MHz','15MHz')){throw 'Frequency not supported by the connected USB Cable II'}
        $i++;$stem=Join-Path $runRoot ($i.ToString('00')+'-'+$freq)
        $lines=@('cfg_set_tcl_break -flag true','cfg_connect -ip 127.0.0.1 -port 65420',('cfg_set_cable_property -index 0 -freq '+$freq))
        for($n=0;$n -lt $Repeats;$n++){$lines+=@('cfg_scan_chain','cfg_read_device_property -mode 0 -device_index 0')}
        $lines+=@('cfg_disconnect','cfg_close')
        $lines | Set-Content -LiteralPath ($stem+'.tcl') -Encoding ascii
        $client=Start-Process -FilePath (Join-Path $pdsBin 'cdt_cfg_shell.exe') -ArgumentList @('-file',($stem+'.tcl'),'-work_dir',$runRoot) -WorkingDirectory $runRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput ($stem+'.out.txt') -RedirectStandardError ($stem+'.err.txt')
        $timedOut=-not $client.WaitForExit(20000)
        if($timedOut){Stop-Process -Id $client.Id -ErrorAction SilentlyContinue;$client.WaitForExit()}
        $log=[string](Get-Content -Raw -LiteralPath ($stem+'.out.txt'))
        $err=[string](Get-Content -Raw -LiteralPath ($stem+'.err.txt'))
        $ids=[regex]::Matches($log,'(?m)^The ID value is: 0x00602899\s*$').Count
        $pass=(!$timedOut -and $client.ExitCode -eq 0 -and $log -notmatch '(?im)^E:|failed|error' -and [string]::IsNullOrWhiteSpace($err) -and $ids -eq $Repeats)
        $result=[pscustomobject]@{Frequency=$freq;Passed=$pass;CorrectIdReads=$ids;Required=$Repeats;ExitCode=$client.ExitCode;TimedOut=$timedOut;UnsupportedFrequency=($log -match 'input Frequency is not support');Log=($stem+'.out.txt')}
        $results+=$result
        Write-Output ($result | ConvertTo-Json -Compress)
        $results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runRoot 'results.json') -Encoding utf8
    }
    Write-Output ('RESULTS='+$runRoot)
} finally {
    if($client -and !$client.HasExited){Stop-Process -Id $client.Id -ErrorAction SilentlyContinue}
    if($server -and !$server.HasExited){Stop-Process -Id $server.Id -ErrorAction SilentlyContinue}
}
