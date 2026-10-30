param([Parameter(Mandatory=$true)][string]$OutputPath)
# Read display configuration only. No SetDisplayConfig/ChangeDisplaySettings,
# device enable/disable, serial/JTAG access or registry mutation is performed.
$ErrorActionPreference='Stop'
$displayCode=@'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class HdmiDisplaySnapshot {
 [StructLayout(LayoutKind.Sequential)] public struct LUID {public uint LowPart;public int HighPart;public override string ToString(){return HighPart.ToString("x8")+LowPart.ToString("x8");}}
 [StructLayout(LayoutKind.Sequential)] public struct RATIONAL {public uint Numerator,Denominator;public double Value {get{return Denominator==0?0:(double)Numerator/Denominator;}}}
 [StructLayout(LayoutKind.Sequential)] public struct REGION {public uint cx,cy;}
 [StructLayout(LayoutKind.Sequential)] public struct VIDEO {public ulong pixelRate;public RATIONAL hSyncFreq,vSyncFreq;public REGION activeSize,totalSize;public uint videoStandard,scanLineOrdering;}
 [StructLayout(LayoutKind.Sequential)] public struct SOURCE {public LUID adapterId;public uint id,modeInfoIdx,statusFlags;}
 [StructLayout(LayoutKind.Sequential)] public struct TARGET {public LUID adapterId;public uint id,modeInfoIdx,outputTechnology,rotation,scaling;public RATIONAL refreshRate;public uint scanLineOrdering;public int targetAvailable;public uint statusFlags;}
 [StructLayout(LayoutKind.Sequential)] public struct PATH {public SOURCE sourceInfo;public TARGET targetInfo;public uint flags;}
 [StructLayout(LayoutKind.Explicit,Size=64)] public struct MODE {[FieldOffset(0)]public uint infoType;[FieldOffset(4)]public uint id;[FieldOffset(8)]public LUID adapterId;[FieldOffset(16)]public VIDEO targetMode;[FieldOffset(16)]public uint sourceWidth;[FieldOffset(20)]public uint sourceHeight;[FieldOffset(24)]public uint sourcePixelFormat;[FieldOffset(28)]public int sourceX;[FieldOffset(32)]public int sourceY;}
 [StructLayout(LayoutKind.Sequential)] public struct HEADER {public uint type,size;public LUID adapterId;public uint id;}
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] public struct TARGETNAME {public HEADER header;public uint flags,outputTechnology;public ushort edidManufactureId,edidProductCodeId;public uint connectorInstance;[MarshalAs(UnmanagedType.ByValTStr,SizeConst=64)]public string friendlyName;[MarshalAs(UnmanagedType.ByValTStr,SizeConst=128)]public string path;}
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] public struct SOURCENAME {public HEADER header;[MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)]public string gdiName;}
 [DllImport("user32.dll")]static extern int GetDisplayConfigBufferSizes(uint flags,out uint np,out uint nm);
 [DllImport("user32.dll")]static extern int QueryDisplayConfig(uint flags,ref uint np,[Out]PATH[] paths,ref uint nm,[Out]MODE[] modes,IntPtr topology);
 [DllImport("user32.dll",EntryPoint="DisplayConfigGetDeviceInfo")]static extern int TargetName(ref TARGETNAME packet);
 [DllImport("user32.dll",EntryPoint="DisplayConfigGetDeviceInfo")]static extern int SourceName(ref SOURCENAME packet);
 public static object Read(uint queryFlags){
  uint np,nm;int rc=GetDisplayConfigBufferSizes(queryFlags,out np,out nm);if(rc!=0)throw new Exception("GetDisplayConfigBufferSizes="+rc);
  PATH[] paths=new PATH[np];MODE[] modes=new MODE[nm];rc=QueryDisplayConfig(queryFlags,ref np,paths,ref nm,modes,IntPtr.Zero);if(rc!=0)throw new Exception("QueryDisplayConfig="+rc);
  var rows=new List<object>();
  for(int i=0;i<np;i++){PATH p=paths[i];TARGETNAME t=new TARGETNAME();t.header.type=2;t.header.size=(uint)Marshal.SizeOf(typeof(TARGETNAME));t.header.adapterId=p.targetInfo.adapterId;t.header.id=p.targetInfo.id;int tc=TargetName(ref t);
   SOURCENAME s=new SOURCENAME();s.header.type=1;s.header.size=(uint)Marshal.SizeOf(typeof(SOURCENAME));s.header.adapterId=p.sourceInfo.adapterId;s.header.id=p.sourceInfo.id;int sc=SourceName(ref s);
   object signal=null,source=null;uint mi=p.targetInfo.modeInfoIdx;
   if(mi<nm && modes[mi].infoType==2){VIDEO v=modes[mi].targetMode;signal=new{activeWidth=v.activeSize.cx,activeHeight=v.activeSize.cy,totalWidth=v.totalSize.cx,totalHeight=v.totalSize.cy,pixelRateHz=v.pixelRate,vSyncNumerator=v.vSyncFreq.Numerator,vSyncDenominator=v.vSyncFreq.Denominator,vSyncHz=v.vSyncFreq.Value,hSyncHz=v.hSyncFreq.Value,scanLineOrdering=v.scanLineOrdering};}
   mi=p.sourceInfo.modeInfoIdx;if(mi<nm && modes[mi].infoType==1){MODE m=modes[mi];source=new{width=m.sourceWidth,height=m.sourceHeight,x=m.sourceX,y=m.sourceY,pixelFormat=m.sourcePixelFormat};}
   rows.Add(new{gdiName=s.gdiName,sourceNameResult=sc,friendlyName=t.friendlyName,targetNameResult=tc,monitorPath=t.path,edidManufacturer=t.edidManufactureId,edidProduct=t.edidProductCodeId,nameFlags=t.flags,sourceAdapter=p.sourceInfo.adapterId.ToString(),sourceId=p.sourceInfo.id,targetAdapter=p.targetInfo.adapterId.ToString(),targetId=p.targetInfo.id,outputTechnology=p.targetInfo.outputTechnology,targetAvailable=p.targetInfo.targetAvailable!=0,pathActive=(p.flags&1)!=0,pathFlags=p.flags,rotation=p.targetInfo.rotation,scaling=p.targetInfo.scaling,pathRefreshNumerator=p.targetInfo.refreshRate.Numerator,pathRefreshDenominator=p.targetInfo.refreshRate.Denominator,pathRefreshHz=p.targetInfo.refreshRate.Value,targetSignal=signal,desktopSource=source});
  }
  return new{queryFlags=queryFlags,returnCode=rc,pathStructBytes=Marshal.SizeOf(typeof(PATH)),modeStructBytes=Marshal.SizeOf(typeof(MODE)),targetNameStructBytes=Marshal.SizeOf(typeof(TARGETNAME)),pathCount=np,paths=rows};
 }
}
'@
Add-Type -TypeDefinition $displayCode -Language CSharp
function Decode-MonitorText($Codes){
    if($null -eq $Codes){return ''}
    return (-join @($Codes | Where-Object {$_ -ne 0} | ForEach-Object {[char]$_}))
}
$started=[DateTime]::UtcNow.ToString('o')
$active=[HdmiDisplaySnapshot]::Read(2)
$all=[HdmiDisplaySnapshot]::Read(1)
$monitorIds=@();$present=@();$wmiError=$null;$pnpError=$null
try{
    $monitorIds=@(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorID | ForEach-Object {
        [ordered]@{InstanceName=$_.InstanceName;Active=$_.Active;Manufacturer=(Decode-MonitorText $_.ManufacturerName);ProductCode=(Decode-MonitorText $_.ProductCodeID);FriendlyName=(Decode-MonitorText $_.UserFriendlyName)}
    })
}catch{$wmiError=$_.Exception.Message}
try{$present=@(Get-PnpDevice -Class Monitor -PresentOnly | Select-Object Status,FriendlyName,InstanceId)}catch{$pnpError=$_.Exception.Message}
$absoluteOutput=[IO.Path]::GetFullPath($OutputPath)
$report=[ordered]@{
    Schema='windows-hdmi-display-snapshot-v1';StartedUTC=$started;EndedUTC=[DateTime]::UtcNow.ToString('o');ReadOnly=$true;DisplaySettingsChanged=$false;
    ScriptPath=$PSCommandPath;ScriptSHA256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();
    ReproduceArgv=@('pwsh.exe','-NoProfile','-File',$PSCommandPath,'-OutputPath','NEW-OUTPUT.json');ActualOutputPath=$absoluteOutput;
    ActiveDisplayConfig=$active;AllDisplayConfig=$all;WmiMonitors=$monitorIds;WmiError=$wmiError;PresentMonitors=$present;PnpError=$pnpError;
    Limits='Windows configured target signals and enumerated sinks only; not FPGA-side timing or successful HDMI reception. Raw pixel-rate/hSync can include driver-specific panel conventions. Source desktop dimensions may differ from target signal.'
}
$json=$report | ConvertTo-Json -Depth 10
$stream=[IO.File]::Open($absoluteOutput,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
$writer=$null
try{$writer=[IO.StreamWriter]::new($stream,[Text.UTF8Encoding]::new($false));$writer.Write($json);$writer.Flush()}finally{if($writer){$writer.Dispose()}else{$stream.Dispose()}}
[ordered]@{Output=$absoluteOutput;ActivePaths=$active.paths;AvailableTargets=@($all.paths | Where-Object {$_.targetAvailable} | Select-Object -Unique targetAdapter,targetId,outputTechnology,friendlyName,monitorPath);WmiMonitors=$monitorIds;WmiError=$wmiError;PresentMonitors=$present;PnpError=$pnpError} | ConvertTo-Json -Depth 8
