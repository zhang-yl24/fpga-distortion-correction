$ErrorActionPreference = 'Stop'
$backupRoot = 'E:\Pango\Downloads\PDS_Full_Package'
$destRoot = 'D:\English\FPGA\vendor\pds'
$resolvedBackup = (Resolve-Path -LiteralPath $backupRoot).Path.TrimEnd('\')
if ($resolvedBackup -cne $backupRoot) { throw 'Unexpected backup path' }
$items = @(Get-Item -LiteralPath $backupRoot) + @(Get-ChildItem -LiteralPath $backupRoot -Recurse -Force)
if ($items | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) { throw 'Backup contains a link; refusing recursive cleanup' }
foreach ($scope in @('Process','User','Machine')) {
    $activeLicense = [Environment]::GetEnvironmentVariable('PANGO_LICENSE_FILE',$scope)
    if ($activeLicense -and $activeLicense.Contains($backupRoot)) { throw 'An active license points into this backup' }
}
$recoverySetup = 'E:\Pango\Downloads\PDS_2022.2-SP6.4-win64\Setup.exe'
if (!(Test-Path -LiteralPath $recoverySetup) -or !(Test-Path -LiteralPath 'E:\Pango\PDS_2022.2-SP6.4\bin\pds_shell.exe')) { throw 'Installed toolchain or recovery installer missing' }
New-Item -ItemType Directory -Force -Path $destRoot | Out-Null
$kept = @()
$files = @(Get-ChildItem -LiteralPath $backupRoot -Recurse -File)
foreach ($sourceFile in $files) {
    if ($sourceFile.Extension -eq '.zip') { continue }
    $relative = $sourceFile.FullName.Substring($backupRoot.Length+1)
    $private = $sourceFile.Extension -eq '.lic' -or $relative.Contains('小眼睛FPGA--license')
    $dest = Join-Path $destRoot (Join-Path $(if ($private) {'private'} else {'reference'}) $relative)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
    Copy-Item -LiteralPath $sourceFile.FullName -Destination $dest
    $before = (Get-FileHash -LiteralPath $sourceFile.FullName -Algorithm SHA256).Hash
    $after = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash
    if ($before -cne $after) { throw "Copy verification failed: $relative" }
    $kept += [pscustomobject]@{File=$relative;Destination=$dest;Bytes=$sourceFile.Length;SHA256=$after}
}
$manifest = [pscustomobject]@{
    Timestamp=(Get-Date).ToString('o');Source=$backupRoot;Preserved=$kept;
    RecoveryInstaller=$recoverySetup;InstalledToolchain='E:\Pango\PDS_2022.2-SP6.4';
    RemovedArchives=@($files | Where-Object Extension -eq '.zip' | Select-Object FullName,Length);
    Reason='User requested preserving useful files locally and deleting unused backups. 2025.2 is unused; 2022.2 installed and separate Setup.exe retained.'
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $destRoot 'cleanup-manifest.json') -Encoding utf8
$zipBytes = ($files | Where-Object Extension -eq '.zip' | Measure-Object Length -Sum).Sum
# Repeat the exact-path check immediately before the recursive operation.
if ((Resolve-Path -LiteralPath $backupRoot).Path.TrimEnd('\') -cne 'E:\Pango\Downloads\PDS_Full_Package') { throw 'Cleanup target changed' }
Remove-Item -LiteralPath $backupRoot -Recurse -Force
if (Test-Path -LiteralPath $backupRoot) { throw 'Backup cleanup incomplete' }
Write-Output ("Preserved {0} files with matching SHA256; removed {1:N2} GiB of archive backups. Installed PDS and recovery Setup.exe retained." -f $kept.Count,($zipBytes/1GB))
