param([ValidateSet('10MHz','5MHz','1MHz','500KHz','100KHz')][string]$Frequency='1MHz')
$ErrorActionPreference = 'Stop'
$checkRoot = 'D:\English\FPGA\hardware_check'
$pdsBin = 'E:\Pango\PDS_2022.2-SP6.4\bin'
$ownedServer = $null
$scanClient = $null
$scanTcl=Join-Path $checkRoot 'scan-only.tcl'
if($Frequency -ne '1MHz') {
    $scanTcl=Join-Path $checkRoot ('scan-only-'+$Frequency+'.tcl')
    (Get-Content -Raw (Join-Path $checkRoot 'scan-only.tcl')).Replace('-freq 1MHz','-freq '+$Frequency) |
        Set-Content -LiteralPath $scanTcl -Encoding ascii
}
try {
    $listener = Get-NetTCPConnection -LocalPort 65420 -State Listen -ErrorAction SilentlyContinue
    if (-not $listener) {
        $ownedServer = Start-Process -FilePath (Join-Path $pdsBin 'cdt_js.exe') -ArgumentList @('-port','65420','-work_dir',$checkRoot) -WorkingDirectory $checkRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $checkRoot 'jtag-server.out.txt') -RedirectStandardError (Join-Path $checkRoot 'jtag-server.err.txt')
        Start-Sleep -Seconds 2
    }
    $scanClient = Start-Process -FilePath (Join-Path $pdsBin 'cdt_cfg_shell.exe') -ArgumentList @('-file',$scanTcl,'-work_dir',$checkRoot) -WorkingDirectory $checkRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $checkRoot 'scan.out.txt') -RedirectStandardError (Join-Path $checkRoot 'scan.err.txt')
    if (-not $scanClient.WaitForExit(20000)) {
        Stop-Process -Id $scanClient.Id -ErrorAction SilentlyContinue
        Write-Output 'SCAN_TIMEOUT'
        throw 'JTAG scan timed out; no programming performed.'
    } else {
        Write-Output ('SCAN_EXIT_CODE=' + $scanClient.ExitCode)
    }
    $scanLog=Get-Content -Raw -LiteralPath (Join-Path $checkRoot 'scan.out.txt')
    Write-Output $scanLog
    Get-Content -LiteralPath (Join-Path $checkRoot 'scan.err.txt')
    if($scanClient.ExitCode -ne 0 -or (Get-Item (Join-Path $checkRoot 'scan.err.txt')).Length -gt 0 -or $scanLog -match '(?m)^E:' -or $scanLog -notmatch '0x00602899') {
        throw 'FPGA JTAG scan did not confirm PG2L100H IDCODE; no programming performed.'
    }
} finally {
    if ($scanClient -and -not $scanClient.HasExited) { Stop-Process -Id $scanClient.Id -ErrorAction SilentlyContinue }
    if ($ownedServer -and -not $ownedServer.HasExited) { Stop-Process -Id $ownedServer.Id -ErrorAction SilentlyContinue }
}
