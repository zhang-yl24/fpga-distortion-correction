"""Exact, source-bound review of this direct build's observed warning bodies.

The inventory is immutable and separately source/receipt bound. Known compiler
cleanup/metadata notifications do not grant clock, pad or reset waivers. Native
functional/site/electrical/clock/CDC evidence remains mandatory at final proof.
"""
from collections import Counter
from pathlib import Path
import re

import hdmi_camera_direct_build as build
import hdmi_camera_direct_reductions as reductions

SELF=Path(__file__).resolve()
INVENTORY=build.WORK/'source-warning-inventory-a.json'
INVENTORY_SHA='f619f845e6fb2fe605ba4ff1b002ee0fe667dc9af32239e8772dedb0b882a727'
require,sha,read,ref=build.require,build.sha,build.read,build.ref


def warning_inventory(work,plan):
    prefix=build.paths.alias_path(build.ROOT,plan['RepoAlias'],work)
    result={}
    for path in sorted(work.rglob('*.log')):
        bodies=[line.strip().replace(prefix,'@BUILD@') for line in path.read_text(encoding='gb18030',errors='strict').splitlines()
            if line.lstrip().startswith('W:')]
        if bodies:result[path.relative_to(work).as_posix()]=dict(sorted(Counter(bodies).items()))
    return result


def table_facts(work):
    rows=[]
    for source,width in (('rtl/experimental/ms7200_1080p30_rearm_ctl.v',14),('rtl/experimental/ms7210_checked_ctl.v',13)):
        text=(work/'compiled'/source).read_text(encoding='utf-8-sig');flat=reductions.compact(text)
        values=[int(x,16) for x in re.findall(r"\d+'d\d+\s*:\s*cmd_data\s*=\s*\{16'h([0-9a-fA-F]+)\s*,",text)]
        require(values and max(values)<(1<<width),'command-table high address bits are not constant zero')
        assignments=re.findall(r'cmd_iic<=([^;]+);',flat)
        require(all(v in ('0',"24'd0",'cmd_data(cmd_index)') for v in assignments) and 'cmd_data(cmd_index)' in assignments,
            'command word has another assignment source')
        ids=re.findall(r"assign\s+device_id\s*=\s*8'h([0-9a-fA-F]+)\s*;",text)
        require(len(ids)==1 and int(ids[0],16)&8==0,'IIC device_id bit3 is not zero')
        rows.append({'Source':ref(work/'compiled'/source),'CommandRows':len(values),'MaximumAddress':max(values),
            'AddressBitsRequired':width,'CommandAssignments':assignments,'DeviceID':int(ids[0],16),
            'DeviceIDBit3Zero':True})
    return rows


def derive(build_plan):
    build_plan=Path(build_plan).absolute();work=build.work_path(build_plan.parent)
    plan=build.validate(build_plan);receipt=build.verify_execution(work/'execution-result.json')
    require(sha(INVENTORY)==INVENTORY_SHA,'direct warning inventory was modified')
    inventory=read(INVENTORY)
    require(inventory['BuildPlan']==ref(build_plan) and inventory['SourceBuildReceipt']==ref(work/'execution-result.json')
        and inventory['Target']==build.TARGET,'warning inventory identifies another direct source build')
    require(inventory['CompiledSources']==[{k:r[k] for k in ('Source','OriginalSHA256','CompiledSHA256')}
        for r in plan['CompiledInputs']],'source warning review belongs to another RTL closure')
    actual=warning_inventory(work,plan)
    require(actual==inventory['WarningBodiesByLog'],'unknown/missing/different source warning body')
    attrs=plan['Pins']['PinInventory'];directions={p:r['DIRECTION'] for p,r in attrs.items()}
    unique={line for counts in actual.values() for line in counts}
    for line in unique:
        m=re.fullmatch(r"W: Timing-(4086|4087): Port '([^']+)' is not constrained, it is treated as combinational (input|output)\.",line)
        if m:
            code,port,direction=m.groups()
            require(port in directions and directions[port] in (direction.upper(),'INOUT')
                and direction==('input' if code=='4086' else 'output'),'source external-AC warning port/direction differs')
        m=re.fullmatch(r'W: ConstraintEditor-4040: \[@BUILD@/(.+)\(line number: (\d+)\)\] Port (?:p:)?(\S+) has been placed at location (\S+), whose type is share pin\.',line)
        if m:
            name,number,port,loc=m.groups();require(port in attrs and attrs[port]['LOC']==loc,'share-pin warning location differs')
            source=work/name;require(source in (work/'compiled'/build.FDC,work/'device_map'/(build.TARGET+'.pcf')),
                'share-pin warning refers to another constraint file')
            native_line=source.read_text(encoding='gb18030',errors='strict').splitlines()[int(number)-1]
            require((native_line=='define_attribute {p:'+port+'} {PAP_IO_LOC} {'+loc+'}') or
                native_line.startswith('def_port {'+port+'} LOC='+loc+' '),'share-pin warning line/attribute differs')
    range_proof,range_inputs=reductions.derive(build_plan);facts=table_facts(work);watched={}
    for name,h in range_inputs.items():build.add(watched,name,h)
    for path in (SELF,INVENTORY):build.add(watched,path)
    return {'Schema':'hdmi-camera-direct-source-warning-review-v1','Target':build.TARGET,'Passed':True,
        'BuildPlan':ref(build_plan),'Inventory':ref(INVENTORY),'Counts':inventory['Counts'],
        'ReviewedWarningBodiesByLog':actual,'Interpretations':inventory['Interpretations'],
        'CounterRangeReviewPassed':range_proof['Passed'],'CommandTableFacts':facts,
        'UnknownWarningBodiesAccepted':False,'SourceToNativeFormalEquivalenceClaimed':False,
        'AdditionalTimingExceptionsAuthorized':False,'ExternalACAccepted':False}, {Path(p):h for p,h in watched.items()}
